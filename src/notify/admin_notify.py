import json
import os
import requests
from datetime import datetime

logger = __import__('logging').getLogger(__name__)

PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
CONFIG_FILE = os.path.join(PROJECT_ROOT, 'configs', 'admin.yml')
NOTIFY_LOG_DIR = os.path.join(PROJECT_ROOT, 'data', 'admin_notify')


def _load_config():
    import yaml
    if os.path.exists(CONFIG_FILE):
        with open(CONFIG_FILE, 'r', encoding='utf-8') as f:
            return yaml.safe_load(f) or {}
    return {}


def _ensure_log_dir():
    os.makedirs(NOTIFY_LOG_DIR, exist_ok=True)


def _log_to_file(filename: str, content: str):
    """将通知内容写入日志文件，供管理面板查看"""
    _ensure_log_dir()
    filepath = os.path.join(NOTIFY_LOG_DIR, filename)
    timestamp = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
    try:
        with open(filepath, 'a', encoding='utf-8') as f:
            f.write(f'[{timestamp}] {content}\n')
    except Exception as e:
        logger.error(f'写入通知日志失败: {e}')


def _send_dingtalk(msg: str):
    config = _load_config()
    bot_token = config.get('DD_BOT_TOKEN', '')
    bot_secret = config.get('DD_BOT_SECRET', '')

    if not bot_token:
        logger.warning('钉钉机器人配置未设置，无法发送通知')
        return False

    try:
        url = f'https://oapi.dingtalk.com/robot/send?access_token={bot_token}'
        headers = {'Content-Type': 'application/json; charset=utf-8'}
        data = {
            'msgtype': 'text',
            'text': {'content': msg}
        }

        if bot_secret:
            from hashlib import sha256
            import time
            timestamp = str(round(time.time() * 1000))
            string_to_sign = f'{timestamp}\n{bot_secret}'
            sign = sha256(string_to_sign.encode()).digest()
            import base64
            sign = base64.b64encode(sign).decode()
            url += f'&timestamp={timestamp}&sign={sign}'

        response = requests.post(url, headers=headers, data=json.dumps(data))
        result = response.json()
        if result.get('errcode') == 0:
            logger.info('钉钉通知发送成功')
            return True
        else:
            logger.error(f'钉钉通知发送失败: {result}')
            return False
    except Exception as e:
        logger.error(f'发送钉钉通知异常: {e}')
        return False


def notify_purchase(username: str, plan_id: str, plan_name: str):
    now_str = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
    msg = f'''【新订阅购买请求】
学号: {username}
套餐: {plan_name} ({plan_id})
时间: {now_str}
请管理员确认收款后生成激活码。'''
    _send_dingtalk(msg.strip())
    _log_to_file('purchase.log', f'用户 {username} 请求购买 {plan_name}（{plan_id}）')


def notify_activation(username: str, plan_name: str, expires_at: str, activation_code: str = ''):
    now_str = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
    msg = f'''【订阅激活成功】
学号: {username}
套餐: {plan_name}
到期时间: {expires_at}
激活码: {activation_code}
时间: {now_str}'''
    _send_dingtalk(msg.strip())
    _log_to_file('activation.log', f'用户 {username} 激活 {plan_name}（激活码: {activation_code}），到期: {expires_at}')


def notify_rollback_failure(username: str, step: str, error: str, activation_code: str = ''):
    now_str = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
    msg = f'''【订阅激活回滚失败】
学号: {username}
激活码: {activation_code}
失败步骤: {step}
错误信息: {error}
时间: {now_str}
请管理员人工介入处理！'''
    _send_dingtalk(msg.strip())
    _log_to_file('rollback.log', f'用户 {username} 回滚失败（激活码: {activation_code}），步骤: {step}，错误: {error}')


def notify_expiring_soon(username: str, days_left: int):
    now_str = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
    msg = f'''【订阅即将到期提醒】
学号: {username}
剩余天数: {days_left}天
时间: {now_str}
请提醒用户续费。'''
    _send_dingtalk(msg.strip())
    _log_to_file('expiry.log', f'用户 {username} 订阅即将到期，剩余 {days_left} 天')


def notify_expired(username: str):
    now_str = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
    msg = f'''【订阅已到期】
学号: {username}
时间: {now_str}
定时任务已自动停止。'''
    _send_dingtalk(msg.strip())
    _log_to_file('expiry.log', f'用户 {username} 订阅已到期，定时任务已停止')


def get_recent_activations(limit: int = 50) -> list:
    """获取最近激活记录，供管理面板查看"""
    _ensure_log_dir()
    log_path = os.path.join(NOTIFY_LOG_DIR, 'activation.log')
    if not os.path.exists(log_path):
        return []

    try:
        with open(log_path, 'r', encoding='utf-8') as f:
            lines = f.readlines()
        lines = [l.strip() for l in lines if l.strip()]
        lines.reverse()
        return lines[:limit]
    except Exception as e:
        logger.error(f'读取激活记录失败: {e}')
        return []