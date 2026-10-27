#!/usr/bin/env bash
# 图书馆签退 —— 三账号并发
# 调度: Hermes cron "30 21 * * *"（ticker 相位 → 21:30 左右拉起）
cd "$HOME/MyQFNULibraryBook" || exit 1
exec "$HOME/MyQFNULibraryBook/.venv/bin/python" scripts/run_all.py signout -u configs/users_all.yml