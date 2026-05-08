import asyncio
import datetime
import logging

import aiohttp

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

URL_GET_SEAT = "http://libyy.qfnu.edu.cn/api/Seat/confirm"

SERVER_TIME_OFFSET = None

BEIJING_TZ = datetime.timezone(datetime.timedelta(hours=8))


def utc_to_beijing(utc_time):
    return utc_time.astimezone(BEIJING_TZ)


async def get_server_time():
    global SERVER_TIME_OFFSET
    try:
        async with aiohttp.ClientSession() as session:
            headers = {
                "Content-Type": "application/json",
                "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36 Edg/122.0.0.0",
            }

            async with session.options(URL_GET_SEAT, headers=headers, timeout=aiohttp.ClientTimeout(total=10)) as resp:
                if resp.headers.get("Date"):
                    server_time_str = resp.headers["Date"]
                    server_time = datetime.datetime.strptime(server_time_str, "%a, %d %b %Y %H:%M:%S GMT")
                    server_time = server_time.replace(tzinfo=datetime.timezone.utc)
                    local_time = datetime.datetime.now(datetime.timezone.utc)
                    offset = server_time - local_time
                    SERVER_TIME_OFFSET = offset.total_seconds()

                    server_time_beijing = utc_to_beijing(server_time)
                    local_time_beijing = utc_to_beijing(local_time)

                    logger.info(f"服务器时间: {server_time_beijing.strftime('%Y-%m-%d %H:%M:%S.%f')[:-3]} (北京时间)")
                    logger.info(f"本地时间: {local_time_beijing.strftime('%Y-%m-%d %H:%M:%S.%f')[:-3]} (北京时间)")
                    logger.info(f"时间差: {offset.total_seconds():.3f} 秒 (正值=本地比服务器快)")
                    return offset
    except Exception as e:
        logger.error(f"获取服务器时间失败: {e}")

    try:
        async with aiohttp.ClientSession() as session:
            headers = {
                "Content-Type": "application/json",
                "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36 Edg/122.0.0.0",
            }

            async with session.get(URL_GET_SEAT, headers=headers, timeout=aiohttp.ClientTimeout(total=10)) as resp:
                if resp.headers.get("Date"):
                    server_time_str = resp.headers["Date"]
                    server_time = datetime.datetime.strptime(server_time_str, "%a, %d %b %Y %H:%M:%S GMT")
                    server_time = server_time.replace(tzinfo=datetime.timezone.utc)
                    local_time = datetime.datetime.now(datetime.timezone.utc)
                    offset = server_time - local_time
                    SERVER_TIME_OFFSET = offset.total_seconds()

                    server_time_beijing = utc_to_beijing(server_time)
                    local_time_beijing = utc_to_beijing(local_time)

                    logger.info(f"服务器时间: {server_time_beijing.strftime('%Y-%m-%d %H:%M:%S.%f')[:-3]} (北京时间)")
                    logger.info(f"本地时间: {local_time_beijing.strftime('%Y-%m-%d %H:%M:%S.%f')[:-3]} (北京时间)")
                    logger.info(f"时间差: {offset.total_seconds():.3f} 秒 (正值=本地比服务器快)")
                    return offset
    except Exception as e:
        logger.error(f"获取服务器时间失败: {e}")
        return None


def get_server_time_sync():
    return asyncio.run(get_server_time())


def get_adjusted_target_time(target_hour=19, target_min=20, target_sec=0, 提前毫秒=80):
    global SERVER_TIME_OFFSET

    if SERVER_TIME_OFFSET is None:
        get_server_time_sync()

    local_now = datetime.datetime.now()
    target_time = local_now.replace(hour=target_hour, minute=target_min, second=target_sec, microsecond=0)

    if local_now > target_time:
        target_time = target_time + datetime.timedelta(days=1)

    adjusted_time = target_time - datetime.timedelta(milliseconds=提前毫秒) - datetime.timedelta(seconds=SERVER_TIME_OFFSET)

    target_time_beijing = datetime.datetime(target_time.year, target_time.month, target_time.day,
                                            target_time.hour, target_time.minute, target_time.second,
                                            tzinfo=BEIJING_TZ)
    adjusted_time_beijing = datetime.datetime(adjusted_time.year, adjusted_time.month, adjusted_time.day,
                                               adjusted_time.hour, adjusted_time.minute, adjusted_time.second,
                                               adjusted_time.microsecond, tzinfo=BEIJING_TZ)

    logger.info(f"目标时间: {target_time_beijing.strftime('%Y-%m-%d %H:%M:%S.%f')[:-3]} (北京时间)")
    logger.info(f"服务器偏移: {SERVER_TIME_OFFSET:.3f} 秒")
    logger.info(f"调整后触发时间: {adjusted_time_beijing.strftime('%Y-%m-%d %H:%M:%S.%f')[:-3]} (北京时间)")

    return adjusted_time


def get_server_time_offset():
    return SERVER_TIME_OFFSET


if __name__ == "__main__":
    print("=" * 60)
    print("获取服务器时间...")
    print("=" * 60)
    offset = get_server_time_sync()

    if offset is not None:
        print("\n" + "=" * 60)
        print("分析结果：")
        print("=" * 60)
        offset_seconds = offset.total_seconds()
        if abs(offset_seconds) < 0.5:
            print("✓ 本地时间与服务器时间几乎同步")
        elif offset_seconds > 0:
            print(f"⚠ 本地时间比服务器时间快 {offset_seconds:.3f} 秒")
            print("  抢座时应提前这么久触发请求")
        else:
            print(f"⚠ 本地时间比服务器时间慢 {abs(offset_seconds):.3f} 秒")
            print("  抢座时应延后这么久触发请求")

    print("\n" + "=" * 60)
    print("计算调整后的目标时间 (北京时间 19:20:00 开放预约)...")
    print("=" * 60)
    get_adjusted_target_time()