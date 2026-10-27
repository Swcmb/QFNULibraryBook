---
name: library-seat-booking
title: 图书馆座位预约工作流
description: 曲阜师范大学图书馆座位预约系统（MyQFNULibraryBook）的完整操作流程与排错指南。覆盖预约、取消、签到、查状态等日常操作。
category: productivity
triggers:
  - 抢座 / 预约 / 座位
  - 三楼240 / 225 / 226
  - 图书馆 / libyy.qfnu.edu.cn
  - 签到 / 签退
---

# 图书馆座位预约工作流

## 项目位置
`/home/admin/MyQFNULibraryBook/`

## 核心文件

| 文件 | 说明 |
|------|------|
| `configs/user1.yml` | <姓名B>（<学号B>）配置 |
| `configs/user2.yml` | <姓名A>（<学号A>）配置 |
| `configs/user3.yml` | 新用户（<学号C>）配置 |
| `src/get_seat.py` | 预约座位入口 |
| `src/check_in.py` | 签到 |
| `src/sign_out.py` | 签退 |
| `src/auth/token.py` | Token管理器 |
| `src/api/constants.py` | API端点常量 |
| `~/.hermes/scripts/book-seat.sh` | 并发抢座脚本（三账号同时抢，座位写死） |
| `~/.hermes/scripts/book-seat-userC.sh` | <姓名C>抢座脚本（19:20:30启动） |
| `~/.hermes/scripts/checkin-students.sh` | 签到脚本 |
| `~/.hermes/scripts/signout-students.sh` | 签退脚本 |

## 运行方式

> ⚠️ **重要：没有虚拟环境！直接用系统 Python**
> 项目依赖已安装在系统级。不要 source .venv，不要用 pip venv。

```bash
cd /home/admin/MyQFNULibraryBook && PYTHONPATH=src python3 src/get_seat.py -c configs/user1.yml
```

## 四种预约模式

| 模式 | 说明 | 使用场景 |
|-----|------|---------|
| `'1'` | 指定ID范围内有插座座位（排除 EXCLUDE_ID） | 特定区域+充电 |
| `'2'` | 有插座座位（任意位置） | 只在意充电 |
| `'3'` | 完全随机（最快，成功率最高） | 只要有座位就行 |
| `'4'` | 指定座位优先（适用于所有教室） | 特定座位偏好 |
| `'5'` | 指定座位直连 POST（无降级） | 锁定特定座位，绝不换座 |

## 预约工作流

### 1. 查当前时间
```bash
date '+%Y-%m-%d %H:%M:%S'
```
预约窗口每天 **19:20** 开放第二天的座位。

### 2. 确定目标座位
根据用户指令确定要抢的座位号：

- **用户说「抢同样的座位」**：用 `session_search` 查近期 cron 会话，找到最近选定的座位号（如 228/240），不要凭默认配置断言
- **用户说「今天我抢的什么座」**：查 session 历史 + 查 config 文件确认，必要时查 API
- **用户说「三楼 240」「五楼随便」**：直接按用户说的配
- config 可能已过时（如 SEAT_ID: [213, 214] 但实际最近在用 228），**先确认再覆盖**

### 3. 更新配置
编辑 user1.yml 或 user2.yml：
- `MODE: '4'`（指定座位）
- `SEAT_ID:` 填入目标座位号
- `DATE: "tomorrow"`（预约明天）

或者编辑并发抢座脚本 `~/.hermes/scripts/book-seat.sh`，直接修改 SEAT_ID 配置。

### 4. 直接运行（推荐）
```bash
cd /home/admin/MyQFNULibraryBook && PYTHONPATH=src python3 src/get_seat.py -c configs/user1.yml
```

### 5. 查当前预约状态
```bash
cd /home/admin/MyQFNULibraryBook && PYTHONPATH=src python3 -c "
from auth.token import TokenManager, requests
from api.constants import URL_CHECK_STATUS, DEFAULT_HEADERS
tm = TokenManager('学号', '密码')
token = tm.get_token()
headers = {**DEFAULT_HEADERS, 'Authorization': token}
r = requests.get(URL_CHECK_STATUS, headers=headers, timeout=10)
import json; print(json.dumps(r.json(), indent=2, ensure_ascii=False)[:2000])
"
```

