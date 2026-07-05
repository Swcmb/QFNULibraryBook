"""
管理面板路由 — Blueprint 模式组织 /admin 相关 API

提供：
- 密码登录认证（session 标记 admin_authed）
- 账号配置 CRUD（修改 users.yml + 各 studentN.yml）
- 抢座顺序管理（admin.yml 的 GRAB_ORDER）
- 手动触发抢座（后台线程顺序执行）
- 日志查看
"""
import os
import sys
import tempfile
import threading
import time
import logging
from datetime import datetime
from typing import Any, Dict, List, Optional

import yaml
from flask import (
    Blueprint,
    jsonify,
    request,
    session,
)

# 固化 src/ 目录到 sys.path，便于复用项目内的核心模块
sys.path.insert(
    0,
    os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "src"),
)

from config.config import AppConfig  # noqa: E402
from auth.token import TokenManager  # noqa: E402

admin_bp = Blueprint("admin", __name__, url_prefix="/admin")
admin_logger = logging.getLogger("admin")

# 路径常量（一次解析，避免反复拼接）
_PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
_CONFIGS_DIR = os.path.join(_PROJECT_ROOT, "configs")
_USERS_INDEX = os.path.join(_CONFIGS_DIR, "users.yml")
_ADMIN_CFG = os.path.join(_CONFIGS_DIR, "admin.yml")
_LOG_DIR = "/var/log/qfnu-library"
_GRAB_LOG = os.path.join(_LOG_DIR, "grab.log")

# 抢座运行时状态（单进程内共享）
_grab_lock = threading.Lock()
_grab_state: Dict[str, Any] = {
    "running": False,
    "started_at": None,
    "finished_at": None,
    "results": [],
}


# ---------- 工具函数 ----------

def _csrf_guard():
    """CSRF 防护：检查 AJAX 头"""
    if request.headers.get("X-Requested-With") != "XMLHttpRequest":
        return (
            jsonify({"success": False, "error": "CSRF 拒绝", "error_code": "CSRF_REJECTED"}),
            403,
        )
    return None


def _require_admin():
    """检查管理员登录状态，未登录返回错误响应"""
    if not session.get("admin_authed"):
        return (
            jsonify({"success": False, "error": "未登录管理面板", "error_code": "UNAUTHORIZED"}),
            401,
        )
    return None


def _atomic_write_yaml(path: str, data: Dict[str, Any]) -> None:
    """原子写入 YAML 文件，避免 cron 读取到部分写入的内容"""
    os.makedirs(os.path.dirname(path), exist_ok=True)
    fd, tmp_path = tempfile.mkstemp(dir=os.path.dirname(path), suffix=".tmp")
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as f:
            yaml.safe_dump(data, f, allow_unicode=True, sort_keys=False)
        os.replace(tmp_path, path)
    except Exception:
        if os.path.exists(tmp_path):
            os.remove(tmp_path)
        raise


def _load_yaml(path: str) -> Dict[str, Any]:
    """加载 YAML 文件，文件不存在时返回空字典"""
    if not os.path.exists(path):
        return {}
    with open(path, "r", encoding="utf-8") as f:
        return yaml.safe_load(f) or {}


def _load_admin_cfg() -> Dict[str, Any]:
    """加载管理面板配置，补全默认字段"""
    cfg = _load_yaml(_ADMIN_CFG)
    cfg.setdefault("ADMIN_PASSWORD", "")
    cfg.setdefault("GRAB_ORDER", [])
    return cfg


def _load_users_index() -> List[Dict[str, str]]:
    """加载用户索引列表"""
    raw = _load_yaml(_USERS_INDEX)
    return raw.get("users", []) if isinstance(raw, dict) else []


def _user_config_path(config_filename: str) -> str:
    """根据 configs/users.yml 中的 config 字段返回绝对路径"""
    if os.path.isabs(config_filename):
        return config_filename
    return os.path.join(_CONFIGS_DIR, config_filename)


