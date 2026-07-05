"""
QFNU 图书馆座位管理 Web 应用 — 全面测试用例
============================================
覆盖: CSRF 防护 / 登录 / 签到 / 签退 / 状态 / 注销 / 错误处理

所有网络调用通过 unittest.mock 隔离，不产生真实 HTTP 请求。
"""
import json
import os
import sys
import tempfile
from unittest.mock import MagicMock, patch

import pytest

# ─── 清理 sys.path 中干扰导入的路径 ──────────────────────────
for _p in list(sys.path):
    if "DocReview" in _p or "Agent" in _p:
        sys.path.remove(_p)

# ─── 确保 Flask-Session 文件系统存储目录存在 ────────────────────
_session_dir = os.path.join(os.getcwd(), "flask_session")
os.makedirs(_session_dir, exist_ok=True)

# ─── Mock 平台相关模块和 cv2（导入时可能触发兼容性问题） ──────────
CV2_MOCK = MagicMock()
CV2_MOCK.dnn = MagicMock()
# cv2.typing 在 cv2 包内，需要在导入 cv2 后再 mock
sys.modules["fcntl"] = MagicMock()
sys.modules["cv2"] = CV2_MOCK
sys.modules["cv2.dnn"] = MagicMock()
sys.modules["cv2.typing"] = MagicMock()
sys.modules["cv2.data"] = MagicMock()

from web import app as web_app


# Flask test client
@pytest.fixture
def client():
    web_app.app.config["TESTING"] = True
    web_app.app.config["SECRET_KEY"] = "test-secret-key"
    web_app.app.secret_key = "test-secret-key"
    with web_app.app.test_client() as c:
        with web_app.app.app_context():
            yield c


# ═══════════════════════════════════════════════════════════════════
# 1. CSRF 防护
# ═══════════════════════════════════════════════════════════════════

class TestCSRFProtection:
    """所有 POST API 必须检查 X-Requested-With 头"""

    @pytest.mark.parametrize("endpoint,method", [
        ("/api/login", "POST"),
        ("/api/checkin", "POST"),
        ("/api/signout", "POST"),
        ("/api/logout", "POST"),
    ])
    def test_missing_csrf_header_returns_403(self, client, endpoint, method):
        """缺少 X-Requested-With 头的 POST 请求应返回 403"""
        resp = client.open(endpoint, method=method,
                          content_type="application/json",
                          data=json.dumps({"username": "test", "password": "p"}))
        assert resp.status_code == 403
        data = resp.get_json()
        assert data["success"] is False
        assert data["error_code"] == "CSRF_REJECTED"

    @pytest.mark.parametrize("endpoint", ["/api/checkin", "/api/signout", "/api/logout"])
    def test_csrf_header_present_allows_request(self, client, endpoint):
        """有正确头的请求不会因为 CSRF 被拒绝"""
        resp = client.post(endpoint,
                           headers={"X-Requested-With": "XMLHttpRequest"})
        # 即使后续因为未登录返回 401，也不应该是 CSRF 拒绝
        assert resp.status_code != 403
        data = resp.get_json()
        assert data.get("error_code") != "CSRF_REJECTED"


# ═══════════════════════════════════════════════════════════════════
# 2. 登录 API
# ═══════════════════════════════════════════════════════════════════

