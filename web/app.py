"""
QFNU 图书馆座位管理 Web 应用（前后端分离版）
===============================
Flask 后端，仅提供 JSON API。
前端为 Vue 3 SPA，由 Nginx 直接托管静态资源。
"""
import json
import logging
import os
import sys
import threading
import time

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "src"))

from flask import Flask, jsonify, request, session
from flask_session import Session
import requests

from api.exceptions import CheckInFailed, SignOutFailed
from auth.login import qfnu_login
from auth.token import TokenManager
from config.config import AppConfig
from check_in import lib_rsv
from sign_out import go_home

app = Flask(__name__)
app.secret_key = os.environ.get("FLASK_SECRET_KEY", os.urandom(24).hex())
app.config["SESSION_TYPE"] = "filesystem"
Session(app)

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    handlers=[logging.StreamHandler()],
)
logger = logging.getLogger(__name__)

# ---------- 到期自动检查后台线程 ----------

_EXPIRY_CHECK_INTERVAL = 3600  # 每小时检查一次
_EXPIRY_CHECK_LOCK = threading.Lock()
_EXPIRY_CHECK_RUNNING = False
_expiry_thread = None


def _check_expired():
    """在后台线程中定期检查过期订阅"""
    global _EXPIRY_CHECK_RUNNING
    from src.user.user_manager import UserManager
    from src.subscription.cron_manager import CronManager
    from src.notify.admin_notify import notify_expired, notify_expiring_soon

    user_mgr = UserManager()
    cron_mgr = CronManager()

    while _EXPIRY_CHECK_RUNNING:
        try:
            time.sleep(_EXPIRY_CHECK_INTERVAL)
            subscribed = user_mgr.list_subscribed_users()
            for u in subscribed:
                if u.get("status") != "active":
                    continue
                expires_str = u.get("expires_at", "")
                if not expires_str:
                    continue
                try:
                    from datetime import datetime
                    expires = datetime.strptime(expires_str, "%Y-%m-%d")
                    now = datetime.now()
                    if expires < now:
                        user_mgr.update_subscription(u["username"], u.get("plan_type", ""), 0)
                        cron_mgr.remove_user_tasks(u["username"])
                        notify_expired(u["username"])
                        logger.info(f"[到期检查] 用户 {u['username']} 订阅已到期，定时任务已停止")
                    elif (expires - now).days <= 3:
                        notify_expiring_soon(u["username"], (expires - now).days)
                        logger.info(f"[到期检查] 用户 {u['username']} 订阅即将到期，剩余 {(expires - now).days} 天")
                except ValueError:
                    continue
        except Exception as e:
            logger.error(f"[到期检查] 后台线程异常: {e}")


def _start_expiry_checker():
    """启动到期检查后台线程（幂等）"""
    global _expiry_thread, _EXPIRY_CHECK_RUNNING
    with _EXPIRY_CHECK_LOCK:
        if _EXPIRY_CHECK_RUNNING:
            return
        _EXPIRY_CHECK_RUNNING = True
        _expiry_thread = threading.Thread(target=_check_expired, daemon=True)
        _expiry_thread.start()
        logger.info("[到期检查] 后台线程已启动")


def _stop_expiry_checker():
    global _EXPIRY_CHECK_RUNNING
    with _EXPIRY_CHECK_LOCK:
        _EXPIRY_CHECK_RUNNING = False
    logger.info("[到期检查] 后台线程已停止")


def _csrf_guard():
    """检查 POST 请求是否来自 AJAX（防 CSRF）"""
    if request.headers.get("X-Requested-With") != "XMLHttpRequest":
        return jsonify({"success": False, "error": "CSRF 拒绝", "error_code": "CSRF_REJECTED"}), 403
    return None


def get_auth_context():
    """从 session 重建凭证上下文（每次请求调用）"""
    u = session.get("username")
    p = session.get("password")
    if not u or not p:
        return None, None
    cfg = AppConfig(username=u, password=p, push_method="")
    return cfg, TokenManager(u, p)


# ---------- API ----------