### 6. 取消预约
不依赖项目脚本，直接调 API 取消：
```python
from api.constants import URL_CANCEL_SEAT, DEFAULT_HEADERS
body = {'id': '预约ID', 'type': 1}
r = requests.post(URL_CANCEL_SEAT, json=body, headers=headers, timeout=10)
# 成功: {"code": 1, "msg": "取消成功"}
```

**预约状态判断：**
- `status: "2"` → 预约成功（可取消，cancel=1）
- `status: "3"` → 使用中（不可取消，需签退，cancel=0）

**取消完整流程：**
1. 查状态 `GET /api/Member/seat` → 找到 `data.data[0].id`（预约ID）
2. 确认 `cancel: 1`（可取消）
3. POST `/api/Space/cancel` → `{'id': 预约ID, 'type': 1}`

## 常见问题处理

### ❌ Cron 报 ok 但实际没抢到座（座位被秒光）
- **现象**：cron 状态显示 ok，但日志里全是"符合条件的座位数量: 0"，50+ 次重试均未成功
- **原因**：热门座位（如252、226）一旦被他人约走，指定模式（MODE='4'）找不到对应座位，脚本不会换备选，直接耗尽重试次数退出
- **处理**：
  1. 查日志确认是否全零：`grep "符合条件的座位数量" ~/.hermes/cron/output/<job_id>/*.md | sort | uniq -c`
  2. 查 API 确认真实预约状态
  3. 告诉用户：指定座位不可用，要么换号，要么改 MODE='3' 随机抢
- **不要**：只看 cron 状态就断言"抢座成功"

### ⚠️ MODE=4/5 已移除 build_id 限制（2026-10-05）
- 原限制：MODE=4/5只适用于 build_id=22（东校区图书馆三楼）
- 修复后：支持所有楼层，如五楼(build_id=49)、综合楼(build_id=16-20)等
- SEAT_ID填座位号（如198），不是座位ID（如9150）
- 座位ID用于调试查询，脚本内部会自动映射

### ✅ 模式5（直连 POST）—— 2026-09-13 新增

`get_seat.py` 新增 `MODE: '5'`：**不做任何切换/降级**，直接向服务端提交 `SEAT_ID` 里的座位。

- 座位号 -> 系统 id 取自**全量座位列表**（`get_all_seats()`）；
  注意 `get_seat_info()` 只返回空闲座位，用它建映射会拿不到 id。
- GET 的 `status_name` 仅供参考，**不作为是否提交的依据**。

**实测结论（2026-09-13 晚）：**
| 场景 | 服务端对 `/api/Seat/confirm` 的返回 |
|---|---|
| 座位空闲、该账号当天无预约 | `{'code':1,'msg':'预约成功',...}` ✅ 真能订上 |
| 座位已被他人占用 | `{'code':0,'msg':'该空间当前状态不可预约'}` |
| 该账号当天已有预约 | `{'code':0,'msg':'当前用户在该时段已存在座位预约，不可重复预约'}` |

**关键：`该空间当前状态不可预约` 不等于"被别人抢走了"**，它也可能表示
该座位处于刚被释放的过渡态。判断归属要用「不可重复预约」这条。

**限流实测**：连续约 30 次 POST（间隔 3 秒）未触发任何限流，
无 `访问频繁，请5分钟后重试`。循环内的 `time.sleep(3)` 已足够。

**注意**：账号当天已有预约时，模式5 会**一直重试到 300 次**（约 17 分钟），
因为服务端对指定座位返回的是"该空间当前状态不可预约"而不是"不可重复预约"，
脚本识别不出"我已经有座位了"。要换座位必须先取消旧预约。

### ⚠️ MODE=5 无降级行为（2026-10-09 确认）
- MODE=5 对指定座位**从不降级**，一直重试到 max_attempts（默认 300 次）
- 每次尝试约 3.5 秒，300 次 ≈ **17.5 分钟**
- 相比之下 MODE=4 在 `SEAT_FALLBACK_AFTER`（默认 60）次失败后自动降级为随机抢
- **建议**：热门座位（252、226 等易被秒抢的）用 MODE=4 而非 MODE=5，避免白等 17 分钟
- 如必须用 MODE=5，可设置环境变量降低重试次数：`MAX_ATTEMPTS=30 bash book-seat.sh`

