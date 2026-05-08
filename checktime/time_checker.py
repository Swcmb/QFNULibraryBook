import asyncio
import datetime
import logging
import sys
import os

import aiohttp

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

logging.basicConfig(level=logging.INFO, format='%(message)s')
logger = logging.getLogger(__name__)

URL_GET_SEAT = "http://libyy.qfnu.edu.cn/api/Seat/confirm"

BEIJING_TZ = datetime.timezone(datetime.timedelta(hours=8))

MAX_SAMPLES = 30


def utc_to_beijing(utc_time):
    return utc_time.astimezone(BEIJING_TZ)


def format_time(dt):
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=datetime.timezone.utc)
    beijing = utc_to_beijing(dt)
    utc = dt.astimezone(datetime.timezone.utc)
    return f"{beijing.strftime('%Y-%m-%d %H:%M:%S.%f')[:-3]} (北京时间) | {utc.strftime('%Y-%m-%d %H:%M:%S.%f')[:-3]} (UTC)"


async def get_server_time_once():
    try:
        async with aiohttp.ClientSession() as session:
            headers = {
                "Content-Type": "application/json",
                "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36 Edg/122.0.0.0",
            }

            async with session.get(URL_GET_SEAT, headers=headers, timeout=aiohttp.ClientTimeout(total=5)) as resp:
                if resp.headers.get("Date"):
                    server_time_str = resp.headers["Date"]
                    server_time = datetime.datetime.strptime(server_time_str, "%a, %d %b %Y %H:%M:%S %Z")
                    server_time = server_time.replace(tzinfo=datetime.timezone.utc)
                    local_time = datetime.datetime.now(datetime.timezone.utc)
                    offset = (server_time - local_time).total_seconds()
                    return server_time, local_time, offset
    except Exception as e:
        logger.error(f"获取失败: {e}")
    return None, None, None


async def run_continuous_check(interval=1):
    offset_history = []
    max_offset = None
    min_offset = None

    print("\n" + "=" * 80)
    print("时间差检测系统 - 每秒检测本地时间与服务器时间差")
    print("=" * 80)
    print("格式: 北京时间 | UTC时间 | 偏移 | 平均偏移 | 最大/最小")
    print("-" * 80 + "\n")

    while True:
        server_time, local_time, offset = await get_server_time_once()

        if offset is not None:
            offset_history.append(offset)
            if len(offset_history) > MAX_SAMPLES:
                offset_history.pop(0)

            if max_offset is None or offset > max_offset:
                max_offset = offset
            if min_offset is None or offset < min_offset:
                min_offset = offset

            avg_offset = sum(offset_history) / len(offset_history)

            line = f"{format_time(server_time)}"
            line += f" | 偏移: {offset:+.3f} 秒"
            line += f" | 平均({len(offset_history)}次): {avg_offset:+.3f} 秒"
            line += f" | 最大: {max_offset:+.3f} | 最小: {min_offset:+.3f}"
            print(line)

        await asyncio.sleep(interval)


def main():
    print("开始检测服务器时间差，按 Ctrl+C 退出\n")
    try:
        asyncio.run(run_continuous_check(interval=1))
    except KeyboardInterrupt:
        print("\n\n检测已停止")


if __name__ == "__main__":
    main()