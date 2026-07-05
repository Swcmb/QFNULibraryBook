# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## 项目概述

曲阜师范大学图书馆座位自动预约系统 — 自动化完成座位**预约 → 签到 → 签退**全流程，基于 `http://libyy.qfnu.edu.cn` REST API 和 `ids.qfnu.edu.cn` CAS 认证。

## 常用命令

```bash
# 安装依赖
pip install -r requirements.txt
# Web 控制面板额外依赖
pip install -r web/requirements.txt

# 运行测试（全部）
pytest tests/ -v
# 运行单个测试文件
pytest tests/test_aes.py -v
# 运行单个测试函数
pytest tests/test_aes.py::test_encrypt_seat_data_roundtrip -v

# 预约座位
python src/get_seat.py -c configs/studentA.yml
# 签到
python src/check_in.py -c configs/studentA.yml
# 签退
python src/sign_out.py -c configs/studentA.yml

# 多用户并发
python scripts/run_all.py seat -u configs/users.yml
python scripts/run_all.py checkin -u configs/users.yml --notify-mode aggregated

# 管理员：抓取教室座位快照
python src/get_seat_info_ForAdmin.py -c configs/template.yml --classrooms "东校区图书馆-三楼自修区"

# 启动 Web 控制面板
python web/app.py
```

## 核心架构

### 认证链（最复杂的子系统）

`src/auth/login.py` → `src/auth/token.py` → 各业务模块

1. **CAS 登录**（`login.py`）：通过 `ids.qfnu.edu.cn` IDS 认证服务完成：
   - 获取 `salt` + `execution` 参数（`_get_salt_and_execution`）
   - 判断是否需要滑块验证码（`_check_need_captcha`）
   - 滑块破解（`_solve_slider_captcha`）：OpenCV CLAHE 增强 + 多策略模板匹配（逆像匹配、灰度匹配、Canny 边缘匹配），三阶段搜索（中心值 → 近邻 ±15 → 全域步长 2），生成模拟人类鼠标轨迹
   - AES 加密密码提交（`encrypt_login_data`）
   - 302 重定向获取 IDS Token → CAS Token → Bearer Token

2. **Token 管理**（`token.py`）：`TokenManager` 线程安全封装，双重检查锁定，1.5 小时过期自动刷新。

### 加密体系（`src/crypto/aes.py`）

两种加密模式：
- **座位 API**：密钥 = `YYYYMMDD + 回文`（如 `2026070330706202`），IV = `"ZZWBKJ_ZHIHUAWEI"`。用于座位预约/签到/签退请求体的 `aesjson` 字段。
- **登录加密**：密码/滑块验证码数据前加 64 字节随机前缀，随机 16 字节 IV。

### 预约流程（`src/get_seat.py`）

```
run_seat_reservation()
  → get_date() 解析 today/tomorrow
  → 遍历 classrooms_name
    → get_build_id() 教室名称 → 系统 ID（classroom_id_mapping）
    → get_segment() 获取时间段 ID
    → select_seat() 根据 MODE 选座
      → get_seat_info() 获取空闲座位列表
      → 按 MODE 过滤（1=指定范围+插座, 2=有插座, 3=完全随机, 4=指定座位号优先）
      → post_to_get_seat() 提交预约
        → encrypt_seat_data() + POST /api/Seat/confirm
        → check_reservation_status() 状态解析与重试
```

### 通知推送（`src/notify/notify.py`）

统一入口 `send_message(config, message, title)` → 按 `push_method` 分发到四个后端，每个后端有 tenacity 3 次重试。四个渠道：Telegram Bot API、钉钉机器人（HMAC-SHA256 签名）、Bark、AnPush。

### 多用户并发（`scripts/run_all.py`）

`ThreadPoolExecutor`（默认 8 线程）+ `concurrent.futures.as_completed()`，支持 `each`（分别通知）和 `aggregated`（聚合汇总）两种通知模式。

### Web 控制面板（`web/app.py`）

Flask + Flask-Session，通过 `sys.path.insert` 复用 `src/` 下的模块。认证凭证存服务端 session，每次签到/签退重新走完整 CAS 登录流程（含滑块破解 ~2-5s）。CSRF 防护检查 `X-Requested-With: XMLHttpRequest` 头。

## 关键数据文件

- `configs/template.yml` — 配置模板（含完整字段注释）
- `configs/users.yml` — 多用户入口，列出每个用户的子配置文件路径
- `data/seat_info/*.json` — 各教室座位布局快照（14 个教室）
- `src/classrooms.py` — 教室名称→ID 映射 + 无插座座位 ID 集合

## 测试特点

- 所有网络调用通过 `unittest.mock.MagicMock` 隔离，测试不产生真实 HTTP 请求
- `conftest.py` 提供共享 fixtures：`sample_config`、`minimal_config`、`fake_token_mgr`、`sample_seat_data` 等
- 16 个测试文件覆盖所有模块，无 integration/e2e 测试
- `pytest.ini` 配置 `testpaths=tests`, `pythonpath=src`，测试从项目根目录运行

## 约束

- **纯 REST 客户端**：无数据库，所有数据通过 API 交互。测试中无需数据库 mock。
- **外部服务依赖**：`ids.qfnu.edu.cn`（IDS 认证）、`libyy.qfnu.edu.cn`（图书馆 API）、各通知渠道 API。代码硬编码这些域名。
- **日期密钥耦合**：AES 加密密钥依赖 `datetime.now()`，跨天边缘（00:00 前后）可能出现密钥变化导致和解密不匹配。
- **编码**：所有 YAML 和 Python 文件使用 UTF-8。PowerShell 环境需注意默认 UTF-16 LE 编码问题。
- **许可证**：CC BY-NC 4.0