### ❌ "未到预约时间"
- 原因：还没到 19:20，或用户已有当天的预约
- 处理：脚本会自动轮询重试。如果用户已有预约，需先取消

### ❌ "重复预约"
- 原因：该用户当天已有有效预约
- 处理：先查当前预约，问用户是否取消再重抢

### ❌ "符合条件的座位数量: 0"
- 原因：指定座位不在当天可用列表里
- 处理：切换 MODE='3' 随机抢一个，或告知用户该座位当天没放

### ⚠️ Cron Job 路径配置坑（2026-09-23 修复）

**错误配置：**
```yaml
script: "bash /home/admin/.hermes/scripts/book-seat.sh"
```
Hermes cron 会把整个字符串当文件路径，导致 "Script not found"。

**正确配置：**
```yaml
script: "book-seat.sh"
```
只填相对路径（相对于 `~/.hermes/scripts/`），cron 会自动加前缀执行。

### ⚠️ 抢座失败不意味着任务失败
- cron exit code 0 ≠ 抢到座，必须查日志确认 "符合条件的座位数量"
- 如果持续为 0，说明座位已被他人约走，需换号或改 MODE=3
- **不要假设 cron 任务成功运行**：exit code -15（SIGTERM）表示任务被强制终止，可能根本没抢到座
- 当用户问"为什么没抢到"或"XX号抢的是几号"时，必须：
  1. 查 cron 历史：`cat ~/.hermes/cron/output/<job_id>/` 看最新日志
  2. 查当前预约状态：通过 API 查询实际预约记录，而非只看配置
  3. 如果 cron 失败，需告知用户并建议手动补跑
- **今天抢明天的预约**：cron 19:18 触发，DATE 字段写死为 tomorrow，确认明天是否有预约需查 API 返回
- **⚠️ Cron 报 ok ≠ 抢座成功**：2026-09-13 发现 cron exit code 124（超时），但状态仍显示 ok。必须查日志确认"符合条件的座位数量"是否为 0

### ✅ 2026-09-13 根因定位：模式4 死等 + 无降级（已修复）

**现象**：19:18 的抢座任务，<学号A>（<姓名A>→三楼252）失败，<学号B>（<姓名B>→三楼226）成功。
cron 状态显示 ok、exit 0，但脚本内部 RC=1（未捕获异常）。

**根因**（实测确认）：
1. `/api/Seat/seat` 返回**全部 278 个座位**（含 `status_name`），不是只返回空闲座位；
   `get_seat_info()` 过滤出 `空闲` 的。
2. 19:20 窗口开放那一刻，**252 已被别人约走**（状态 `已预约`），226 还空闲 →
   226 一次命中，252 全程不可用。
3. `MODE='4'` 只认 `SEAT_ID` 里的座位，**没有任何降级逻辑**：
   找不到就 `指定座位列表中无可用座位，立即重试`，300 次 × 3.5 秒 ≈ 17.5 分钟耗尽后
   抛 `ReservationFailed` → **0 收获退出**。
   今天那次任务从 19:18:37 跑到 19:36:17，正好是 17 分 40 秒。

**修复**（已上线）：
- `src/get_seat.py`：模式4 连续 `SEAT_FALLBACK_AFTER`（默认 60）次抢不到指定座位时，
  **自动降级为随机抢座**（等价模式3），保证"有座 > 没座"。
  环境变量 `SEAT_FALLBACK_AFTER=0` 可关闭降级。
- `scripts/book-seat.sh`：19:18 启动后 `sleep 110` 对齐到 19:19:50，
  让登录/滑块验证在窗口开放前完成；并 `export SEAT_FALLBACK_AFTER=30`。
  ⚠️ **注意**：`SEAT_FALLBACK_AFTER` 只对 MODE=4 生效，MODE=5 不设此变量，会死等 300 次（约 17 分钟耗尽）。

**排查要点（下次照做）**：
- 判断座位是否可用，看 `status_name`，别只看座位号在不在列表里
- 脚本跑满 17 分钟才结束 = 全程没抢到（正常抢到是秒退）
- `python3` 解析：能在本机跑通项目的解释器是
  `/home/admin/.hermes/hermes-agent/.venv/bin/python`（系统 `/usr/bin/python3` **没有 Crypto**）

