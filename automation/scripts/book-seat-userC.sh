#!/bin/bash
# 图书馆抢座 — <姓名C>（<学号C>）抢五楼198号
# 启动时间：19:20:30（比<姓名A>、<姓名B>晚30秒，错开请求峰值）
# 注意：cron 只支持分钟精度，所以设置在 19:20 启动，脚本内 sleep 30 秒
#
# SUSPEND 配置：设置环境变量 SUSPEND=true 可暂停抢座并发送通知
# 用法: SUSPEND=true bash book-seat-userC.sh

cd /home/admin/MyQFNULibraryBook || exit 1

# 使用项目独立 venv（系统 /usr/bin/python3 与 Hermes venv 均缺 Crypto/cv2）
PYTHON="$HOME/MyQFNULibraryBook/.venv/bin/python"
[ -x "$PYTHON" ] || { echo "项目 venv 不存在: $PYTHON" >&2; exit 1; }

# ---- SUSPEND 检查 ----
# 必须在 cd 与 PYTHON 赋值之后，否则暂停分支拿不到解释器
if [ "${SUSPEND}" = "true" ] || [ "${SUSPEND}" = "1" ]; then
    echo "[$(date '+%Y-%m-%d %H:%M:%S')] SUSPEND=true，暂停抢座，发送通知..."
    $PYTHON << 'PYEOF'
import sys
sys.path.insert(0, '/home/admin/MyQFNULibraryBook/src')
from notify.notify import send_message
from config.config import AppConfig

config = AppConfig.from_yaml('/home/admin/MyQFNULibraryBook/configs/user3.yml')
send_message(config, "<姓名C>抢座任务已暂停（SUSPEND=true）", "图书馆抢座通知")
print("通知已发送")
PYEOF
    echo "[$(date '+%Y-%m-%d %H:%M:%S')] 抢座已暂停，退出"
    exit 0
fi

# 等待30秒，确保在 19:20:30 开始抢座
echo "[$(date '+%Y-%m-%d %H:%M:%S')] <姓名C>抢座脚本启动，等待30秒..."
sleep 30
echo "[$(date '+%Y-%m-%d %H:%M:%S')] <姓名C>抢座正式开始（19:20:30）"

echo "[$(date '+%Y-%m-%d %H:%M:%S')] <姓名C>抢座开始..."

# 生成临时配置（凭据从 configs/user3.yml 继承）
$PYTHON << 'PYEOF'
import os
import sys
import yaml

sys.path.insert(0, '/home/admin/MyQFNULibraryBook/src')
from config.config import AppConfig

cfg = AppConfig.from_yaml('configs/user3.yml')
data = {
    'PUSH_METHOD': cfg.push_method,
    'DD_BOT_TOKEN': cfg.dd_bot_token,
    'DD_BOT_SECRET': cfg.dd_bot_secret,
    'USERNAME': cfg.username,
    'PASSWORD': cfg.password,
    'GITHUB': False,
    'MODE': '5',
    'DATE': 'tomorrow',
    'SEAT_ID': [198],  # 座位号
    'CLASSROOMS_NAME': ['东校区图书馆-五楼自习区（南）（东区房间静音）'],
    'SUSPEND': cfg.suspend,
}
with open('/tmp/user3-booking.yml', 'w') as f:
    yaml.dump(data, f, allow_unicode=True)
# 临时配置含明文密码与钉钉凭据，立即收紧到 600
os.chmod('/tmp/user3-booking.yml', 0o600)
print("临时配置已生成")
PYEOF
if [ $? -ne 0 ]; then
    echo "[$(date '+%Y-%m-%d %H:%M:%S')] 临时配置生成失败，退出"
    exit 1
fi

# 抢座
$PYTHON src/get_seat.py -c /tmp/user3-booking.yml > /tmp/seat-<学号C>.log 2>&1
RC=$?

echo "[$(date '+%Y-%m-%d %H:%M:%S')] 抢座完成，退出码: $RC"

# 推送结果到钉钉
$PYTHON /home/admin/.hermes/scripts/seat-notify.py --users configs/user3.yml

rm -f /tmp/user3-booking.yml
exit $RC