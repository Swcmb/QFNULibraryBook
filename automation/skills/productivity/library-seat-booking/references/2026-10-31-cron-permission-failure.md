# 抢座任务权限故障与全流程验证（2026-10-31）

## 摘要

2026-10-31 19:18，Hermes cron 任务「图书馆抢座」按计划触发，但脚本在第一步生成临时配置时报 `PermissionError` 直接退出，`get_seat.py` 一次也没有启动。当日 19:20 放出的次日座位全部被其他读者预约。

根因：`book-seat.sh` 把临时配置固定写到 `/tmp/userN-booking.yml`。当天早上 07:44 有一次以 root 身份运行的残留，三个文件属主变为 `root:root`、权限 `0600`。`/tmp` 带 sticky 位，普通用户既不能覆盖也不能删除他人文件，于是 cron 以普通用户运行时在 `open(tmp_file, 'w')` 处失败。

修复：临时配置改用 `mktemp -d` 唯一目录，并用 `trap ... EXIT` 保证任何退出路径都清理明文凭据。修复后三个账号的预约、签到、签退全流程实测通过。

## 时间线

| 时间 | 事件 |
|---|---|
| 10-31 07:44 | 一次以 root 身份执行的 `book-seat.sh` 中断，未走到末尾清理，留下三个 `root:root 0600` 的临时配置 |
| 10-31 19:18:08 | cron 准时拉起任务（延迟 8.9s，`on_time`） |
| 10-31 19:18:11 | 配置生成失败，任务以 `error` 结束，`failure_streak` 变为 1 |
| 10-31 19:20 | 次日座位放座，三个目标座位被其他读者预约 |
| 10-31 20:45 | 排查定位到 `/tmp` 残留文件，确认权限与属主 |
| 10-31 20:46 | 清理残留、部署 `mktemp` 版本并完成干跑验证 |
| 10-31 20:53–20:59 | 三个账号签到、签退、预约全流程真实 API 验证通过 |

## 故障现象

cron 输出的错误为：

```text
[2026-10-31 19:18:11] 开始抢座...
[2026-10-31 19:18:11] 临时配置生成失败，退出
PermissionError: [Errno 13] Permission denied: '/tmp/user2-booking.yml'
```

同时 `/tmp/seat-*.log` 的时间戳仍停留在前一日，说明三个抢座进程都没有被创建。

## 根因分析

1. **固定路径的临时文件**：三个账号的临时配置写在 `/tmp/user1-booking.yml`、`/tmp/user2-booking.yml`、`/tmp/user3-booking.yml`，与运行用户无关。
2. **root 残留**：任意一次以 root 运行且中途退出，都会把文件留成 `root:root 0600`。脚本只在正常结束时执行 `rm`，异常路径不清理。
3. **sticky 位阻止接管**：`/tmp` 权限为 `1777`，普通用户不能删除或改写他人拥有的文件，`chown` 也需要 root。
4. **失败点在最前**：配置生成是脚本第一步，失败后直接 `exit 1`，后续 SUSPEND 检查与抢座进程全部不执行。

只改属主（`chown`）能解这一次，但下一次再有人以 root 运行仍会复发，因此修复选择消除共享固定路径。

## 修复

`automation/scripts/book-seat.sh`：

```bash
TMP_DIR=$(mktemp -d /tmp/seat-booking.XXXXXX) || { echo "创建临时目录失败" >&2; exit 1; }
trap 'rm -rf "$TMP_DIR"' EXIT
```

- 三个临时配置写入 `$TMP_DIR`，不再使用固定路径
- 生成段与 SUSPEND 检查段通过环境变量 `TMP_DIR` 传给 Python
- 三处 `get_seat.py -c` 指向 `$TMP_DIR`
- 删除结尾的固定路径 `rm`，由 `EXIT` trap 统一清理
- 顺带把目标座位从 10-27 的临时值（四层 49）改回三层 252 / 三层 226 / 五层 198

唯一目录的另一个作用：即使进程被 `SIGKILL`（trap 不会触发），残留也只是一个普通用户持有的随机目录，不会阻塞下一次运行。

## 验证

### 静态与权限

```text
bash -n book-seat.sh                 → OK
属主 admin:admin  权限 755
```

### 干跑（只执行到 SUSPEND 检查，不触发抢座）

以任务实际运行用户执行脚本第 1–112 行：

```text
configs/user2.yml -> /tmp/seat-booking.RM6i8I/user2-booking.yml (座位 252)
configs/user1.yml -> /tmp/seat-booking.RM6i8I/user1-booking.yml (座位 226)
configs/user3.yml -> /tmp/seat-booking.RM6i8I/user3-booking.yml (座位 198)
临时配置已生成
RC=0
```

退出后检查：`tmp dir cleaned`、`no fixed-name booking files`。

### 调度状态

`enabled=True`，`next_run_at=2026-11-01T19:18:00+08:00`。次日 19:18 的真实执行是最终验收点。

## 全流程验证（2026-10-31 20:58–20:59）

三个账号针对当日空位执行「预约 → 签到 → 签退」，全部走真实接口。

| 账号 | 预约 | 签到 | 签退 | 终态 |
|---|---|---|---|---|
| `<姓名A>` | 三层 005 成功 | 签到成功 | 完全离开操作成功 | 已结束 |
| `<姓名B>` | 三层 002 成功 | 使用中，无需重复签到 | 完全离开操作成功 | 已结束 |
| `<姓名C>` | 五层 001 成功 | 签到成功 | 完全离开操作成功 | 已结束 |

- 登录耗时 2.6–3.3 秒，滑块验证在 46–57 次尝试内命中
- 预约从发请求到「预约成功」约 0.2–0.8 秒
- 签退三次均返回「完全离开操作成功」，总耗时 14.4 秒

## 状态字段纠正

`scripts/probe_my_bookings.py` 里的数字映射把 `status=4` 注释为「已签到」，实测 `statusName` 是 **「已结束」**。判断签退是否成功应看 `statusName`，不要依赖数字编码。签退后当日记录即为「已结束」，与「已签到」无关。

## 遗留风险

滑块验证存在偶发「241 次 gap 搜索全部落空」的情况，由 `_login_with_retry` 重试兜底。常态下 50 次左右即可命中、3 秒内完成；一旦赶上全失败，单次登录会消耗数分钟，在 19:18–19:20 这两分钟窗口内属于时间风险。当前没有做时间预算控制。

## 相关文件

- `automation/scripts/book-seat.sh` — 本次修复的抢座入口
- `src/get_seat.py` — 抢座核心逻辑，负责登录、预热与放座瞬间连发
- `src/auth/login.py` — 滑块验证与重试
- `src/sign_out.py` — 签退实现，按 `statusName == 使用中` 匹配记录
- `src/check_in.py` — 签到实现
