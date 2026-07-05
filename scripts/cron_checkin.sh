#!/bin/bash
# 签到 cron 任务
# 对 configs/users.yml 中所有账号执行签到（并发）
set -u

cd /opt/qfnu-library || exit 1

/opt/qfnu-library/venv/bin/python3 scripts/run_all.py checkin -u configs/users.yml
