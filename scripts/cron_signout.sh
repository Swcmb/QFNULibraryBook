#!/bin/bash
# 签退 cron 任务
# 对 configs/users.yml 中所有账号执行签退（并发）
set -u

cd /opt/qfnu-library || exit 1

/opt/qfnu-library/venv/bin/python3 scripts/run_all.py signout -u configs/users.yml