### ⚠️ 并发抢座脚本已固定座位配置
- book-seat.sh 中两个账号的座位已写死：<学号A>→252，<学号B>→226
- 如需改座位，直接编辑脚本即可，不需要改 yml 配置文件
- 签退通知格式已加学号前缀：`学号: {username}\n签退成功`

## 用户授权
- 主动发消息无需提前问：成绩更新、座位变动、定时事务直接推
- 用户重复同一句话3次→停！那句就是答案
- **用户情绪急躁时（骂人、连续发问）**：快速响应，不要废话，直接给结果

## 配置细节

### user1.yml（<姓名B>）
- 学号: <学号B>
- 默认座位: 东图三楼226（并发脚本已固定）
- 密码存于配置文件
- SUSPEND: true（当前已暂停抢座）

### user2.yml（<姓名A>）
- 学号: <学号A>
- 默认座位: 东图三楼252（并发脚本已固定）
- 密码存于配置文件
- SUSPEND: true（当前已暂停抢座）

### user3.yml（<学号C> - <姓名C>）
- 学号: <学号C>
### user3.yml（<学号C> - <姓名C>）
- 学号: <学号C>
- 预约: 东校区图书馆五楼198号 (build_id=49)
- 密码: `<redacted>`
- MODE=5直连，SEAT_ID填座位号198（不是座位ID 9150）
- 抢座时间: 19:20:30（比<姓名A>、<姓名B>晚30秒，错开请求峰值）
- 2026-10-05: 已移除build_id=22限制，MODE=4/5支持所有楼层
- 2026-10-10: 使用独立脚本 book-seat-userC.sh，不受并发脚本SUSPEND影响

## SUSPEND 配置（2026-10-08 新增）

在 user1.yml/user2.yml 中设置 `SUSPEND: true` 可暂停抢座并发送钉钉通知。

**配置文件字段：**
```yaml
# 抢座暂停开关，true=暂停抢座并发送通知，false=正常抢座
SUSPEND: true
```

**实现原理：**
1. 脚本从原始配置文件加载配置，保留SUSPEND字段
2. 生成临时配置文件到 /tmp/
3. 检查每个配置的 SUSPEND 字段
4. 如果为 true，发送钉钉通知「抢座任务已暂停」并退出
5. 如果为 false，正常执行抢座

**用法：**
```bash
# 通过环境变量暂停（临时）
SUSPEND=true bash book-seat.sh

# 通过配置文件永久暂停
# 编辑 user1.yml 或 user2.yml，添加 SUSPEND: true
```

**注意：** 配置修改后需重启抢座脚本或等下次 cron 运行才生效。

### ⚠️ SUSPEND 检查逻辑（2026-10-10 修复）

`book-seat.sh` 的 SUSPEND 检查会检查**所有用户**的配置。如果任一用户 SUSPEND=true，整个脚本立即退出。

**现象：** <姓名A>或<姓名B> SUSPEND=true 时，整个并发抢座脚本都会退出。

**处理方案：**
- 只想暂停某个用户 → 用独立脚本而非并发脚本
- 目前：<姓名C>有独立脚本 `book-seat-userC.sh`，不受并发脚本影响
- 并发脚本里<姓名A>/<姓名B>共享同一脚本，若任一人暂停，另一人也被阻塞

**恢复抢座方法：**
```bash
# 编辑对应的 yml 文件，将 SUSPEND 改为 false
sed -i 's/SUSPEND: true/SUSPEND: false/' configs/user1.yml
sed -i 's/SUSPEND: true/SUSPEND: false/' configs/user2.yml
```

## 参考资料
- `references/2026-10-01-fifth-floor-inquiry.md` — 东校区图书馆五楼座位查询记录
- `references/suspend-config.md` — SUSPEND 配置功能说明
- `references/mode5-no-fallback.md` — MODE=5 无降级行为及时间消耗记录

### user3.yml（<学号C>）
- 学号: <学号C>
- 预约: 综合楼-804自习室 (build_id=18)，目标座位号15（ID=4020）
- 密码: `<redacted>`
- 注意：MODE=4 仅支持 build_id=22，综合楼需用 MODE=3 随机或手动指定座位ID

