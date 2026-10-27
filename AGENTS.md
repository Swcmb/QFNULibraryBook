# MyQFNULibraryBook — AGENTS.md

## 项目概述

曲阜师范大学图书馆座位自动预约系统。自动化完成 **预约 → 签到 → 签退** 三阶段流程，支持多用户并发、多教室、多渠道通知推送。目标系统为 `http://libyy.qfnu.edu.cn`（图书馆座位预约平台），通过 IDS CAS 统一认证登录。

核心能力：**OpenCV 滑块验证码自动破解** + **AES 动态加密请求体** + **多模式选座策略**。

GitHub: `https://github.com/Swcmb/MyQFNULibraryBook`

---

## 技术栈

| 组件 | 版本 / 用途 |
|------|-------------|
| **Python** | 3.10+ |
| **requests** | HTTP 客户端（带 tenacity 重试） |
| **OpenCV (opencv-python-headless)** | 滑块验证码缺口识别（边缘检测 + 多策略匹配） |
| **PyCryptodome** | AES-CBC 加密（登录密码、预约数据、滑块签名） |
| **Flask + flask-session** | Web 控制面板（浏览器端一键签到/签退） |
| **PyYAML** | 用户配置文件解析（dataclass 绑定） |
| **numpy** | OpenCV 图像处理依赖 |
| **tenacity** | 通知推送重试装饰器 |
| **pytest** | 单元测试框架 |

---

## 目录结构

```
MyQFNULibraryBook/
├── src/                              # 核心源码
│   ├── auth/                         # 登录认证模块
│   │   ├── login.py                  #   CAS 登录 + 滑块验证码破解（核心，~450 行）
│   │   └── token.py                  #   Token 管理器（缓存/过期刷新，线程安全）
│   ├── config/
│   │   └── config.py                 #   AppConfig 数据类（YAML → dataclass）
│   ├── notify/
│   │   └── notify.py                 #   消息推送（钉钉/Telegram/Bark/AnPush，含 tenacity 重试）
│   ├── crypto/
│   │   └── aes.py                    #   AES-CBC 加密（日期回文密钥 + 随机前缀/IV）
│   ├── api/
│   │   ├── constants.py              #   API URL 常量 + 默认请求头
│   │   ├── exceptions.py             #   自定义异常链（RequestFailed / ReservationFailed / ...）
│   │   └── http.py                   #   带重试 + 总超时的 POST 工具
│   ├── classrooms.py                 #   教室名称 → ID 映射 + 无插座座位 EXCLUDE_ID 集合
│   ├── get_seat.py                   #   预约座位（入口文件，四种模式）
│   ├── check_in.py                   #   签到
│   ├── sign_out.py                   #   签退
│   ├── get_info.py                   #   日期/时间段/座位查询工具
│   └── get_seat_info_ForAdmin.py     #   管理员：抓取座位布局 JSON 快照
├── configs/                          # 用户 YAML 配置文件
│   ├── template.yml                  #   配置模板（含所有字段说明）
│   ├── studentA.yml / studentB.yml   #   用户配置示例
│   ├── user1.yml / user2.yml         #   多用户配置
│   └── users.yml                     #   多用户并发入口（run_all.py 使用）
├── data/seat_info/                   # 教室座位布局 JSON 快照（15 个教室）
├── scripts/                          # 辅助脚本
│   ├── run_all.py                    #   多用户并发（ThreadPoolExecutor，支持聚合通知）
│   ├── performance_probe.py          #   API 性能探测（7 项测量，含 AES/TCP/登录/API）
│   └── time_window_test.py           #   19:20 预约窗口敏感性测试（2s 密集采样）
├── web/                              # Flask Web 控制面板
│   ├── app.py                        #   后端 API（登录/签到/签退/状态/登出）
│   ├── requirements.txt              #   Flask + flask-session
│   ├── README.md                     #   部署说明
│   ├── static/logo.png               #   校徽
│   └── templates/index.html          #   前端（登录页 + 控制面板，单页 SPA 风格）
├── tests/                            # pytest 测试套件（16 个测试文件）
│   ├── conftest.py
│   ├── __init__.py
│   ├── fixtures/                     #   7 个配置 fixture（完整/最小/空/各通知渠道）
│   │   ├── config_full.yaml
│   │   ├── config_minimal.yaml
│   │   ├── config_empty.yaml
│   │   ├── config_anpush.yaml
│   │   ├── config_bark.yaml
│   │   ├── config_dd.yaml
│   │   └── config_tg.yaml
│   └── test_*.py                     #   模块级测试（config / login / token / aes / http / ...）
├── assets/                           # 文档截图（教室实景、Web 界面）
├── pytest.ini                        # pytest 配置（testpaths=tests, pythonpath=src）
├── requirements.txt                  # 项目依赖
├── .gitignore                        # 忽略规则
├── LICENSE                           # CC BY-NC 4.0
└── AGENTS.md                         # ← 本文件
```

