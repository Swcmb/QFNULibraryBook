import logging
import os
import sys

PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, PROJECT_ROOT)

from datetime import datetime

from flask import Blueprint, jsonify, request, session

from src.user.user_manager import UserManager
from src.subscription.code_manager import ActivationCodeManager
from src.subscription.cron_manager import CronManager
from src.notify.admin_notify import notify_activation, notify_rollback_failure

logger = logging.getLogger(__name__)

def _csrf_guard():
    """CSRF 防护：检查 AJAX 头"""
    from flask import jsonify, request
    if request.headers.get("X-Requested-With") != "XMLHttpRequest":
        return (
            jsonify({"success": False, "error": "CSRF 拒绝", "error_code": "CSRF_REJECTED"}),
            403,
        )
    return None



plans_bp = Blueprint('plans', __name__, url_prefix='/plans')

user_mgr = UserManager()
code_mgr = ActivationCodeManager()
cron_mgr = CronManager()

@plans_bp.route('/api/plans')
def api_plans():
    plans = code_mgr.get_plans()
    result = []
    for plan in plans:
        result.append({
            'id': plan['id'],
            'name': plan['name'],
            'description': plan['description'],
            'price': plan['price'],
            'type': plan['type'],
            'duration_days': plan['duration_days'],
            'default_checkin_time': plan.get('default_checkin_time', ''),
            'default_signout_time': plan.get('default_signout_time', ''),
        })
    return jsonify({'success': True, 'plans': result})

@plans_bp.route('/api/activate', methods=['POST'])
def api_activate():
    guard = _csrf_guard()
    if guard:
        return guard
    if 'username' not in session:
        return jsonify({'success': False, 'error': '未登录', 'error_code': 'UNAUTHORIZED'}), 401

    username = session['username']
    data = request.get_json()
    activation_code = data.get('activation_code', '').strip()
    plan_id = data.get('plan_id', '').strip()

    if not activation_code or not plan_id:
        return jsonify({'success': False, 'error': '参数错误', 'error_code': 'BAD_REQUEST'}), 400

    verification = code_mgr.verify_code(activation_code, username)
    if not verification['valid']:
        return jsonify({'success': False, 'error': verification['error'], 'error_code': verification['error_code']}), 400

    code_entry = verification['code_entry']
    if code_entry['plan_id'] != plan_id:
        return jsonify({'success': False, 'error': '激活码与套餐不匹配', 'error_code': 'PLAN_NOT_FOUND'}), 400

    plan = code_mgr.get_plan(plan_id)
    if not plan:
        return jsonify({'success': False, 'error': '套餐不存在', 'error_code': 'PLAN_NOT_FOUND'}), 404

    snapshot = user_mgr.save_subscription_snapshot(username)
    config_path = user_mgr.get_user_config_path(username)

    try:
        success = user_mgr.update_subscription(username, plan['type'], plan['duration_days'])
        if not success:
            return jsonify({'success': False, 'error': '更新用户配置失败', 'error_code': 'INTERNAL_ERROR'}), 500

        checkin_success = True
        signout_success = True

        if plan['type'] in ('checkin', 'combo'):
            checkin_time = plan.get('default_checkin_time', '08:01')
            checkin_success = cron_mgr.add_user_checkin_task(username, config_path, checkin_time)

        if plan['type'] in ('signout', 'combo') and checkin_success:
            signout_time = plan.get('default_signout_time', '21:01')
            signout_success = cron_mgr.add_user_signout_task(username, config_path, signout_time)

        if not checkin_success or not signout_success:
            logger.error(f'用户 {username} 定时任务配置失败，开始回滚')
            user_mgr.restore_subscription_snapshot(username, snapshot)
            if plan['type'] in ('checkin', 'combo'):
                cron_mgr.remove_user_task(username, 'checkin')
            if plan['type'] in ('signout', 'combo'):
                cron_mgr.remove_user_task(username, 'signout')
            return jsonify({'success': False, 'error': '定时任务配置失败', 'error_code': 'INTERNAL_ERROR'}), 500

        code_mgr.activate_code(activation_code, username)

        sub_info = user_mgr.get_subscription_info(username)
        notify_activation(username, plan['name'], sub_info['expires_at'], activation_code)

        return jsonify({
            'success': True,
            'message': '订阅已激活成功',
            'plan_type': plan['type'],
            'expires_at': sub_info['expires_at'],
            'checkin_time': plan.get('default_checkin_time', ''),
            'signout_time': plan.get('default_signout_time', ''),
        })

    except Exception as e:
        logger.error(f'用户 {username} 激活过程异常: {e}')
        user_mgr.restore_subscription_snapshot(username, snapshot)
        cron_mgr.remove_user_tasks(username)
        notify_rollback_failure(username, '激活过程异常', str(e), activation_code)
        return jsonify({'success': False, 'error': '激活过程异常', 'error_code': 'INTERNAL_ERROR'}), 500

@plans_bp.route('/api/status')
def api_status():
    if 'username' not in session:
        return jsonify({'success': False, 'error': '未登录', 'error_code': 'UNAUTHORIZED'}), 401

    username = session['username']
    sub_info = user_mgr.get_subscription_info(username)

    if sub_info:
        return jsonify({'success': True, 'subscription': sub_info})
    else:
        return jsonify({'success': False, 'error': '用户不存在', 'error_code': 'USER_NOT_FOUND'}), 404