@app.route("/api/login", methods=["POST"])
def api_login():
    guard = _csrf_guard()
    if guard:
        return guard

    data = request.get_json(silent=True)
    if not data:
        return jsonify({"success": False, "error": "请求体为空", "error_code": "BAD_REQUEST"}), 400

    username = data.get("username", "").strip()
    password = data.get("password", "")

    if not username or not password:
        return jsonify({"success": False, "error": "学号和密码不能为空", "error_code": "BAD_REQUEST"}), 400

    # 安全审计日志：只记录学号与登录结果，绝不记录明文密码
    logger.info(f"登录尝试 username={username}")

    try:
        name, token = qfnu_login(username, password)
        if not token:
            logger.warning(f"登录失败 username={username}")
            return jsonify({"success": False, "error": "登录失败，请检查账号密码", "error_code": "LOGIN_FAILED"}), 401

        session["username"] = username
        session["password"] = password

        try:
            from src.user.user_manager import UserManager
            user_mgr = UserManager()
            user_mgr.register_user(username, password)
            logger.info(f"用户 {username} 自动注册成功")
        except Exception as e:
            logger.warning(f"用户 {username} 自动注册失败: {e}")

        logger.info(f"用户 {username} ({name}) 登录成功")
        return jsonify({"success": True, "name": name})
    except Exception as e:
        logger.error(f"登录异常 username={username}: {e}")
        return jsonify({"success": False, "error": f"登录异常: {e}", "error_code": "LOGIN_FAILED"}), 401


@app.route("/api/checkin", methods=["POST"])
def api_checkin():
    guard = _csrf_guard()
    if guard:
        return guard

    cfg, token_mgr = get_auth_context()
    if not cfg:
        return jsonify({"success": False, "error": "未登录", "error_code": "UNAUTHORIZED"}), 401

    try:
        lib_rsv(cfg, token_mgr)
        logger.info(f"[{cfg.username}] 签到成功")
        return jsonify({"success": True, "message": "签到成功"})
    except (CheckInFailed, SignOutFailed, requests.RequestException, json.JSONDecodeError) as e:
        logger.error(f"[{cfg.username}] 签到失败: {e}")
        return jsonify({"success": False, "error": f"签到失败: {e}", "error_code": "CHECKIN_FAILED"}), 502
    except Exception as e:
        logger.error(f"[{cfg.username}] 签到异常: {e}")
        return jsonify({"success": False, "error": f"签到异常: {e}", "error_code": "CHECKIN_FAILED"}), 500


@app.route("/api/signout", methods=["POST"])
def api_signout():
    guard = _csrf_guard()
    if guard:
        return guard

    cfg, token_mgr = get_auth_context()
    if not cfg:
        return jsonify({"success": False, "error": "未登录", "error_code": "UNAUTHORIZED"}), 401

    try:
        result = go_home(cfg, token_mgr)
        if result:
            logger.info(f"[{cfg.username}] 签退成功")
            return jsonify({"success": True, "message": "签退成功"})
        else:
            logger.warning(f"[{cfg.username}] 签退失败")
            return jsonify({"success": False, "error": "签退失败：没有正在使用的座位", "error_code": "SIGNOUT_FAILED"}), 502
    except (CheckInFailed, SignOutFailed, requests.RequestException, json.JSONDecodeError) as e:
        logger.error(f"[{cfg.username}] 签退失败: {e}")
        return jsonify({"success": False, "error": f"签退失败: {e}", "error_code": "SIGNOUT_FAILED"}), 502
    except Exception as e:
        logger.error(f"[{cfg.username}] 签退异常: {e}")
        return jsonify({"success": False, "error": f"签退异常: {e}", "error_code": "SIGNOUT_FAILED"}), 500


@app.route("/api/status")
def api_status():
    u = session.get("username")
    if u:
        sub_info = None
        try:
            from src.user.user_manager import UserManager
            user_mgr = UserManager()
            sub_info = user_mgr.get_subscription_info(u)
        except Exception:
            pass
        return jsonify({"logged_in": True, "username": u, "subscription": sub_info})
    return jsonify({"logged_in": False})


@app.route("/api/logout", methods=["POST"])
def api_logout():
    guard = _csrf_guard()
    if guard:
        return guard
    session.clear()
    return jsonify({"success": True})


# ---------- 注册蓝图 ----------
from admin_routes import admin_bp  # noqa: E402
from plans_routes import plans_bp  # noqa: E402

app.register_blueprint(admin_bp)
app.register_blueprint(plans_bp)


if __name__ == "__main__":
    _start_expiry_checker()
    app.run(host="0.0.0.0", port=5000, debug=True)
