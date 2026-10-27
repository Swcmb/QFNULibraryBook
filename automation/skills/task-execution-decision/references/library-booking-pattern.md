# 图书馆自动预约模式

## 场景

曲阜师范大学图书馆座位预约系统（`MyQFNULibraryBook`）。每日 19:00 询问用户座位偏好，19:20 开放预约次日座位。

## 完整流程

1. **19:00** — `ask-seat-preference` cron 触发，询问用户楼层和座位号
2. **用户回复** — 如「三楼 240」「五楼随便」「不约」
3. **保存偏好** — 写入 `seat-preference.txt`（第1行楼层，第2行座位号）
4. **19:19** — `book-seat` 预约脚本启动（定时后台进程或 `at`）
   - 读取 `seat-preference.txt` 或准备好配置文件
   - 从 `configs/user1.yml` 模板生成或修改临时配置
   - 设置 MODE='4'（指定座位）或 MODE='3'（随机）
   - SEAT_ID: [座位号] 为指定座位
   - DATE: "tomorrow"
   - 运行 `python src/get_seat.py -c configs/user1.yml`
5. **完成后通知用户** — 预约成功/失败直接推送到 QQ（用户已授权主动推送）

## 预约时间窗口

- **系统开放时间**：19:20
- **启动时间**：19:19（提前1分钟启动，命中开放时刻）
- 之前设过 19:18:30，用户于 2026-07-12 改为 19:19
- `at` 命令计算秒差：`echo $(( $(date -d '19:19' '+%s') - $(date '+%s') ))`
- 后台定时：`terminal(background=true, command="sleep <秒差> && python src/get_seat.py...")`

## 实现方式对比

| 方式 | 适用 | 注意 |
|------|------|------|
| `at` 命令 | 一次性的延时任务 | 需要安装 `at`（`apt install at`） |
| background sleep | 一次性的延时任务 | 用 `notify_on_complete=true` 监听完成 |
| cron | 每天重复的定时预约 | 用户可能每天换座位，不易动态改 |

推荐：一次性的用 `background sleep`，每天重复的用 cron。

## 配置文件结构（user1.yml）

```yaml
PUSH_METHOD: "DD"
DD_BOT_TOKEN: "xxx"
DD_BOT_SECRET: "xxx"
USERNAME: "<学号B>"
PASSWORD: "xxx"
MODE: '4'  # 4=指定座位优先（仅东图三楼 build_id=22 支持）
SEAT_ID:
  - 240   # 第一个为优先座位
CLASSROOMS_NAME:
  - 东校区图书馆-三层自习室  # 会被映射到 build_id=22
DATE: "tomorrow"
```

## 预约脚本（get_seat.py）结构

- `select_seat()` — while 循环（最多 100 次），每次请求空闲座位并尝试预约
- 四种模式：1=有插座指定范围, 2=有插座, 3=随机, 4=指定座位优先
- 模式4（东图三楼专用，build_id=22）：从 SEAT_ID 取首座位优先，其次选列表中可用座位
- 登录含 OpenCV 滑块验证码破解
- 通知：DD（钉钉），PUSH_METHOD 控制

## 关键问题：限流

**问题：** while 循环无延迟，`"开始第 1 次尝试"` 到 `"开始第 46 次尝试"` 在约 30 秒内完成 → 服务器返回 `"访问频繁，请5分钟后重试"`

**修复：** 在 `select_seat()` 的 while 循环中，`retries += 1` 后添加 `time.sleep(3)`，确保每轮间隔 3 秒

```python
while not flag and retries < 100:
    logger.info(f"开始第 {retries + 1} 次尝试获取座位")
    retries += 1
    time.sleep(3)  # 关键：防止触发服务器限流
    ...
```

## 主动推送（用户已授权）

用户于 2026-07-12 明确授权：「你可以主动给我发消息」。预约完成后直接推送结果到 QQ，不需要等用户问"抢到了吗"。成绩监控同理（QFNUScoreReminder 新成绩直接推）。

## 后台定时失败的快速恢复

2026-07-12 实际案例：background sleep 进程因 `.venv/bin/activate` 不存在而失败（项目无虚拟环境，使用系统 Python）。

恢复步骤：
1. 收到 notify_on_complete 失败通知后，立即 `process(action="log", ...)` 查看错误
2. 判断：是环境问题还是逻辑问题？
3. 如果是环境问题，立即改用正确命令重新运行
4. 如果预约时间窗口仍在开放（19:20~19:30），直接重跑
5. 如果超时窗口，通知用户结果

## 自动降级策略（推荐）

指定座位（模式4）抢不到时，不要让用户干等或手动切模式，应自动降级：

1. **前 10 次** — 模式4硬抢指定座位
2. **无果** → 自动切模式3（随机选座），**不再询问用户意见**
3. 抢到了直接通知结果 + 说明原座未放号、改抢了随机座位
4. 如果模式3也失败（万中无一），才告知用户