class TestLoginAPI:
    """POST /api/login — CAS 认证登录"""

    def test_empty_request_body(self, client):
        """空请求体返回 400"""
        resp = client.post("/api/login",
                           headers={"X-Requested-With": "XMLHttpRequest"},
                           content_type="application/json",
                           data="")
        assert resp.status_code == 400
        assert resp.get_json()["error_code"] == "BAD_REQUEST"

    def test_missing_fields(self, client):
        """缺失 username/password 字段返回 400"""
        resp = client.post("/api/login",
                           headers={"X-Requested-With": "XMLHttpRequest"},
                           content_type="application/json",
                           data=json.dumps({"username": "test"}))
        assert resp.status_code == 400
        assert resp.get_json()["error_code"] == "BAD_REQUEST"

    def test_empty_username_and_password(self, client):
        """空学号和密码返回 400"""
        resp = client.post("/api/login",
                           headers={"X-Requested-With": "XMLHttpRequest"},
                           content_type="application/json",
                           data=json.dumps({"username": "", "password": ""}))
        assert resp.status_code == 400
        assert resp.get_json()["error_code"] == "BAD_REQUEST"

    @patch("web.app.qfnu_login")
    def test_login_success(self, mock_login, client):
        """正确凭证 → 登录成功，session 保存"""
        mock_login.return_value = ("张三", "bearer_TOKEN")
        resp = client.post("/api/login",
                           headers={"X-Requested-With": "XMLHttpRequest"},
                           content_type="application/json",
                           data=json.dumps({"username": "20240001", "password": "correct"}))
        assert resp.status_code == 200
        data = resp.get_json()
        assert data["success"] is True
        assert data["name"] == "张三"

        # 验证 session 已写入
        with client.session_transaction() as sess:
            assert sess["username"] == "20240001"
            assert sess["password"] == "correct"

    @patch("web.app.qfnu_login")
    def test_login_failure_wrong_password(self, mock_login, client):
        """错误密码 → 返回 401"""
        mock_login.return_value = (None, None)
        resp = client.post("/api/login",
                           headers={"X-Requested-With": "XMLHttpRequest"},
                           content_type="application/json",
                           data=json.dumps({"username": "20240001", "password": "wrong"}))
        assert resp.status_code == 401
        assert resp.get_json()["error_code"] == "LOGIN_FAILED"

    @patch("web.app.qfnu_login")
    def test_login_exception(self, mock_login, client):
        """登录过程抛异常 → 返回 401 并包含异常信息"""
        mock_login.side_effect = ConnectionError("CAS 服务不可用")
        resp = client.post("/api/login",
                           headers={"X-Requested-With": "XMLHttpRequest"},
                           content_type="application/json",
                           data=json.dumps({"username": "20240001", "password": "any"}))
        assert resp.status_code == 401
        data = resp.get_json()
        assert data["error_code"] == "LOGIN_FAILED"
        assert "CAS" in data["error"]

    @patch("web.app.qfnu_login")
    def test_login_username_whitespace_stripped(self, mock_login, client):
        """学号前后空格应被去除"""
        mock_login.return_value = ("李四", "bearer_T")
        resp = client.post("/api/login",
                           headers={"X-Requested-With": "XMLHttpRequest"},
                           content_type="application/json",
                           data=json.dumps({"username": "  20240001  ", "password": "pass"}))
        assert resp.status_code == 200
        # 验证传给 qfnu_login 的 username 已 trim
        mock_login.assert_called_with("20240001", "pass")


# ═══════════════════════════════════════════════════════════════════
# 3. 签到 API
# ═══════════════════════════════════════════════════════════════════

class TestCheckinAPI:
    """POST /api/checkin — 签到"""

    def test_checkin_without_login(self, client):
        """未登录的签到请求返回 401"""
        resp = client.post("/api/checkin",
                           headers={"X-Requested-With": "XMLHttpRequest"})
        assert resp.status_code == 401
        assert resp.get_json()["error_code"] == "UNAUTHORIZED"

    @patch("web.app.lib_rsv")
    def test_checkin_success(self, mock_lib_rsv, client):
        """已登录的签到请求 → 200 成功"""
        # 先登录
        with client.session_transaction() as sess:
            sess["username"] = "20240001"
            sess["password"] = "pass"

        mock_lib_rsv.return_value = None
        resp = client.post("/api/checkin",
                           headers={"X-Requested-With": "XMLHttpRequest"})
        assert resp.status_code == 200
        assert resp.get_json()["success"] is True
        assert resp.get_json()["message"] == "签到成功"

    @patch("web.app.lib_rsv")
    def test_checkin_api_exception(self, mock_lib_rsv, client):
        """签到模块抛异常 → 502"""
        with client.session_transaction() as sess:
            sess["username"] = "20240001"
            sess["password"] = "pass"

        from api.exceptions import CheckInFailed
        mock_lib_rsv.side_effect = CheckInFailed("座位已被占用")
        resp = client.post("/api/checkin",
                           headers={"X-Requested-With": "XMLHttpRequest"})
        assert resp.status_code == 502
        assert resp.get_json()["error_code"] == "CHECKIN_FAILED"

    @patch("web.app.lib_rsv")
    def test_checkin_generic_exception(self, mock_lib_rsv, client):
        """签到模块抛未知异常 → 500"""
        with client.session_transaction() as sess:
            sess["username"] = "20240001"
            sess["password"] = "pass"

        mock_lib_rsv.side_effect = RuntimeError("未知错误")
        resp = client.post("/api/checkin",
                           headers={"X-Requested-With": "XMLHttpRequest"})
        assert resp.status_code == 500
        assert resp.get_json()["error_code"] == "CHECKIN_FAILED"


# ═══════════════════════════════════════════════════════════════════
# 4. 签退 API
# ═══════════════════════════════════════════════════════════════════

