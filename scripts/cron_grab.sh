#!/bin/bash
# 顺序抢座 cron 任务
# 按 configs/admin.yml 中的 GRAB_ORDER 顺序对每个账号执行抢座
set -u

cd /opt/qfnu-library || exit 1

# 调用顺序抢座脚本（内部已处理日志写入）
/opt/qfnu-library/venv/bin/python3 scripts/sequential_grab.py