## 踩坑记录

1. **不要用虚拟环境** — 项目依赖装在系统 Python 里，无 .venv/venv
2. ⚠️ **重试预算有限，不要跑太早** — 脚本默认 max_attempts=100，自旋速度约 100 次/7 分钟。如果 19:00 就跑，**20 分钟的自旋会把所有重试次数耗在「未到预约时间」上**，到 19:20 窗口开放时已经弹尽粮绝。策略：计算时间差，若距 19:20 超过 8 分钟，用 `sleep` 控制启动时机。
3. **推荐计时策略（避免重试耗尽）**：
   - 查当前时间 `date '+%Y-%m-%d %H:%M:%S'`
   - 若距 19:20 < 5 分钟：直接运行，自旋等待即可
   - 若距 19:20 ≥ 5 分钟：用 `sleep` 对齐到 19:19 附近（登录需 ~30s，让脚本在 19:19:30 左右进入自旋，留 30~60s 缓冲即可覆盖「未到预约时间」阶段，窗口一开立刻命中）
   - 示例：`sleep $(( $(date -d '19:19:30' +%s) - $(date +%s) )) && cd ... && python3 ...`
4. **设后台先验环境** — 任何背景进程必须先在 foreground 验证命令能跑通
5. **Cron job 执行结果必须验证** — exit code -15（SIGTERM）表示任务被杀，可能根本没抢到座。用户问座位时先查 cron 历史 + API 查询实际状态，不要只看配置
6. **并发抢座脚本座位已固定** — book-seat.sh 中已写死：<学号A>→252，<学号B>→226，改座位直接改脚本，不用改 yml
7. **签退通知格式** — 已加学号前缀：`学号: {username}\n签退成功`
8. **⚠️ 抢座失败不通知用户** — 脚本退出码非零不代表失败，只有当"符合条件的座位数量"持续为0时才真正失败。必须查日志确认后再告知用户
9. **⚠️ MODE=5 热门座位慎用** — 252/226 这类热门座一旦被占，MODE=5 会死等 300 次（17.5 分钟），无降级机制。建议用 MODE=4（自动降级）或 MODE=3（随机）
10. **⚠️ 抢座脚本已移除时间对齐（2026-10-10）** — 用户要求「脚本内不用对齐，直接让程序运行即可」。脚本现在立即启动，不再等待 19:18:30。cron 设置在 19:17 启动，实际运行距窗口约 3 分钟，重试预算足够。
11. **⚠️ 重试次数已改为 100 次（2026-10-10）** — 原 300 次，现 100 次。MODE=5 热门座位失败后约 10 分钟退出。get_seat.py 第 153、312 行已修改。
12. **⚠️ 抢座进程清理** — 多次手动运行抢座脚本时，旧进程可能残留（如 PID 3885566）。清理命令：`ps aux | grep "get_seat.py" | grep -v grep; kill <PID>`
13. **⚠️ seat-notify.py 路径错误（2026-10-10）** — <姓名C>独立脚本调用 seat-notify.py 时，该脚本硬编码读取 `/tmp/user2-booking.yml`，而非根据实际配置生成文件名。<姓名C>抢座完成后通知推送失败，但抢座本身正常。
10. **⚠️ 抢座脚本已移除时间对齐（2026-10-10）** — 用户要求「脚本内不用对齐，直接让程序运行即可」。脚本现在立即启动，不再等待 19:18:30。cron 设置在 19:17 启动，实际运行距窗口约 3 分钟，重试预算足够。
11. **⚠️ 重试次数已改为 100 次（2026-10-10）** — 原 300 次，现 100 次。MODE=5 热门座位失败后约 10 分钟退出。get_seat.py 第 153、312 行已修改。
12. **⚠️ 抢座进程清理** — 多次手动运行抢座脚本时，旧进程可能残留（如 PID 3885566）。清理命令：`ps aux | grep "get_seat.py" | grep -v grep; kill <PID>`
13. **⚠️ seat-notify.py 路径错误（2026-10-10）** — <姓名C>独立脚本调用 seat-notify.py 时，该脚本硬编码读取 `/tmp/user2-booking.yml`，而非根据实际配置生成文件名。<姓名C>抢座完成后通知推送失败，但抢座本身正常。