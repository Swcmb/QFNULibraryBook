# 座位预约工作流 — 实操备忘录

## 核心命令

```bash
cd /home/admin/MyQFNULibraryBook && PYTHONPATH=src python3 src/get_seat.py -c configs/user1.yml
```

⚠️ 无虚拟环境！直接用系统 Python，不要 source .venv/bin/activate。

## 用户配置

| 用户 | 配置文件 | 学号 | 默认座位 |
|------|---------|------|---------|
| <姓名B>（主人） | `configs/user1.yml` | <学号B> | 三楼240 |
| <姓名A>（对象） | `configs/user2.yml` | <学号A> | 三楼219/220(原) |

密码在对应 YAML 文件中，勿外泄。

## 换座完整流程

### 1. 查当前预约 → 找目标座位 ID

```python
from auth.token import TokenManager
tm = TokenManager('<学号B>', '<redacted>')
token = tm.get_token()
r = requests.get('http://libyy.qfnu.edu.cn/api/Member/seat?per_page=50',
    headers={'Authorization': token})
# 遍历 data['data']['data']，找需要的座位的 id
```

### 2. 取消旧预约

```python
r = requests.post('http://libyy.qfnu.edu.cn/api/Space/cancel',
    json={'id': res_id, 'authorization': token},
    headers={'Authorization': token})
# → {"code":1,"msg":"取消成功"}
```

### 3. 改配置
- `MODE: '4'`（指定座位优先）
- `SEAT_ID`: 修改为目标座位号
- `DATE: "tomorrow"`（19:20后抢明天）

### 4. 抢座
```bash
PYTHONPATH=src python3 src/get_seat.py -c configs/user1.yml
```

## 计时策略（避免重试耗尽）

脚本默认 max_attempts=100，自旋速度约 100 次/7 分钟。窗口 19:20 开放。

**推荐做法：**
- 距 19:20 < 5 分钟 → 直接跑，自旋覆盖
- 距 19:20 ≥ 5 分钟 → 用 sleep 对齐到 19:19 左右
  ```bash
  # 当前时间 19:07，距 19:19:30 约 744 秒
  sleep 744 && cd /home/admin/MyQFNULibraryBook && PYTHONPATH=src python3 src/get_seat.py -c configs/user1.yml
  ```
  登录需 ~30 秒，脚本在 19:19:30 进入自旋，留 30~60 秒缓冲覆盖「未到预约时间」阶段，窗口一开立刻命中。

**现场验证（2026-07-16）：** 第一次 19:00 直接跑，100 次自旋在 19:07 前全部耗尽，弹尽粮绝。第二次用 `sleep 744` 对齐到 19:19:30，第 3 次尝试就抢到 240。✅

## Cron 任务自主决策模式

当 cron 任务收到用户询问消息（如「今晚19:20开放，约哪个座位？」）且用户不在线时：
1. 用户无法回复确认 — 这是 cron 任务，不是交互对话
2. **直接按默认座位执行**（user1 默认三楼240，user2 按最近 session 记录或配置）
3. 不需要等待或追问，默认就是安全选项
4. 流程：改配置 → 按计时策略发起后台进程 → 等待结果 → 报告

## 常见错误处理

| 错误 | 原因 | 处理 |
|------|------|------|
| 未到预约时间 | 19:20前 | 等19:20后重试。注意重试预算有限 |
| 重复预约 | 已有预约 | 先取消再抢 |
| 符合条件的座位数量: 0 | 座位不在可用列表 | 多试几轮，真没有就报告用户 |
| .venv/bin/activate: 不存在 | 不该source | 直接用系统 Python |

## 用户硬性规则
1. 进程炸了**立刻诊断重启**，不等用户问
2. **不要擅自切换模式**（比如随机），先问用户
3. 钉钉通知已配置，预约成功自动推送