**理由：** 用户在 19:19 告诉你「要240」时已经做出了选择——在240不可用的情况下，有座位 > 没座位。不需要再问一遍「240没了，要不要随机？」

## 座位抢不到的处理

- 某些座位号（如 240）在特定时间窗口可能不在可用列表里
- 系统返回的座位编号从 001 开始，240 可能这轮没放出来
- 但注意：**座位可用性随时间变化**——之前说"没放出来"的座位，等几分钟后再试可能就有了
- 不要因为第一次没找到就对用户说"240没放出来"，先重试多轮（至少20轮）再下结论

## 查询当前预约状态

API 端点：`GET /api/Member/seat`

- 请求头：`Authorization: bearer <token>`（从 `TokenManager` 获取）
- 返回结构：`data.data[]` 数组，按时间倒序排列
- 注意：默认每页 10 条，如果第1页找不到目标记录，加 `?per_page=50` 参数

### 状态码含义

| status | 含义 | 说明 |
|--------|------|------|
| `"1"` | 预约成功（旧） | 已预约但未签到，可取消 |
| `"2"` | 预约成功 | 已预约但未签到，可取消 |
| `"3"` | 使用中 | 已签到，正在使用座位 |
| `"4"` | 已结束 | 已签退或超时结束 |
| `"6"` | 用户取消 | 已取消的预约 |

### 关键字段

| 字段 | 说明 | 示例 |
|------|------|------|
| `no` | 座位号 | `"201"` |
| `name` | 座位名称（同 no） | `"201"` |
| `nameMerge` | 完整区域 | `"曲阜校区-东校区图书馆 -三楼自修区"` |
| `beginTime` | 开始时间 | `"2026-07-13 08:00:00"` |
| `endTime` | 结束时间 | `"2026-07-13 21:59:59"` |
| `status` | 状态码 | `"2"` |
| `statusName` | 状态描述 | `"预约成功"` |

### 查询命令

```python
import requests
from auth.token import TokenManager

# PYTHONPATH=src 或在项目目录下运行
tm = TokenManager('学号', '密码')
token = tm.get_token()
r = requests.get('http://libyy.qfnu.edu.cn/api/Member/seat?per_page=50',
    headers={'Authorization': token, 'Content-Type': 'application/json'})
data = r.json()
```

## 取消已有预约 + 重新预约流程

当用户已有预约（如座位 240 已成功），但想改抢其他座位（如 213/214）时，流程如下：

### 方案一：直接取消后重跑（推荐）

1. **查询当前预约** — 找到目标座位的预约 ID
   ```python
   GET /api/Member/seat?per_page=50  → 找到 no="240" 的记录，记下 id
   ```

2. **取消预约** — POST `/api/Space/cancel`
   ```python
   cancel_data = {'id': '2802200', 'authorization': token}
   r = requests.post('http://libyy.qfnu.edu.cn/api/Space/cancel', json=cancel_data, headers=headers)
   # 成功返回: {"code":1,"msg":"取消成功"}
   ```

3. **更新配置** — 修改 `configs/user1.yml` 中的 SEAT_ID 列表
   ```yaml
   SEAT_ID:
     - 213
     - 214
   ```

4. **重新运行预约脚本**
   ```bash
   cd /home/admin/MyQFNULibraryBook && PYTHONPATH=src python3 src/get_seat.py -c configs/user1.yml
   ```

### 方案二：直接跑脚本（脚本会自动处理"重复预约"）

当脚本检测到"重复预约"时，会查询当前预约并汇报结果，但**不会自动取消**。所以必须手动取消后再重新跑脚本。

### 为什么脚本会报"重复预约"

- 脚本检测到用户已有该日期/时段的预约
- 这是正常保护机制，不是错误
- 脚本会输出"预约成功：你当前的座位是 X"并退出，但实际没有改变座位
- 必须取消旧的预约，再跑一次才能换座位

## 常见失败模式速查

| 失败症状 | 原因 | 修复 |
|----------|------|------|
| `未到预约时间` | 早于 19:20 | 继续重试，19:20 后自动解决 |
| `重复预约` | 已有该时段预约 | 先取消再重跑 |
| `符合条件的座位数量: 0` | 指定座位不在可用列表 | 换模式3随机抢，或过几分钟再试 |
| `预约成功：座位 240` 但实际想改213 | 脚本检测到已有预约，未改 | 需先取消240再跑 |
| 后台进程炸了（exit code 1） | venv 不存在/路径错 | 不用 source，直接 `python3` |

## 调试技巧

查看 no_agent cron 的输出：`.hermes/cron/output/<job_id>_<timestamp>.txt`
- 每个完成的一次性 cron 任务在 cron/output 下留有运行日志
- 标准输出和错误都会被捕获
- 可据此判断预约状态（登录成功/未到预约时间/限流/成功）

## 前置通知要求（2026-07-12 更新）

用户之前要求「预约脚本执行前必须先发消息通知，确认后再运行。不要直接静默执行。」——这条已被「你可以主动给我发消息」覆盖，预约和成绩监控可直接执行并推送结果，不再需要预先询问。