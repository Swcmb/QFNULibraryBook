#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""综合楼804 座位15 精准抢座 — 学号 <学号C>（MODE 5 直连，不降级）

调度: 手动执行 bash ~/.hermes/scripts/book-seat-zonghe.sh
     cron "17 19 * * *" 会误触发 book-seat.sh，故本脚本不挂 cron。

时序: 登录 → 预取座位ID映射 → 睡到 19:21:30 → 首发预约请求

为何不复用 src/get_seat.py 的轮询循环、也不在 19:20:00 抢首发:
  /api/Seat/confirm 的限流按【出口 IP】计（实测阈值 ~22-23 次/60 秒），而
  book-seat.sh 的两个账号（最高优先级任务）在 19:19:00-19:20:00 已占用 ~20 次。
  若本脚本也在 19:20:00 抢首发，三账号叠加会顶破阈值，触发后数分钟不恢复，
  会把两个最高优先级账号一起拖下水。故本脚本：
    · 19:21:30 前不发任何 confirm（把 19:20 放座瞬间的限流额度全让给两账号）；
    · 首发后只留 4 次重试（≈36 秒），全程 5 次请求。

凭据从 configs/user3.yml 读取，代码内不出现密码与钉钉 token。
用法:
  book-seat-zonghe.py          正常调度（睡到 19:21:30 首发）
  book-seat-zonghe.py --test   跳过等待，立即发一次请求（链路自检用）
"""
import argparse
import logging
import os
import sys
import time
from datetime import datetime

_PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
_PROJECT_SRC = os.path.join(_PROJECT_ROOT, "src")
_LOG_FILE = "/tmp/seat-<学号C>.log"

sys.path.insert(0, _PROJECT_SRC)

from config.config import AppConfig                        # noqa: E402
from auth.token import TokenManager                        # noqa: E402
from notify.notify import send_message                     # noqa: E402
from get_info import get_date, get_build_id, get_segment   # noqa: E402
from get_seat import get_all_seats, post_to_get_seat       # noqa: E402

logger = logging.getLogger("book_zonghe")

# 首发时刻。刻意晚于 19:20 放座 90 秒：放座瞬间限流额度全给 book-seat.sh 的两账号
RELEASE_TIME = "19:21:30"
# 首发后的重试间隔: 前两次 6 秒（兜住服务端放座延迟），之后拉长到 12 秒
FIRST_GAP, LATER_GAP = 6, 12
# 尝试次数上限（首发 + 4 次重试 ≈ 36 秒），避免长期占用限流额度
MAX_ATTEMPTS = 5

# 本脚本专属的抢座目标，覆盖 configs/user3.yml 里的常规座位
SEAT_NO = "15"
CLASSROOM = "综合楼-804自习室"


def load_config():
    """从 configs/user3.yml 继承凭据与通知设置，叠加本脚本的专属座位。"""
    cfg = AppConfig.from_yaml(os.path.join(_PROJECT_ROOT, "configs", "user3.yml"))
    cfg.mode = "5"
    cfg.seat_id = [SEAT_NO]
    cfg.classrooms_name = [CLASSROOM]
    cfg.date = "tomorrow"
    return cfg


def sleep_until(epoch: float, busy_window: float = 0.05) -> None:
    """睡到指定 epoch。最后 busy_window 秒改用短睡，避免 sleep 唤醒抖动睡过头。"""
    while True:
        remain = epoch - time.time()
        if remain <= 0:
            return
        time.sleep(remain - busy_window if remain > busy_window else 0.001)


def resolve_seat_id(build_id, segment, nowday, target_no):
    """座位号 → 系统 ID。必须查全量座位表：空闲表里不含已被预约的座位。"""
    for seat in get_all_seats(build_id, segment, nowday):
        if (str(seat["no"]).lstrip("0") or "0") == target_no:
            return seat["id"]
    return None


def main() -> int:
    parser = argparse.ArgumentParser(description="综合楼804 座位15 精准抢座")
    parser.add_argument("--test", action="store_true",
                        help="跳过等待，立即发一次请求（链路自检）")
    args = parser.parse_args()

    config = load_config()
    token_mgr = TokenManager(config.username, config.password)

    nowday = get_date(config.date)
    build_id = get_build_id(config.classrooms_name[0])
    segment = get_segment(build_id, nowday)
    logger.info("目标: %s 座位%s | 日期 %s | build_id=%s segment=%s",
                config.classrooms_name[0], config.seat_id[0], nowday, build_id, segment)

    token_mgr.get_token()   # 提前登录（含滑块验证，实测 ~11s）
    logger.info("登录就绪: %s", config.username)

    target_no = str(config.seat_id[0]).lstrip("0") or "0"
    seat_id = resolve_seat_id(build_id, segment, nowday, target_no)
    if seat_id is None:
        msg = "未在座位表中找到座位 %s，放弃" % target_no
        logger.error(msg)
        send_message(config, msg, "抢座异常 - 学号: %s" % config.username)
        return 1
    logger.info("座位 %s → 系统ID %s", target_no, seat_id)

    if args.test:
        release_at = time.time()
        logger.info("--test 模式：立即首发")
    else:
        hh, mm, ss = (int(x) for x in RELEASE_TIME.split(":"))
        release_at = datetime.now().replace(
            hour=hh, minute=mm, second=ss, microsecond=0).timestamp()
        if release_at <= time.time():
            logger.warning("已过 %s，立即开始", RELEASE_TIME)
            release_at = time.time()
        else:
            logger.info("等待首发时刻 %s（还有 %.0f 秒，19:20 放座期间不发请求）",
                        RELEASE_TIME, release_at - time.time())

    messages = []
    for attempt in range(1, MAX_ATTEMPTS + 1):
        sleep_until(release_at)
        started = time.time()
        try:
            ok = post_to_get_seat(seat_id, segment, config, token_mgr, messages)
        except Exception as exc:
            # 限流/网络异常：不再硬刚，避免把限流窗口拖长（触发后数分钟不恢复）
            logger.error("第 %d 次请求异常，停止重试: %s", attempt, exc)
            messages.append("第 %d 次请求异常: %s" % (attempt, exc))
            break
        cost_ms = (time.time() - started) * 1000
        logger.info("第 %d 次%s（%.0fms）", attempt, "成功" if ok else "未成功", cost_ms)
        if ok:
            break
        release_at = time.time() + (FIRST_GAP if attempt <= 2 else LATER_GAP)

    if messages:
        send_message(config, "\n".join(messages),
                     "抢座结果 - 学号: %s" % config.username)
    return 0


if __name__ == "__main__":
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(levelname)s %(message)s",
        handlers=[
            logging.FileHandler(_LOG_FILE, encoding="utf-8"),
            logging.StreamHandler(sys.stdout),
        ],
    )
    sys.exit(main())