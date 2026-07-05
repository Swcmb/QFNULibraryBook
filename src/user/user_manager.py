import fcntl
import os
import tempfile
from datetime import datetime, timedelta
from typing import Dict, List, Optional

import yaml

logger = __import__('logging').getLogger(__name__)

PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
CONFIGS_DIR = os.path.join(PROJECT_ROOT, 'configs')
USERS_INDEX = os.path.join(CONFIGS_DIR, 'users.yml')


def _load_yaml(path: str) -> Dict:
    if not os.path.exists(path):
        return {}
    with open(path, 'r', encoding='utf-8') as f:
        return yaml.safe_load(f) or {}


def _atomic_write_yaml(path: str, data: Dict) -> None:
    os.makedirs(os.path.dirname(path), exist_ok=True)
    fd, tmp_path = tempfile.mkstemp(dir=os.path.dirname(path), suffix='.tmp')
    try:
        with os.fdopen(fd, 'w', encoding='utf-8') as f:
            yaml.safe_dump(data, f, allow_unicode=True, sort_keys=False)
        os.replace(tmp_path, path)
    except Exception:
        if os.path.exists(tmp_path):
            os.remove(tmp_path)
        raise


def _acquire_file_lock(path: str, exclusive: bool = True) -> int:
    fd = os.open(path, os.O_RDWR | os.O_CREAT)
    lock_type = fcntl.LOCK_EX if exclusive else fcntl.LOCK_SH
    fcntl.flock(fd, lock_type)
    return fd


def _release_file_lock(fd: int) -> None:
    fcntl.flock(fd, fcntl.LOCK_UN)
    os.close(fd)


