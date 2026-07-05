# QFNULibrary Web 服务 — 全面测试报告

**测试日期**: 2026-07-06  
**测试对象**: 阿里云服务器 `47.104.159.142`  
**架构**: nginx (80) → gunicorn (127.0.0.1:8000, 3 workers) → Flask (Vue 3 SPA 前后端分离版)

---

## 一、线上实时 HTTP 测试结果（20 项）

### 1.1 基础功能

| 编号 | 测试项 | 实际结果 | 状态 |
|:---:|:---|:---|:---:|
| 1 | GET `/` — SPA 首页 | 200, 返回 Vue 3 启动 HTML | ✅ |
| 2 | GET `/assets/index-xxx.js` — JS Bundle | 200, 122KB | ✅ |
| 3 | GET `/assets/index-xxx.css` — CSS Bundle | 200, 21KB | ✅ |
| 4 | GET `/api/status` — 未登录状态 | `{"logged_in": false}`, 200 | ✅ |

### 1.2 登录认证

| 编号 | 测试项 | 实际结果 | 状态 |
|:---:|:---|:---|:---:|
| 5 | POST `/api/login` 空请求体 | 400, `BAD_REQUEST` | ✅ |
| 6 | POST `/api/login` 空学号密码 | 400, `BAD_REQUEST` | ✅ |
| 7 | POST `/api/login` 缺字段 | 400, `BAD_REQUEST` | ✅ |
| 8 | POST `/api/login` 错误密码 (CAS 真实调用) | 401, `LOGIN_FAILED` | ✅ |
| 9 | POST `/api/login` XSS payload | 401, 异常捕获（CAS 连接重置） | ⚠️ |

### 1.3 CSRF 防护

| 编号 | 测试项 | 实际结果 | 状态 |
|:---:|:---|:---|:---:|
| 10 | 无 `X-Requested-With` 头的 POST | 403, `CSRF_REJECTED` | ✅ |
| 11 | 有正确头的 POST | 正常通过 CSRF 检查 | ✅ |
| 12 | GET `/api/login` (方法不允许) | 405 Method Not Allowed | ✅ |
| 13 | OPTIONS 预检请求 | 200 | ✅ |

### 1.4 签到/签退

| 编号 | 测试项 | 实际结果 | 状态 |
|:---:|:---|:---|:---:|
| 14 | POST `/api/checkin` 未登录 | 401, `UNAUTHORIZED` | ✅ |
| 15 | POST `/api/signout` 未登录 | 401, `UNAUTHORIZED` | ✅ |
| 16 | 10 并发签到请求 | 全部 401（正确，无 session cookie） | ✅ |

### 1.5 管理面板 (新增)

| 编号 | 测试项 | 实际结果 | 状态 |
|:---:|:---|:---|:---:|
| 17 | POST `/admin/api/auth` 空密码 | 401, `密码错误` | ✅ |
| 18 | GET `/admin/api/grab/status` 未登录 | 401, `未登录管理面板` | ✅ |
| 19 | GET `/admin/api/logs` 未登录 | 401, `未登录管理面板` | ✅ |

### 1.6 订阅计划 (新增)

| 编号 | 测试项 | 实际结果 | 状态 |
|:---:|:---|:---|:---:|
| 20 | GET `/plans/api/plans` | 200, 返回 3 个套餐（签到月卡 ¥9.9/签退月卡 ¥9.9/组合包 ¥16.9） | ✅ |
| 21 | GET `/plans/api/status` 未登录 | 401, `未登录` | ✅ |
| 22 | POST `/plans/api/activate` 未登录 | 401, `未登录` | ✅ |

### 1.7 安全响应头

| 编号 | 测试项 | 实际结果 | 状态 |
|:---:|:---|:---|:---:|
| 23 | `X-Frame-Options` | `DENY` | ✅ |
| 24 | `X-Content-Type-Options` | `nosniff` | ✅ |
| 25 | `X-XSS-Protection` | `1; mode=block` | ✅ |
| 26 | 隐藏文件 `.env` | 403 Forbidden | ✅ |
| 27 | `venv/` 目录 | 403 Forbidden | ✅ |
| 28 | SPA 路由回退 `/random-path` | 返回 index.html | ✅ |
| 29 | 不存在的 API `/api/nonexistent` | 404 | ✅ |

---

## 二、单元测试结果（181 个，全部通过）

### 新增 `tests/test_web_app.py` — 33 个测试用例

| 测试类 | 数量 | 覆盖内容 |
|:---|:---:|:---|
| `TestCSRFProtection` | 7 | 4 端点×缺失头→403, 3 端点×正确头→不拒绝 |
| `TestLoginAPI` | 6 | 空体/空字段/成功/失败/异常/trim |
| `TestCheckinAPI` | 4 | 未登录/成功/业务异常/未知异常 |
| `TestSignoutAPI` | 5 | 未登录/成功/无座位/业务异常/未知异常 |
| `TestStatusAPI` | 2 | 已登录/未登录 |
| `TestLogoutAPI` | 2 | 清空session/未登录 |
| `TestIndexPage` | 1 | HTML 响应 |
| `TestHTTPMethodEnforcement` | 5 | 5 端点×错误方法→405 |

### 原有测试 — 148 个，全部通过（无回归）

覆盖：AES 加密、签到/签退、教室映射、配置加载、常量定义、HTTP 重试、滑块验证码、通知推送、Token 管理、JSON 快照。

---

## 三、发现的问题

### 3.1 严重问题：服务器版本与本地代码不一致

服务器运行的是 **前后端分离版**（Vue 3 SPA + Flask API），而本地仓库仍是旧版（Flask 模板渲染）。服务器上有大量新增文件：

| 文件 | 大小 | 说明 |
|:---|:---:|:---|
| `web/app.py` | 6KB | 移除 `render_template`，移除密码明文日志，新增 `UserManager` 自动注册 |
| `web/admin_routes.py` | 23KB | 管理面板：用户 CRUD、抢座管理、日志查看、订阅管理 |
| `web/plans_routes.py` | 5.6KB | 订阅计划：套餐列表、激活码、订阅状态 |
| `frontend/` | — | Vue 3 SPA 完整前端（Vite 构建） |

**建议**: 将服务器代码同步回本地仓库，确保版本一致。

### 3.2 轻微问题：XSS payload 导致 CAS 连接重置

当用户名包含 `<script>` 标签时，CAS 服务器返回 `ConnectionResetError`，Flask 捕获后返回 401 异常信息。虽然不构成安全漏洞（返回的是错误信息而非页面渲染），但建议添加更友好的错误消息。

### 3.3 密码日志差异

- **本地版本**: 记录明文密码到 `/var/log/qfnu-library/credentials.log`
- **服务器版本**: 已移除密码日志（安全改进），仅记录 `username` 和登录结果

---

## 四、服务器状态总结

| 组件 | 状态 | 详情 |
|:---|:---:|:---|
| systemd `qfnu-library` | ✅ | active (running) |
| nginx | ✅ | active, 监听 80 端口 |
| gunicorn | ✅ | 3 个 worker, 监听 127.0.0.1:8000 |
| Flask 应用 | ✅ | 6 个 API 端点 + 管理面板 + 订阅计划 |
| Vue 3 SPA 前端 | ✅ | 122KB JS + 21KB CSS, 路由器回退正常 |
| 安全响应头 | ✅ | X-Frame-Options / X-Content-Type-Options / X-XSS-Protection |
| 敏感文件保护 | ✅ | .env / venv 目录 403 禁止访问 |