def _serialize_user(cfg_data: Dict[str, Any]) -> Dict[str, Any]:
    """将原始 YAML 字段转换为前端可用的 JSON 结构"""
    return {
        "username": cfg_data.get("USERNAME", ""),
        "password": cfg_data.get("PASSWORD", ""),
        "mode": str(cfg_data.get("MODE", "")),
        "seat_id": cfg_data.get("SEAT_ID", []) or [],
        "classrooms_name": cfg_data.get("CLASSROOMS_NAME", []) or [],
        "date": cfg_data.get("DATE", "today"),
        "push_method": cfg_data.get("PUSH_METHOD", ""),
        "dd_bot_token": cfg_data.get("DD_BOT_TOKEN", ""),
        "dd_bot_secret": cfg_data.get("DD_BOT_SECRET", ""),
    }


def _build_user_yaml(
    data: Dict[str, Any], base: Optional[Dict[str, Any]] = None
) -> Dict[str, Any]:
    """根据请求体构造 userN.yml 内容，未提供的字段保留 base 中的值"""
    cfg = dict(base or {})
    if "username" in data:
        cfg["USERNAME"] = str(data["username"])
    if "password" in data:
        cfg["PASSWORD"] = str(data["password"])
    if "mode" in data:
        cfg["MODE"] = str(data["mode"])
    if "seat_id" in data:
        cfg["SEAT_ID"] = data["seat_id"] or []
    if "classrooms_name" in data:
        cfg["CLASSROOMS_NAME"] = data["classrooms_name"] or []
    if "date" in data:
        cfg["DATE"] = str(data["date"])
    if "push_method" in data:
        cfg["PUSH_METHOD"] = str(data["push_method"])
    if "dd_bot_token" in data:
        cfg["DD_BOT_TOKEN"] = str(data["dd_bot_token"])
    if "dd_bot_secret" in data:
        cfg["DD_BOT_SECRET"] = str(data["dd_bot_secret"])
    return cfg


def _next_student_filename() -> Optional[str]:
    """生成下一个可用的 studentX.yml 文件名"""
    for i in range(1, 27):
        candidate = f"student{chr(ord('A') + i - 1)}.yml"
        if not os.path.exists(os.path.join(_CONFIGS_DIR, candidate)):
            return candidate
    return None


# ---------- 页面 ----------



# ---------- 认证 ----------

@admin_bp.route("/api/auth", methods=["POST"])
def admin_auth():
    """管理员密码登录"""
    guard = _csrf_guard()
    if guard:
        return guard

    data = request.get_json(silent=True) or {}
    password = data.get("password", "")
    admin_cfg = _load_admin_cfg()
    expected = admin_cfg.get("ADMIN_PASSWORD", "")

    if not expected:
        admin_logger.error("admin.yml 缺少 ADMIN_PASSWORD")
        return jsonify({"success": False, "error": "管理面板未初始化"}), 500

    if password == expected:
        session["admin_authed"] = True
        session.permanent = True
        admin_logger.info("管理员登录成功")
        return jsonify({"success": True})

    admin_logger.warning("管理员登录失败")
    return (
        jsonify({"success": False, "error": "密码错误", "error_code": "AUTH_FAILED"}),
        401,
    )


@admin_bp.route("/api/logout", methods=["POST"])
def admin_logout():
    """管理员退出"""
    guard = _csrf_guard()
    if guard:
        return guard
    session.pop("admin_authed", None)
    return jsonify({"success": True})


# ---------- 账号管理 ----------

@admin_bp.route("/api/users", methods=["GET"])
def admin_list_users():
    """列出所有账号配置 + 抢座顺序"""
    auth_err = _require_admin()
    if auth_err:
        return auth_err

    users_index = _load_users_index()
    result = []
    for entry in users_index:
        cfg_path = _user_config_path(entry["config"])
        cfg_data = _load_yaml(cfg_path)
        result.append(
            {
                "config_file": entry["config"],
                "name": entry.get("name", ""),
                **_serialize_user(cfg_data),
            }
        )

    admin_cfg = _load_admin_cfg()
    return jsonify(
        {
            "success": True,
            "users": result,
            "grab_order": admin_cfg.get("GRAB_ORDER", []),
        }
    )