class UserManager:
    def register_user(self, username: str, password: str) -> bool:
        fd = None
        try:
            fd = _acquire_file_lock(USERS_INDEX)
            users_index = _load_yaml(USERS_INDEX)
            users_list = users_index.get('users', [])

            for entry in users_list:
                cfg_path = os.path.join(CONFIGS_DIR, entry['config'])
                if os.path.exists(cfg_path):
                    cfg_data = _load_yaml(cfg_path)
                    if cfg_data.get('USERNAME') == username:
                        existing_pwd = cfg_data.get('PASSWORD', '')
                        if existing_pwd != password:
                            cfg_data['PASSWORD'] = password
                            _atomic_write_yaml(cfg_path, cfg_data)
                            logger.info(f'用户 {username} 密码已更新')
                        return True

            new_filename = self._next_student_filename()
            if not new_filename:
                logger.error(f'用户 {username} 注册失败：账号数量已达上限')
                return False

            new_cfg = {
                'USERNAME': username,
                'PASSWORD': password,
                'MODE': '',
                'SEAT_ID': [],
                'CLASSROOMS_NAME': [],
                'DATE': 'today',
                'PUSH_METHOD': '',
                'DD_BOT_TOKEN': '',
                'DD_BOT_SECRET': '',
                'CHANNEL_ID': '',
                'TELEGRAM_BOT_TOKEN': '',
                'BARK_URL': '',
                'BARK_EXTRA': '',
                'ANPUSH_TOKEN': '',
                'ANPUSH_CHANNEL': '',
                'GITHUB': False,
                'SUBSCRIPTION_TYPE': 'none',
                'SUBSCRIPTION_EXPIRES': '',
                'SUBSCRIPTION_STATUS': 'inactive',
                'CHECKIN_TIME': '08:01',
                'SIGNOUT_TIME': '21:01',
            }
            new_path = os.path.join(CONFIGS_DIR, new_filename)
            _atomic_write_yaml(new_path, new_cfg)

            users_index.setdefault('users', []).append({
                'config': new_filename,
                'name': f'用户 {username}',
            })
            _atomic_write_yaml(USERS_INDEX, users_index)

            logger.info(f'用户 {username} 首次登录，已自动注册')
            return True
        finally:
            if fd:
                _release_file_lock(fd)

    def _next_student_filename(self) -> Optional[str]:
        for i in range(1, 27):
            candidate = f'student{chr(ord("A") + i - 1)}.yml'
            if not os.path.exists(os.path.join(CONFIGS_DIR, candidate)):
                return candidate
        return None

    def get_user_config_path(self, username: str) -> Optional[str]:
        users_index = _load_yaml(USERS_INDEX)
        for entry in users_index.get('users', []):
            cfg_path = os.path.join(CONFIGS_DIR, entry['config'])
            if os.path.exists(cfg_path):
                cfg_data = _load_yaml(cfg_path)
                if cfg_data.get('USERNAME') == username:
                    return cfg_path
        return None

    def update_subscription(self, username: str, plan_type: str, duration_days: int) -> bool:
        cfg_path = self.get_user_config_path(username)
        if not cfg_path:
            return False

        fd = None
        try:
            fd = _acquire_file_lock(cfg_path)
            cfg_data = _load_yaml(cfg_path)

            now = datetime.now()
            expires_str = cfg_data.get('SUBSCRIPTION_EXPIRES', '')
            if expires_str:
                try:
                    expires = datetime.strptime(expires_str, '%Y-%m-%d')
                    if expires > now:
                        new_expires = expires + timedelta(days=duration_days)
                    else:
                        new_expires = now + timedelta(days=duration_days)
                except ValueError:
                    new_expires = now + timedelta(days=duration_days)
            else:
                new_expires = now + timedelta(days=duration_days)

            cfg_data['SUBSCRIPTION_TYPE'] = plan_type
            cfg_data['SUBSCRIPTION_EXPIRES'] = new_expires.strftime('%Y-%m-%d')
            cfg_data['SUBSCRIPTION_STATUS'] = 'active'
            _atomic_write_yaml(cfg_path, cfg_data)

            logger.info(f'用户 {username} 订阅已更新：{plan_type}，到期时间：{cfg_data["SUBSCRIPTION_EXPIRES"]}')
            return True
        finally:
            if fd:
                _release_file_lock(fd)

    def is_subscription_active(self, username: str) -> bool:
        cfg_path = self.get_user_config_path(username)
        if not cfg_path:
            return False

        cfg_data = _load_yaml(cfg_path)
        status = cfg_data.get('SUBSCRIPTION_STATUS', '')
        if status != 'active':
            return False

        expires_str = cfg_data.get('SUBSCRIPTION_EXPIRES', '')
        if not expires_str:
            return False

        try:
            expires = datetime.strptime(expires_str, '%Y-%m-%d')
            return expires > datetime.now()
        except ValueError:
            return False

    def get_subscription_info(self, username: str) -> Optional[Dict]:
        cfg_path = self.get_user_config_path(username)
        if not cfg_path:
            return None

        cfg_data = _load_yaml(cfg_path)
        expires_str = cfg_data.get('SUBSCRIPTION_EXPIRES', '')
        days_left = 0
        if expires_str:
            try:
                expires = datetime.strptime(expires_str, '%Y-%m-%d')
                diff = expires - datetime.now()
                days_left = max(0, diff.days)
            except ValueError:
                pass

        return {
            'type': cfg_data.get('SUBSCRIPTION_TYPE', 'none'),
            'status': cfg_data.get('SUBSCRIPTION_STATUS', 'inactive'),
            'expires_at': expires_str,
            'checkin_time': cfg_data.get('CHECKIN_TIME', '08:01'),
            'signout_time': cfg_data.get('SIGNOUT_TIME', '21:01'),
            'days_left': days_left,
        }

    def list_subscribed_users(self) -> List[Dict]:
        result = []
        users_index = _load_yaml(USERS_INDEX)
        for entry in users_index.get('users', []):
            cfg_path = os.path.join(CONFIGS_DIR, entry['config'])
            if os.path.exists(cfg_path):
                cfg_data = _load_yaml(cfg_path)
                username = cfg_data.get('USERNAME', '')
                sub_status = cfg_data.get('SUBSCRIPTION_STATUS', '')
                if sub_status == 'active':
                    result.append({
                        'username': username,
                        'plan_type': cfg_data.get('SUBSCRIPTION_TYPE', ''),
                        'status': sub_status,
                        'expires_at': cfg_data.get('SUBSCRIPTION_EXPIRES', ''),
                    })
        return result

    def save_subscription_snapshot(self, username: str) -> Dict:
        cfg_path = self.get_user_config_path(username)
        if not cfg_path:
            return {}

        cfg_data = _load_yaml(cfg_path)
        return {
            'subscription_type': cfg_data.get('SUBSCRIPTION_TYPE', 'none'),
            'subscription_expires': cfg_data.get('SUBSCRIPTION_EXPIRES', ''),
            'subscription_status': cfg_data.get('SUBSCRIPTION_STATUS', 'inactive'),
        }

    def restore_subscription_snapshot(self, username: str, snapshot: Dict) -> bool:
        cfg_path = self.get_user_config_path(username)
        if not cfg_path:
            return False

        fd = None
        try:
            fd = _acquire_file_lock(cfg_path)
            cfg_data = _load_yaml(cfg_path)
            cfg_data['SUBSCRIPTION_TYPE'] = snapshot.get('subscription_type', 'none')
            cfg_data['SUBSCRIPTION_EXPIRES'] = snapshot.get('subscription_expires', '')
            cfg_data['SUBSCRIPTION_STATUS'] = snapshot.get('subscription_status', 'inactive')
            _atomic_write_yaml(cfg_path, cfg_data)
            return True
        finally:
            if fd:
                _release_file_lock(fd)

    def mark_subscription_abnormal(self, username: str) -> bool:
        cfg_path = self.get_user_config_path(username)
        if not cfg_path:
            return False

        fd = None
        try:
            fd = _acquire_file_lock(cfg_path)
            cfg_data = _load_yaml(cfg_path)
            cfg_data['SUBSCRIPTION_STATUS'] = 'abnormal'
            _atomic_write_yaml(cfg_path, cfg_data)
            logger.warning(f'用户 {username} 订阅已标记为异常待人工处理')
            return True
        finally:
            if fd:
                _release_file_lock(fd)
