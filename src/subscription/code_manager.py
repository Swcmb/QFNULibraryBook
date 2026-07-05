import fcntl
import os
import secrets
import tempfile
from datetime import datetime, timedelta
from typing import Dict, List, Optional

import yaml

logger = __import__('logging').getLogger(__name__)

PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
DATA_DIR = os.path.join(PROJECT_ROOT, 'data')
CODES_FILE = os.path.join(DATA_DIR, 'activation_codes.yml')
PLANS_FILE = os.path.join(DATA_DIR, 'plans.yml')

CODE_LENGTH = 16
CODE_CHARS = 'ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789'


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


class ActivationCodeManager:
    def __init__(self):
        self._ensure_files()

    def _ensure_files(self):
        os.makedirs(DATA_DIR, exist_ok=True)
        if not os.path.exists(CODES_FILE):
            _atomic_write_yaml(CODES_FILE, {'codes': []})
        if not os.path.exists(PLANS_FILE):
            self._init_plans()

    def _init_plans(self):
        plans = {
            'plans': [
                {
                    'id': 'checkin_monthly',
                    'name': '自动签到月卡',
                    'description': '每日自动签到，省心省力，再也不用担心迟到',
                    'price': 9.9,
                    'type': 'checkin',
                    'duration_days': 30,
                    'default_checkin_time': '08:01',
                    'default_signout_time': '',
                    'enabled': True,
                },
                {
                    'id': 'signout_monthly',
                    'name': '自动签退月卡',
                    'description': '每日自动签退，不用担心超时被记录',
                    'price': 9.9,
                    'type': 'signout',
                    'duration_days': 30,
                    'default_checkin_time': '',
                    'default_signout_time': '21:01',
                    'enabled': True,
                },
                {
                    'id': 'combo_monthly',
                    'name': '签到签退组合包',
                    'description': '自动签到 + 自动签退，全程无忧，性价比之选',
                    'price': 16.9,
                    'type': 'combo',
                    'duration_days': 30,
                    'default_checkin_time': '08:01',
                    'default_signout_time': '21:01',
                    'enabled': True,
                },
            ]
        }
        _atomic_write_yaml(PLANS_FILE, plans)

    def _generate_random_code(self) -> str:
        return ''.join(secrets.choice(CODE_CHARS) for _ in range(CODE_LENGTH))

    def generate_code(self, plan_id: str, bound_username: str = '') -> Dict:
        fd = None
        try:
            fd = _acquire_file_lock(CODES_FILE)
            codes_data = _load_yaml(CODES_FILE)
            codes_list = codes_data.setdefault('codes', [])

            plans_data = _load_yaml(PLANS_FILE)
            plan = None
            for p in plans_data.get('plans', []):
                if p['id'] == plan_id and p.get('enabled', True):
                    plan = p
                    break

            if not plan:
                raise ValueError(f'套餐不存在或已禁用: {plan_id}')

            code = self._generate_random_code()
            max_retries = 5
            retry_count = 0
            while any(c['code'] == code for c in codes_list) and retry_count < max_retries:
                code = self._generate_random_code()
                retry_count += 1

            if retry_count >= max_retries:
                raise RuntimeError('生成激活码失败，重试次数过多')

            now = datetime.now()
            expires_at = now + timedelta(hours=24)

            new_code = {
                'code': code,
                'plan_type': plan['type'],
                'plan_id': plan_id,
                'price': plan['price'],
                'bound_username': bound_username,
                'used_by': '',
                'created_at': now.isoformat(),
                'expires_at': expires_at.isoformat(),
                'activated_at': '',
                'status': 'pending',
                'duration_days': plan['duration_days'],
            }

            codes_list.append(new_code)
            _atomic_write_yaml(CODES_FILE, codes_data)

            logger.info(f'激活码生成成功: {code}，套餐: {plan_id}')
            return new_code
        finally:
            if fd:
                _release_file_lock(fd)

    def generate_codes(self, plan_id: str, count: int, bound_username: str = '') -> List[Dict]:
        result = []
        for _ in range(min(count, 100)):
            code = self.generate_code(plan_id, bound_username)
            result.append(code)
        return result

    def verify_code(self, code: str, username: str) -> Optional[Dict]:
        fd = None
        try:
            fd = _acquire_file_lock(CODES_FILE, exclusive=False)
            codes_data = _load_yaml(CODES_FILE)

            for code_entry in codes_data.get('codes', []):
                if code_entry['code'] == code:
                    now = datetime.now()
                    expires = datetime.fromisoformat(code_entry['expires_at'])

                    if code_entry['status'] == 'revoked':
                        return {'valid': False, 'error': '激活码已作废', 'error_code': 'CODE_REVOKED'}

                    if code_entry['status'] == 'active':
                        return {'valid': False, 'error': '激活码已使用', 'error_code': 'CODE_USED'}

                    if expires < now:
                        return {'valid': False, 'error': '激活码已过期', 'error_code': 'CODE_EXPIRED'}

                    if code_entry['bound_username'] and code_entry['bound_username'] != username:
                        return {'valid': False, 'error': '激活码与学号不匹配', 'error_code': 'CODE_USER_MISMATCH'}

                    return {'valid': True, 'code_entry': code_entry}

            return {'valid': False, 'error': '激活码无效', 'error_code': 'CODE_INVALID'}
        finally:
            if fd:
                _release_file_lock(fd)

    def activate_code(self, code: str, username: str) -> bool:
        fd = None
        try:
            fd = _acquire_file_lock(CODES_FILE)
            codes_data = _load_yaml(CODES_FILE)

            for code_entry in codes_data.get('codes', []):
                if code_entry['code'] == code:
                    now = datetime.now()
                    code_entry['status'] = 'active'
                    code_entry['activated_at'] = now.isoformat()
                    code_entry['used_by'] = username
                    _atomic_write_yaml(CODES_FILE, codes_data)
                    logger.info(f'激活码已激活: {code}，用户: {username}')
                    return True

            return False
        finally:
            if fd:
                _release_file_lock(fd)

    def list_codes(self, status: str = None) -> List[Dict]:
        fd = None
        try:
            fd = _acquire_file_lock(CODES_FILE, exclusive=False)
            codes_data = _load_yaml(CODES_FILE)
            codes = codes_data.get('codes', [])

            if status:
                codes = [c for c in codes if c.get('status') == status]

            codes.sort(key=lambda x: x['created_at'], reverse=True)
            return codes
        finally:
            if fd:
                _release_file_lock(fd)

    def revoke_code(self, code: str) -> bool:
        fd = None
        try:
            fd = _acquire_file_lock(CODES_FILE)
            codes_data = _load_yaml(CODES_FILE)

            for code_entry in codes_data.get('codes', []):
                if code_entry['code'] == code:
                    if code_entry['status'] != 'pending':
                        return False

                    code_entry['status'] = 'revoked'
                    _atomic_write_yaml(CODES_FILE, codes_data)
                    logger.info(f'激活码已作废: {code}')
                    return True

            return False
        finally:
            if fd:
                _release_file_lock(fd)

    def get_plans(self) -> List[Dict]:
        plans_data = _load_yaml(PLANS_FILE)
        return [p for p in plans_data.get('plans', []) if p.get('enabled', True)]

    def get_plan(self, plan_id: str) -> Optional[Dict]:
        plans_data = _load_yaml(PLANS_FILE)
        for p in plans_data.get('plans', []):
            if p['id'] == plan_id and p.get('enabled', True):
                return p
        return None