@admin_bp.route("/api/users", methods=["POST"])
def admin_add_user():
    """新增账号（生成新 studentN.yml 并加入 users.yml）"""
    auth_err = _require_admin()
    if auth_err:
        return auth_err
    guard = _csrf_guard()
    if guard:
        return guard

    data = request.get_json(silent=True) or {}
    username = (data.get("username") or "").strip()
    if not username:
        return jsonify({"success": False, "error": "学号不能为空"}), 400

    # 学号唯一性检查
    users_index = _load_users_index()
    for entry in users_index:
        cfg_data = _load_yaml(_user_config_path(entry["config"]))
        if cfg_data.get("USERNAME") == username:
            return jsonify({"success": False, "error": "学号已存在"}), 409

    new_filename = _next_student_filename()
    if not new_filename:
        return jsonify({"success": False, "error": "账号数量已达上限"}), 500

    new_cfg = _build_user_yaml(data)
    new_path = os.path.join(_CONFIGS_DIR, new_filename)
    _atomic_write_yaml(new_path, new_cfg)

    # 同步更新 users.yml
    users_data = _load_yaml(_USERS_INDEX)
    users_data.setdefault("users", []).append(
        {"config": new_filename, "name": f"用户 {username}"}
    )
    _atomic_write_yaml(_USERS_INDEX, users_data)

    # 默认追加到抢座顺序末尾
    admin_cfg = _load_admin_cfg()
    admin_cfg.setdefault("GRAB_ORDER", [])
    if username not in admin_cfg["GRAB_ORDER"]:
        admin_cfg["GRAB_ORDER"].append(username)
    _atomic_write_yaml(_ADMIN_CFG, admin_cfg)

    admin_logger.info(f"新增账号 {username} (配置文件 {new_filename})")
    return jsonify({"success": True, "config_file": new_filename})


@admin_bp.route("/api/users/<username>", methods=["PUT"])
def admin_update_user(username: str):
    """修改账号配置（支持学号变更，会同步更新 users.yml 与 admin.yml 的 GRAB_ORDER）"""
    auth_err = _require_admin()
    if auth_err:
        return auth_err
    guard = _csrf_guard()
    if guard:
        return guard

    data = request.get_json(silent=True) or {}
    users_index = _load_users_index()

    # 定位目标账号的配置文件路径
    target_path = None
    for entry in users_index:
        cfg_path = _user_config_path(entry["config"])
        cfg_data = _load_yaml(cfg_path)
        if cfg_data.get("USERNAME") == username:
            target_path = cfg_path
            break

    if not target_path:
        return jsonify({"success": False, "error": "账号不存在"}), 404

    # 学号变更：校验新学号未被其他账号占用
    new_username = (data.get("username") or "").strip()
    if new_username and new_username != username:
        for entry in users_index:
            cfg_path = _user_config_path(entry["config"])
            if cfg_path == target_path:
                continue
            other_data = _load_yaml(cfg_path)
            if other_data.get("USERNAME") == new_username:
                return (
                    jsonify({"success": False, "error": "新学号已被其他账号占用"}),
                    409,
                )

    existing = _load_yaml(target_path)
    new_data = _build_user_yaml(data, base=existing)
    _atomic_write_yaml(target_path, new_data)

    # 学号变更时同步更新 users.yml 的 name 字段与 admin.yml 的 GRAB_ORDER
    if new_username and new_username != username:
        users_data = _load_yaml(_USERS_INDEX)
        for entry in users_data.get("users", []):
            cfg_path = _user_config_path(entry["config"])
            if cfg_path == target_path:
                entry["name"] = f"用户 {new_username}"
                break
        _atomic_write_yaml(_USERS_INDEX, users_data)

        admin_cfg = _load_admin_cfg()
        order = admin_cfg.get("GRAB_ORDER", [])
        if username in order:
            admin_cfg["GRAB_ORDER"] = [
                new_username if u == username else u for u in order
            ]
            _atomic_write_yaml(_ADMIN_CFG, admin_cfg)

        admin_logger.info(f"账号 {username} → {new_username}（学号已变更）")
    else:
        admin_logger.info(f"更新账号 {username} 配置")

    return jsonify({"success": True})