---

## 核心架构

### 完整流程

```
用户配置 YAML
    │
    ▼
AppConfig.from_yaml() ──▶ TokenManager (缓存 + 线程锁)
    │                               │
    │                               ▼
    │                    qfnu_login() ──▶ IDS CAS 认证
    │                       │                │
    │                       │          ┌─────┴──────────────┐
    │                       │          │ 提取 salt+execution │
    │                       │          │ 检查是否需要滑块验证码│
    │                       │          │ ┌─ 需要：OpenCV 定位│
    │                       │          │ │ 三阶段搜索策略     │
    │                       │          │ │ 模拟人类鼠标轨迹   │
    │                       │          │ │ AES 加密签名发送   │
    │                       │          │ └─ 不需要：直接登录  │
    │                       │          │ POST AES 加密密码   │
    │                       │          │ 302 → CAS token     │
    │                       │          │ POST /api/cas/user  │
    │                       │          └───▶ Bearer Token    │
    │                       ▼
    │               "bearer" + token
    │                       │
    ▼                       ▼
run_seat_reservation()
    │
    ├── get_date()          # today / tomorrow
    ├── get_build_id()      # 教室名称 → 系统 ID
    ├── get_segment()       # 获取可用时间段 ID
    └── select_seat()       # 循环尝试（最多 100 次）
         │
         ├── get_seat_info()        # 获取空闲座位列表
         ├── 按模式过滤             # 四种模式
         ├── random_get_seat()      # 随机选一个
         ├── encrypt_seat_data()    # AES 加密请求体
         └── post_to_get_seat()     # POST 预约（最多 10 次重试）
              │
              └── check_reservation_status()
                    ├── "预约成功"  ──▶ 通知推送 ✓
                    ├── "重复预约"  ──▶ 查询已预约座位
                    ├── "未到时间"  ──▶ 继续重试
                    ├── "您尚未登录" ──▶ 刷新 Token
                    └── "不可预约"  ──▶ 换座位
```

### 登录与滑块验证码破解（`auth/login.py`）

```
IDS 登录页 ──▶ 提取 salt + execution
   │
   ├── 检查 checkNeedCaptcha.htl
   │    ├── 需要：OpenCV 滑块破解（_solve_slider_captcha）
   │    │        └── 获取 bigImage + smallImage
   │    │             └── _detect_gap_opencv()
   │    │                  ├── CLAHE 增强对比度
   │    │                  ├── 提取滑块图形区域（非黑色像素包围盒）
   │    │                  ├── 策略 1：逆像匹配（TM_CCOEFF / TM_CCORR）
   │    │                  ├── 策略 2：灰度直接匹配
   │    │                  └── 策略 3：Canny 边缘匹配
   │    │             └── _generate_human_tracks() 模拟鼠标轨迹
   │    │             └── AES 加密签名 → POST verifySliderCaptcha
   │    │             └── 搜索策略（最多 300 次尝试）：
   │    │                 阶段 1：中心值
   │    │                 阶段 2：近邻 ±15（步长 1）
   │    │                 阶段 3：全域步长 2
   │    │                 阶段 4：全域步长 2 偏移
   │    └── 不需要：跳过
   │
   └── POST 密码（AES 加密，64 字节随机前缀 + 随机 IV）
        └── 302 重定向 → CAS 换取 Bearer Token
```

### AES 加密体系（`src/crypto/aes.py`）

