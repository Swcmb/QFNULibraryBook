#!/bin/bash
# 综合楼804 座位15 精准抢座 — 学号 <学号C>
# 手动执行（不挂 cron）：bash ~/.hermes/scripts/book-seat-zonghe.sh
# 加 --test 跳过等待，立即发一次请求做链路自检
#
# 首发 19:21:30，刻意晚于 19:20 放座 90 秒：
# /api/Seat/confirm 的限流按出口 IP 计（实测阈值约 22-23 次/60 秒），
# 而 book-seat.sh 的两个账号在 19:19-19:20 已占用约 20 次。

cd /home/admin/MyQFNULibraryBook || exit 1

# 使用项目独立 venv（系统 /usr/bin/python3 与 Hermes venv 均缺 Crypto/cv2）
PYTHON="$HOME/MyQFNULibraryBook/.venv/bin/python"
[ -x "$PYTHON" ] || { echo "项目 venv 不存在: $PYTHON" >&2; exit 1; }

exec "$PYTHON" /home/admin/.hermes/scripts/book-seat-zonghe.py "$@"