@admin_bp.route("/api/users/<username>", methods=["DELETE"])
def admin_delete_user(username: str):
    """删除账号"""
    auth_err = _require_admin()
    if auth_err:
        return auth_err
    guard = _csrf_guard()
    if guard:
        return guard

    users_data = _load_yaml(_USERS_INDEX)
    users_index = users_data.get("users", [])
    new_index = []
    deleted_file = None
    for entry in users_index:
        cfg_path = _user_config_path(entry["config"])
        cfg_data = _load_yaml(cfg_path)
        if cfg_data.get("USERNAME") == username:
            deleted_file = cfg_path
        else:
            new_index.append(entry)

    if deleted_file is None:
        return jsonify({"success": False, "error": "账号不存在"}), 404

    users_data["users"] = new_index
    _atomic_write_yaml(_USERS_INDEX, users_data)

    if os.path.exists(deleted_file):
        os.remove(deleted_file)

    # 从抢座顺序中移除
    admin_cfg = _load_admin_cfg()
    if username in admin_cfg.get("GRAB_ORDER", []):
        admin_cfg["GRAB_ORDER"] = [
            u for u in admin_cfg["GRAB_ORDER"] if u != username
        ]
        _atomic_write_yaml(_ADMIN_CFG, admin_cfg)

    admin_logger.info(f"删除账号 {username}")
    return jsonify({"success": True})


@admin_bp.route("/api/users/order", methods=["PUT"])
def admin_update_order():
    """修改抢座顺序"""
    auth_err = _require_admin()
    if auth_err:
        return auth_err
    guard = _csrf_guard()
    if guard:
        return guard

    data = request.get_json(silent=True) or {}
    new_order = data.get("grab_order", [])
    if not isinstance(new_order, list):
        return jsonify({"success": False, "error": "grab_order 必须是列表"}), 400

    admin_cfg = _load_admin_cfg()
    admin_cfg["GRAB_ORDER"] = [str(u) for u in new_order]
    _atomic_write_yaml(_ADMIN_CFG, admin_cfg)

    admin_logger.info(f"更新抢座顺序: {new_order}")
    return jsonify({"success": True})


# ---------- 抢座 ----------

@admin_bp.route("/api/grab", methods=["POST"])
def admin_trigger_grab():
    """手动触发顺序抢座（后台线程）"""
    auth_err = _require_admin()
    if auth_err:
        return auth_err
    guard = _csrf_guard()
    if guard:
        return guard

    with _grab_lock:
        if _grab_state["running"]:
            return jsonify({"success": False, "error": "抢座任务正在运行"}), 409
        _grab_state.update(
            {
                "running": True,
                "started_at": datetime.now().isoformat(),
                "finished_at": None,
                "results": [],
            }
        )

    thread = threading.Thread(target=_run_grab_sequential, daemon=True)
    thread.start()
    return jsonify({"success": True, "message": "抢座任务已启动"})


