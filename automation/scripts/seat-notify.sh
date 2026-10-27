#!/usr/bin/env bash
# 图书馆抢座结果汇总通知 —— 由 book-seat.sh / book-seat-userC.sh 调用。
#
# 账号信息（日志文件名、姓名、密码、当前预约查询）全部从 configs/userN.yml 读取，
# 调用方通过 --users 指定本次参与的账号。
set -euo pipefail

_PYTHON=/home/admin/MyQFNULibraryBook/.venv/bin/python
[ -x "$_PYTHON" ] || { echo "项目 venv 不存在: $_PYTHON" >&2; exit 1; }

exec "$_PYTHON" /home/admin/.hermes/scripts/seat-notify.py "$@"