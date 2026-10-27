#!/usr/bin/env bash
# 图书馆签到 —— 三账号并发
# 调度: Hermes cron "1 8 * * *"（ticker 相位 → 08:01 左右拉起）
cd "$HOME/MyQFNULibraryBook" || exit 1
exec "$HOME/MyQFNULibraryBook/.venv/bin/python" scripts/run_all.py checkin -u configs/users_all.yml