def _run_grab_sequential() -> None:
    """顺序执行抢座（在线程中运行，单账号失败不影响后续）"""
    from get_seat import run_seat_reservation

    admin_cfg = _load_admin_cfg()
    order = admin_cfg.get("GRAB_ORDER", [])
    users_index = _load_users_index()

    # 学号 → 配置文件路径
    username_to_path: Dict[str, str] = {}
    for entry in users_index:
        cfg_path = _user_config_path(entry["config"])
        cfg_data = _load_yaml(cfg_path)
        u = cfg_data.get("USERNAME")
        if u:
            username_to_path[u] = cfg_path

    results: List[Dict[str, Any]] = []
    for username in order:
        cfg_path = username_to_path.get(username)
        if not cfg_path:
            results.append(
                {"username": username, "success": False, "error": "配置文件缺失"}
            )
            continue

        try:
            cfg = AppConfig.from_yaml(cfg_path)
            if not cfg.username or not cfg.password:
                results.append(
                    {
                        "username": username,
                        "success": False,
                        "error": "用户名或密码为空",
                    }
                )
                continue

            token_mgr = TokenManager(cfg.username, cfg.password)
            run_seat_reservation(cfg, token_mgr)
            results.append({"username": username, "success": True, "error": ""})
            admin_logger.info(f"[{username}] 抢座成功")
        except Exception as e:
            results.append({"username": username, "success": False, "error": str(e)})
            admin_logger.error(f"[{username}] 抢座失败: {e}")

        time.sleep(5)  # 防止接口风控

    with _grab_lock:
        _grab_state["running"] = False
        _grab_state["finished_at"] = datetime.now().isoformat()
        _grab_state["results"] = results


@admin_bp.route("/api/grab/status", methods=["GET"])
def admin_grab_status():
    """获取抢座任务状态"""
    auth_err = _require_admin()
    if auth_err:
        return auth_err

    with _grab_lock:
        state = dict(_grab_state)
    return jsonify({"success": True, "state": state})


# ---------- 日志 ----------

@admin_bp.route("/api/logs", methods=["GET"])
def admin_logs():
    """获取最近日志（默认 100 行，最多 1000 行）"""
    auth_err = _require_admin()
    if auth_err:
        return auth_err

    lines_limit = request.args.get("lines", 100, type=int)
    lines_limit = max(1, min(lines_limit, 1000))

    if not os.path.exists(_GRAB_LOG):
        return jsonify({"success": True, "logs": ""})

    try:
        with open(_GRAB_LOG, "r", encoding="utf-8", errors="replace") as f:
            lines = f.readlines()[-lines_limit:]
        return jsonify({"success": True, "logs": "".join(lines)})
    except Exception as e:
        return jsonify({"success": False, "error": str(e)}), 500


# ---------- 订阅管理 ----------

@admin_bp.route('/api/subscriptions/codes', methods=['POST'])
def admin_generate_codes():
    """生成激活码"""
    auth_err = _require_admin()
    if auth_err:
        return auth_err
    guard = _csrf_guard()
    if guard:
        return guard

    data = request.get_json(silent=True) or {}
    plan_id = data.get('plan_id', '').strip()
    count = data.get('count', 1)
    bound_username = data.get('bound_username', '').strip()

    if not plan_id:
        return jsonify({'success': False, 'error': '套餐ID不能为空'}), 400

    if not isinstance(count, int) or count < 1 or count > 100:
        return jsonify({'success': False, 'error': '生成数量必须在1-100之间'}), 400

    try:
        from src.subscription.code_manager import ActivationCodeManager
        code_mgr = ActivationCodeManager()
        codes = code_mgr.generate_codes(plan_id, count, bound_username)

        result = []
        for c in codes:
            result.append({
                'code': c['code'],
                'plan_id': c['plan_id'],
                'plan_type': c['plan_type'],
                'expires_at': c['expires_at'],
            })

        admin_logger.info(f'管理员生成 {count} 个激活码，套餐: {plan_id}')
        return jsonify({'success': True, 'codes': result})
    except Exception as e:
        admin_logger.error(f'生成激活码失败: {e}')
        return jsonify({'success': False, 'error': str(e)}), 500


@admin_bp.route('/api/subscriptions/codes', methods=['GET'])
def admin_list_codes():
    """激活码列表"""
    auth_err = _require_admin()
    if auth_err:
        return auth_err

    status = request.args.get('status', '')
    page = request.args.get('page', 1, type=int)
    page_size = request.args.get('page_size', 20, type=int)

    try:
        from src.subscription.code_manager import ActivationCodeManager
        code_mgr = ActivationCodeManager()
        all_codes = code_mgr.list_codes(status=status if status else None)

        total = len(all_codes)
        start = (page - 1) * page_size
        end = start + page_size
        codes = all_codes[start:end]

        return jsonify({
            'success': True,
            'codes': codes,
            'total': total,
            'page': page,
            'page_size': page_size,
        })
    except Exception as e:
        admin_logger.error(f'获取激活码列表失败: {e}')
        return jsonify({'success': False, 'error': str(e)}), 500


