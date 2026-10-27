#!/bin/bash
# 图书馆预约/签到/签退精准定时守护脚本
# 08:01 签到  |  19:19 抢座  |  21:30 签退

LOG_DIR=/opt/qfnulibrary/logs
PY=/opt/qfnulibrary/venv/bin/python3
ARGS="-u /opt/qfnulibrary/configs/users.yml --notify-mode aggregated"
mkdir -p $LOG_DIR

cd /opt/qfnulibrary

log() {
    echo "[$(date '+%Y-%m-%d %H:%M:%S')] $1" >> $LOG_DIR/loop.log
}

run_and_log() {
    local action=$1
    log "开始执行: $action"
    $PY scripts/run_all.py "$action" $ARGS >> $LOG_DIR/${action}.log 2>&1
    log "$action 执行完毕"
}

while true; do
    now=$(date '+%H%M')

    # --- 08:01 签到 ---
    if [ "$now" = "0801" ]; then
        run_and_log checkin
        sleep 65
        continue
    fi

    # --- 19:19 抢座 ---
    if [ "$now" = "1919" ]; then
        run_and_log seat
        sleep 65
        continue
    fi

    # --- 21:30 签退 ---
    if [ "$now" = "2130" ]; then
        run_and_log signout
        sleep 65
        continue
    fi

    sleep 10
done
