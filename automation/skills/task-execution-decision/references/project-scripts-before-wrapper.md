# 创建自动化脚本前先查项目自带入口

## 教训来源

本 session 中，用户在设置图书馆签到/签退定时任务时说 **「我不是有脚本吗」**——项目已经有了 `check_in.py` 和 `sign_out.py`，但我却先创建了 wrapper 包装脚本。

## 原则

**项目自带的脚本优先。** 不是因为 wrapper 会出 bug，而是：

1. **项目脚本已测试过** — 经过了实际运行验证，走了完整错误处理路径
2. **无额外维护负担** — wrapper 脚本是额外需要维护的代码，每次项目更新可能都需要同步更新 wrapper
3. **YAGNI** — 项目有现成的入口就用现成的，不要为了"统一管理"而包装一层

## 操作流程

### 第一步：检查项目内置入口

```bash
# 检查常见脚本目录
ls -la <项目目录>/scripts/
ls -la <项目目录>/src/
ls -la <项目目录>/bin/

# 特别留意命名：check_in, sign_out, run_all, main, cli 等
```

### 第二步：判断是否可以直接调用

| 情况 | 做法 |
|------|------|
| 项目有对应功能的脚本（如 `check_in.py`） | 直接通过 cron 的 script 参数调用 `python src/check_in.py -c configs/user1.yml` |
| 项目有批量处理入口（如 `run_all.py`） | 优先使用批量入口 |
| 项目没有现成入口，但可一行命令调用 | 创建最小包装脚本（仅 cd + python call） |
| 确实需要多步骤处理 | 创建包装脚本，但注释说明为什么不能直接调 |

### 第三步：包装脚本最小化

如果确实需要包装脚本，保持最小：

```bash
#!/bin/bash
# 好的：只做一件事，透传
cd /home/admin/MyQFNULibraryBook
python src/check_in.py -c configs/user1.yml 2>&1
python src/check_in.py -c configs/user2.yml 2>&1
```

```bash
#!/bin/bash
# 不好的：自己加日志、错误处理、重试机制 —— 项目脚本已经做了
LOGFILE=/tmp/checkin.log
echo "$(date) 开始..." >> "$LOGFILE"
cd /path && python src/check_in.py -c user.yml >> "$LOGFILE" 2>&1
if [ $? -ne 0 ]; then echo "失败"; fi
echo "完成" >> "$LOGFILE"
```

### 第四步：配置 cron 执行

对于单命令执行，使用 `no_agent: true` 模式，script 参数指向包装脚本（最小版本）：

```python
cronjob(
    action='create',
    name='任务名',
    no_agent=True,
    schedule='...',
    script='checkin-students.sh',
    deliver='origin'
)
```

## 检查清单

- [ ] 项目 `scripts/` 目录检查了吗？
- [ ] 项目 `src/` 目录下有同名脚本吗？
- [ ] README 里提到了运行方式吗？
- [ ] 包装脚本是否只是透传调用，没有重复的错误处理？