class TestSignoutAPI:
    """POST /api/signout — 签退"""

    def test_signout_without_login(self, client):
        """未登录的签退请求返回 401"""
        resp = client.post("/api/signout",
                           headers={"X-Requested-With": "XMLHttpRequest"})
        assert resp.status_code == 401
        assert resp.get_json()["error_code"] == "UNAUTHORIZED"

    @patch("web.app.go_home")
    def test_signout_success(self, mock_go_home, client):
        """已登录的签退请求 → 200 成功"""
        with client.session_transaction() as sess:
            sess["username"] = "20240001"
            sess["password"] = "pass"

        mock_go_home.return_value = True
        resp = client.post("/api/signout",
                           headers={"X-Requested-With": "XMLHttpRequest"})
        assert resp.status_code == 200
        assert resp.get_json()["success"] is True
        assert resp.get_json()["message"] == "签退成功"

    @patch("web.app.go_home")
    def test_signout_no_active_seat(self, mock_go_home, client):
        """没有正在使用的座位 → 502"""
        with client.session_transaction() as sess:
            sess["username"] = "20240001"
            sess["password"] = "pass"

        mock_go_home.return_value = False
        resp = client.post("/api/signout",
                           headers={"X-Requested-With": "XMLHttpRequest"})
        assert resp.status_code == 502
        assert resp.get_json()["error_code"] == "SIGNOUT_FAILED"

    @patch("web.app.go_home")
    def test_signout_exception(self, mock_go_home, client):
        """签退时抛异常 → 502"""
        with client.session_transaction() as sess:
            sess["username"] = "20240001"
            sess["password"] = "pass"

        from api.exceptions import SignOutFailed
        mock_go_home.side_effect = SignOutFailed("签退失败")
        resp = client.post("/api/signout",
                           headers={"X-Requested-With": "XMLHttpRequest"})
        assert resp.status_code == 502
        assert resp.get_json()["error_code"] == "SIGNOUT_FAILED"

    @patch("web.app.go_home")
    def test_signout_generic_exception(self, mock_go_home, client):
        """签退时抛未知异常 → 500"""
        with client.session_transaction() as sess:
            sess["username"] = "20240001"
            sess["password"] = "pass"

        mock_go_home.side_effect = RuntimeError("未知异常")
        resp = client.post("/api/signout",
                           headers={"X-Requested-With": "XMLHttpRequest"})
        assert resp.status_code == 500
        assert resp.get_json()["error_code"] == "SIGNOUT_FAILED"


# ═══════════════════════════════════════════════════════════════════
# 5. 状态 API
# ═══════════════════════════════════════════════════════════════════

class TestStatusAPI:
    """GET /api/status — 登录状态查询"""

    def test_status_logged_out(self, client):
        """未登录 → logged_in=False"""
        resp = client.get("/api/status")
        assert resp.status_code == 200
        data = resp.get_json()
        assert data["logged_in"] is False

    def test_status_logged_in(self, client):
        """已登录 → logged_in=True + username"""
        with client.session_transaction() as sess:
            sess["username"] = "20240001"
        resp = client.get("/api/status")
        assert resp.status_code == 200
        data = resp.get_json()
        assert data["logged_in"] is True
        assert data["username"] == "20240001"


# ═══════════════════════════════════════════════════════════════════
# 6. 注销 API
# ═══════════════════════════════════════════════════════════════════

class TestLogoutAPI:
    """POST /api/logout — 注销"""

    def test_logout_clears_session(self, client):
        """注销后 session 应被清空"""
        with client.session_transaction() as sess:
            sess["username"] = "20240001"
            sess["password"] = "secret"

        resp = client.post("/api/logout",
                           headers={"X-Requested-With": "XMLHttpRequest"})
        assert resp.status_code == 200
        assert resp.get_json()["success"] is True

        # 验证 session 已清空
        status_resp = client.get("/api/status")
        assert status_resp.get_json()["logged_in"] is False

    def test_logout_without_login(self, client):
        """未登录时注销也应成功返回"""
        resp = client.post("/api/logout",
                           headers={"X-Requested-With": "XMLHttpRequest"})
        assert resp.status_code == 200
        assert resp.get_json()["success"] is True


# ═══════════════════════════════════════════════════════════════════
# 7. 主页面（前后端分离版无 Flask 路由，由 nginx 直接托管 SPA）
# ═══════════════════════════════════════════════════════════════════

class TestIndexPage:
    """GET / — 前后端分离版中 Flask 不提供首页路由"""

    def test_index_returns_404_from_flask(self, client):
        """Flask 不提供 / 路由，应返回 404（由 nginx 托管 SPA）"""
        resp = client.get("/")
        assert resp.status_code == 404


# ═══════════════════════════════════════════════════════════════════
# 8. 错误 HTTP 方法
# ═══════════════════════════════════════════════════════════════════

class TestHTTPMethodEnforcement:
    """不允许的 HTTP 方法应返回 405"""

    @pytest.mark.parametrize("endpoint,allowed", [
        ("/api/login", ["POST", "OPTIONS"]),
        ("/api/checkin", ["POST", "OPTIONS"]),
        ("/api/signout", ["POST", "OPTIONS"]),
        ("/api/status", ["GET", "HEAD", "OPTIONS"]),
        ("/api/logout", ["POST", "OPTIONS"]),
    ])
    def test_disallowed_method_returns_405(self, client, endpoint, allowed):
        """不允许的 HTTP 方法返回 405 Method Not Allowed"""
        test_methods = ["GET", "POST", "PUT", "DELETE", "PATCH"]
        for method in test_methods:
            if method not in allowed and method != "OPTIONS":
                resp = client.open(endpoint, method=method)
                assert resp.status_code == 405, (
                    f"{method} {endpoint} 应返回 405，实际 {resp.status_code}"
                )