| 用途 | 密钥 | IV | 特性 |
|------|------|----|------|
| **座位 API**（预约/签到） | `YYYYMMDD + YYYYMMDD` 回文（每日变化） | 固定 `ZZWBKJ_ZHIHUAWEI` | 日期绑定密钥 |
| **登录密码** | `pwdEncryptSalt`（服务端下发） | 随机 16 字符 | 64 字节随机前缀 + 随机 IV |

### 预约五种模式（`get_seat.py`）

| 模式 | 说明 | 使用场景 |
|:-----|:------|:---------|
| **1** | 指定 ID 范围内有插座座位（排除 EXCLUDE_ID） | 想要特定区域 + 充电 |
| **2** | 有插座座位（任意位置，排除 EXCLUDE_ID） | 只在意充电 |
| **3** | 完全随机（最快，成功率最高） | 只要有座位就行 |
| **4** | 指定座位优先，仅适用于 `build_id=22`（东校区图书馆-三楼自修区） | 特定座位偏好 |
| **5** | 指定座位**直连**：只提交 `SEAT_ID` 写明的座位，不切换到其他座位 | 锁定特定座位。⚠️ **永不降级**——抢不到就重试到上限，宁可 0 结果也不坐别的位置 |

### 通知推送（`src/notify/notify.py`）

统一接口 `send_message(config, message, title)`，支持四种渠道：

| 渠道 | 配置字段 | 特点 |
|------|---------|------|
| **DD**（钉钉） | `dd_bot_token` + `dd_bot_secret` | HMAC-SHA256 签名 |
| **TG**（Telegram） | `telegram_bot_token` + `channel_id` | HTTP API 直接调用 |
| **BARK**（iOS） | `bark_url` + `bark_extra` | GET 请求 |
| **ANPUSH** | `anpush_token` + `anpush_channel` | POST form 请求 |

所有渠道使用 `tenacity` 装饰器，网络异常自动重试 3 次（间隔 1s）。

### Web 控制面板（`web/`）

Flask 应用，单页 SPA 风格（`index.html` 包含全部 CSS/JS）：

| API | 方法 | 说明 |
|-----|------|------|
| `/api/login` | POST | CAS 认证（触发滑块验证码） |
| `/api/checkin` | POST | 一键签到 |
| `/api/signout` | POST | 一键签退 |
| `/api/status` | GET | 检查登录状态 |
| `/api/logout` | POST | 清除 session |

特点：
- CSRF 防护（检查 `X-Requested-With` 头）
- Session 存储在文件系统（`flask_session/` 目录）
- 密码明文保存在服务端 session 中
- 蓝色渐变 UI，自适应移动端

### 多用户并发（`scripts/run_all.py`）

- `ThreadPoolExecutor` 并发（默认 8 线程）
- 支持 `--notify-mode aggregated` 聚合通知
- 支持三种操作：`seat` / `checkin` / `signout`

### 辅助脚本

| 脚本 | 用途 |
|------|------|
| `scripts/performance_probe.py` | 7 项性能测量：AES 加密、TCP 延迟、登录全链路、Token 缓存、segment 查询、座位查询、HTTP 状态码分布 |
| `scripts/time_window_test.py` | 19:20 预约时间窗口测试，19:19~19:25 密集采样，2s 间隔 |
| `src/get_seat_info_ForAdmin.py` | 抓取教室座位布局并保存 JSON 快照到 `data/seat_info/` |

---

## 运行命令

```bash
# 安装依赖
pip install -r requirements.txt

# 预约座位（单人）
python src/get_seat.py -c configs/studentA.yml

# 签到
python src/check_in.py -c configs/studentA.yml

# 签退
python src/sign_out.py -c configs/studentA.yml

# 多用户并发预约
python scripts/run_all.py seat -u configs/users.yml

# 多用户签到（聚合通知）
python scripts/run_all.py checkin -u configs/users.yml --notify-mode aggregated

# 管理员：抓取座位布局
python src/get_seat_info_ForAdmin.py -c configs/template.yml \
  --classrooms "东校区图书馆-三楼自修区" --date tomorrow

# 性能探测（只读，不触发真实预约）
python scripts/performance_probe.py -c configs/studentA.yml -n 10

# 19:20 预约窗口测试
python scripts/time_window_test.py -c configs/studentA.yml

# Web 控制面板
cd web
pip install -r web/requirements.txt
python web/app.py
# 浏览器打开 http://localhost:5000
```

