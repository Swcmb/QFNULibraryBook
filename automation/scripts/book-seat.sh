#!/bin/bash
# 图书馆抢座 — 三个账号并发抢不同座位（MODE 5 直连，抢不到也不降级）
# <学号A> (<姓名A>) -> 四楼 49（临时，2026-10-27 改，原目标 三楼 252）
# <学号B> (<姓名B>) -> 三楼 226
# <学号C> (<姓名C>) -> 五楼 198
#
# 调度: Hermes cron "18 19 * * *"（实测 ticker 在整分后约 9~10 秒拉起脚本）
#   <姓名A>、<姓名B>：脚本一起来就启动，登录+座位表实测 2.8~5.8s，随后进入放座前预热
#   <姓名C>：脚本内部睡到绝对时刻 19:19:30 再启动（独立 cron 任务已按用户要求删除）
#   放座瞬间 19:20:00 的三个座位抢法见 get_seat.py 顶部的限流实测注释
#
# SUSPEND 配置：在 user1.yml/user2.yml/user3.yml 中设置 SUSPEND: true 可暂停抢座并发送通知

cd /home/admin/MyQFNULibraryBook || exit 1

# 使用项目独立 venv（系统 /usr/bin/python3 与 Hermes venv 均缺 Crypto/cv2）
PYTHON="$HOME/MyQFNULibraryBook/.venv/bin/python"
[ -x "$PYTHON" ] || { echo "项目 venv 不存在: $PYTHON" >&2; exit 1; }

echo "[$(date '+%Y-%m-%d %H:%M:%S')] 开始抢座..."

# 生成三个用户的临时配置（固定座位，预约明天）
# 凭据全部从 configs/userN.yml 继承，此处只覆盖抢座相关字段
$PYTHON << 'PYEOF'
import os
import sys
import yaml

sys.path.insert(0, '/home/admin/MyQFNULibraryBook/src')
from config.config import AppConfig

# 学号 -> (目标座位号, 目标区域)
TARGETS = {
    '<学号A>': (49, '东校区图书馆-四层中文现刊室'),
    '<学号B>': (226, '东校区图书馆-三层自习室'),
    '<学号C>': (198, '东校区图书馆-五楼自习区（南）（东区房间静音）'),
}

for source_file, tmp_file in [
    ('configs/user2.yml', '/tmp/user2-booking.yml'),
    ('configs/user1.yml', '/tmp/user1-booking.yml'),
    ('configs/user3.yml', '/tmp/user3-booking.yml'),
]:
    cfg = AppConfig.from_yaml(source_file)
    seat_id, classroom = TARGETS[cfg.username]

    # 保留凭据与通知设置，只覆盖抢座相关配置
    data = {
        'PUSH_METHOD': cfg.push_method,
        'DD_BOT_TOKEN': cfg.dd_bot_token,
        'DD_BOT_SECRET': cfg.dd_bot_secret,
        'USERNAME': cfg.username,
        'PASSWORD': cfg.password,
        'GITHUB': False,
        'MODE': '5',
        'DATE': 'tomorrow',
        'SEAT_ID': [seat_id],
        'CLASSROOMS_NAME': [classroom],
        'SUSPEND': cfg.suspend,
    }
    with open(tmp_file, 'w') as f:
        yaml.dump(data, f, allow_unicode=True)
    # 临时配置含明文密码与钉钉凭据，立即收紧到 600
    os.chmod(tmp_file, 0o600)
    print('%s -> %s (座位 %s)' % (source_file, tmp_file, seat_id))

print("临时配置已生成")
PYEOF
if [ $? -ne 0 ]; then
    echo "[$(date '+%Y-%m-%d %H:%M:%S')] 临时配置生成失败，退出"
    exit 1
fi

# ---- SUSPEND 检查 ----
$PYTHON << 'PYEOF'
import sys
sys.path.insert(0, '/home/admin/MyQFNULibraryBook/src')
from notify.notify import send_message
from config.config import AppConfig

suspended = False
for cfg_file in ['/tmp/user2-booking.yml', '/tmp/user1-booking.yml', '/tmp/user3-booking.yml']:
    try:
        config = AppConfig.from_yaml(cfg_file)
        if config.suspend:
            send_message(config, "抢座任务已暂停（SUSPEND=true）", "图书馆抢座通知")
            print(f"{cfg_file}: SUSPEND=true，已发送通知")
            suspended = True
    except Exception as e:
        print(f"检查 {cfg_file} 失败: {e}")

if suspended:
    sys.exit(1)  # 有用户暂停，返回非0
sys.exit(0)    # 全部正常，返回0
PYEOF
if [ $? -ne 0 ]; then
    echo "[$(date '+%Y-%m-%d %H:%M:%S')] 抢座已暂停，退出"
    exit 0
fi

# 并发抢座（各自输出留档，便于事后核查）
# <姓名A>、<姓名B>立即启动
$PYTHON src/get_seat.py -c /tmp/user2-booking.yml > /tmp/seat-<学号A>.log 2>&1 &
PID_A=$!
$PYTHON src/get_seat.py -c /tmp/user1-booking.yml > /tmp/seat-<学号B>.log 2>&1 &
PID_B=$!

# <姓名C>睡到绝对时刻 19:19:30 再启动。用绝对时刻而不是固定 sleep，
# 是因为 cron 只有分钟精度、ticker 又有约 9~10 秒延迟，固定秒数会让启动点漂移。
(
    _target=$(date -d "today 19:19:30" +%s)
    _gap=$((_target - $(date +%s)))
    if [ "$_gap" -gt 0 ]; then
        echo "[$(date '+%Y-%m-%d %H:%M:%S')] <姓名C>等待 ${_gap}s，19:19:30 启动"
        sleep "$_gap"
    else
        echo "[$(date '+%Y-%m-%d %H:%M:%S')] 已过 19:19:30，<姓名C>立即启动"
    fi
    $PYTHON src/get_seat.py -c /tmp/user3-booking.yml > /tmp/seat-<学号C>.log 2>&1
) &
PID_C=$!

wait $PID_A
RC_A=$?
wait $PID_B
RC_B=$?
wait $PID_C
RC_C=$?

echo "<姓名A>(<学号A>->49): $RC_A | <姓名B>(<学号B>->226): $RC_B | <姓名C>(<学号C>->198): $RC_C"

# ---- 抢座结束后，把结果推送到钉钉 ----
$PYTHON /home/admin/.hermes/scripts/seat-notify.py \
    --users configs/user2.yml configs/user1.yml configs/user3.yml

rm -f /tmp/user1-booking.yml /tmp/user2-booking.yml /tmp/user3-booking.yml
echo "[$(date '+%Y-%m-%d %H:%M:%S')] 抢座完成"

# 退出码必须反映真实结果。原实现无条件 exit 0，把 2026-10-18 <姓名A>丢座
# （RC_A=1）上报成 cron "ok"，failure_streak 和告警全部失效。
if [ "$RC_A" -ne 0 ] || [ "$RC_B" -ne 0 ] || [ "$RC_C" -ne 0 ]; then
    echo "[$(date '+%Y-%m-%d %H:%M:%S')] 有账号未抢到座位，返回非零"
    exit 1
fi
exit 0