@admin_bp.route('/api/subscriptions/codes/<code>/revoke', methods=['POST'])
def admin_revoke_code(code):
    """作废激活码"""
    auth_err = _require_admin()
    if auth_err:
        return auth_err
    guard = _csrf_guard()
    if guard:
        return guard

    try:
        from src.subscription.code_manager import ActivationCodeManager
        code_mgr = ActivationCodeManager()
        success = code_mgr.revoke_code(code)

        if success:
            admin_logger.info(f'管理员作废激活码: {code}')
            return jsonify({'success': True, 'message': '激活码已作废'})
        else:
            return jsonify({'success': False, 'error': '作废失败，激活码不存在或已使用'}), 400
    except Exception as e:
        admin_logger.error(f'作废激活码失败: {e}')
        return jsonify({'success': False, 'error': str(e)}), 500


@admin_bp.route('/api/subscriptions/users', methods=['GET'])
def admin_list_subscribed_users():
    """订阅用户列表"""
    auth_err = _require_admin()
    if auth_err:
        return auth_err

    try:
        from src.user.user_manager import UserManager
        user_mgr = UserManager()
        users = user_mgr.list_subscribed_users()

        return jsonify({'success': True, 'users': users, 'total': len(users)})
    except Exception as e:
        admin_logger.error(f'获取订阅用户列表失败: {e}')
        return jsonify({'success': False, 'error': str(e)}), 500


@admin_bp.route('/api/subscriptions/stats', methods=['GET'])
def admin_subscription_stats():
    """订阅统计"""
    auth_err = _require_admin()
    if auth_err:
        return auth_err

    try:
        from src.subscription.code_manager import ActivationCodeManager
        from src.user.user_manager import UserManager

        code_mgr = ActivationCodeManager()
        user_mgr = UserManager()

        codes = code_mgr.list_codes()
        users = user_mgr.list_subscribed_users()

        plan_stats = {}
        total_revenue = 0.0

        for c in codes:
            if c['status'] == 'active':
                plan_id = c['plan_id']
                plan_stats[plan_id] = plan_stats.get(plan_id, 0) + 1
                total_revenue += c['price']

        return jsonify({
            'success': True,
            'stats': {
                'total_subscribers': len(users),
                'active_subscribers': len(users),
                'plan_stats': plan_stats,
                'total_revenue': round(total_revenue, 2),
            },
        })
    except Exception as e:
        admin_logger.error(f'获取订阅统计失败: {e}')
        return jsonify({'success': False, 'error': str(e)}), 500


@admin_bp.route('/api/subscriptions/plans', methods=['GET'])
def admin_list_plans():
    """获取套餐列表"""
    auth_err = _require_admin()
    if auth_err:
        return auth_err

    try:
        from src.subscription.code_manager import ActivationCodeManager
        code_mgr = ActivationCodeManager()
        plans = code_mgr.get_plans()

        return jsonify({'success': True, 'plans': plans})
    except Exception as e:
        admin_logger.error(f'获取套餐列表失败: {e}')
        return jsonify({'success': False, 'error': str(e)}), 500


@admin_bp.route('/api/subscriptions/activations', methods=['GET'])
def admin_activation_logs():
    """查看最近激活记录"""
    auth_err = _require_admin()
    if auth_err:
        return auth_err

    try:
        from src.notify.admin_notify import get_recent_activations
        limit = request.args.get('limit', 50, type=int)
        records = get_recent_activations(limit)
        return jsonify({'success': True, 'records': records, 'total': len(records)})
    except Exception as e:
        admin_logger.error(f'获取激活记录失败: {e}')
        return jsonify({'success': False, 'error': str(e)}), 500