### 测试

```bash
pytest                          # 运行全部测试（16 个测试文件）
pytest -v                       # 详细输出
pytest tests/test_config.py     # 单个测试文件
pytest -k "login or token"      # 按关键字过滤
pytest --co                     # 收集测试列表（dry-run）
```

测试配置见 `pytest.ini`（`testpaths=tests`, `pythonpath=src`）。

---

## 关键约定

### 配置文件
- YAML 格式，存放于 `configs/` 目录
- `template.yml` 是模板，复制为 `studentA.yml` 使用
- 通过 `-c` 参数指定，支持相对路径（优先项目根，回退至 `src/` 目录）
- 必填字段：`USERNAME`、`PASSWORD`、`MODE`、`CLASSROOMS_NAME`、`DATE`

### HTTP 重试策略（`src/api/http.py`）

| 条件 | 行为 |
|------|------|
| 4xx 响应 | **不重试，直接抛出** `RequestFailed` |
| 5xx / 超时 / 网络异常 | 重试，最多 10 次，1s 间隔 + 0~0.5s 随机抖动 |
| 总超时 | 120s 后放弃 |

### 异常体系（`src/api/exceptions.py`）

```
Exception
├── RequestFailed          # HTTP 请求失败
├── AuthenticationError    # 登录认证失败
├── ReservationFailed      # 座位预约失败
├── CheckInFailed          # 签到失败
└── SignOutFailed          # 签退失败
```

各入口文件的 `run_*` 函数统一捕获，链式异常追溯。

### 日志规范
- Python 标准 `logging` 模块，入口文件配置 `logging.basicConfig(level=logging.INFO)`
- 输出到 stderr，不写文件
- 多线程场景（`run_all.py`）日志格式含 `%(threadName)s`

### 代码风格
- Google-style docstring
- 类型注解（`typing` / dataclass）
- 无外部 lint 工具（pylint / black / ruff）

### .gitignore
- 忽略 `__pycache__/`、`*.pyc`、IDE 目录、`debug_captcha/`、`flask_session/`

---

## 已知事项

### ⚠️ 重要限制

1. **预约模式 4（指定座位优先）硬编码**仅适用于 `build_id=22`（东校区图书馆-三楼自修区），其他教室会跳过

2. **AES 加密非安全级**：
   - 座位 API 密钥为日期回文（可逆向推算）
   - 固定 IV `ZZWBKJ_ZHIHUAWEI`
   - 登录加密使用随机前缀 + 随机 IV，相对安全

3. **Web 应用**密码明文存储在 Flask session 文件中

4. **不支持 Windows 路径**：路径拼接使用 `os.path.join` + Linux 假设（`/` 分隔符）

### 运行时注意

5. **预约入口最多重试 300 次**，失败后发送通知并退出
6. **滑块验证码最多 300 次尝试**（约 5-30 秒），失败后登录失败
7. **19:20 开放预约**：系统在 19:20 才开放次日预约。在此之前提交预约请求，服务端返回 `{"msg":"开放预约时间19:20"}`（`get_segment()` 本身返回的是时间段 id，不受是否开放影响）
8. **Token 有效期**：1.5 小时，过期自动刷新（线程安全双重检查锁）
9. **服务端限流**（实测 2026-09-14）：`POST /api/Seat/confirm` 按**出口 IP** 限流（不是按账号），
   阈值约 **22-23 次 / 60 秒**。触发后返回 `msg=null` 的快速拒绝（响应约 60ms，正常约 180ms），
   或 `{"msg":"访问频繁，请5分钟后重试"}`，且**数分钟不恢复**。
   同 IP 的无鉴权查询接口 `/api/Seat/seat` 不受影响。
   ⚠️ 阈值按出口 IP 累计，多账号并发会叠加：两个账号各跑 3 秒间隔（合计 37.5 次/分钟）即会越线。
   抢座脚本当前把单账号压到 6 秒间隔（合计约 20 次/分钟）。

### 许可证
- **CC BY-NC 4.0**（署名-非商业使用）

---

*生成时间：2026-07-09 | 基于现有 AGENTS.md 改进补充*