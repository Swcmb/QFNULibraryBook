import asyncio
import datetime
import logging
import time
from statistics import mean, stdev

import aiohttp

logging.basicConfig(level=logging.INFO, format='%(message)s')
logger = logging.getLogger(__name__)

TARGET_HOST = "libyy.qfnu.edu.cn"
URL_GET_SEAT = "http://libyy.qfnu.edu.cn/api/Seat/confirm"
URL_CAS = "http://ids.qfnu.edu.cn/authserver/login"

BEIJING_TZ = datetime.timezone(datetime.timedelta(hours=8))


def format_time(dt):
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=datetime.timezone.utc)
    beijing = dt.astimezone(BEIJING_TZ)
    return beijing.strftime("%Y-%m-%d %H:%M:%S.%f")[:-3]


async def tcp_connect_test(host, port=80, count=10):
    results = []
    logger.info(f"\n=== TCP 连接测试 ({host}:{port}) ===")
    
    for i in range(count):
        start = time.perf_counter()
        try:
            reader, writer = await asyncio.wait_for(
                asyncio.open_connection(host, port),
                timeout=5.0
            )
            writer.close()
            await writer.wait_closed()
            elapsed = (time.perf_counter() - start) * 1000
            results.append(elapsed)
            logger.info(f"TCP连接 #{i+1}: {elapsed:.2f} ms")
        except asyncio.TimeoutError:
            logger.info(f"TCP连接 #{i+1}: 超时")
            results.append(None)
        except Exception as e:
            logger.info(f"TCP连接 #{i+1}: 失败 - {e}")
            results.append(None)
    
    successes = [r for r in results if r is not None]
    if successes:
        logger.info(f"\nTCP连接统计:")
        logger.info(f"  成功次数: {len(successes)}/{count}")
        logger.info(f"  最小延迟: {min(successes):.2f} ms")
        logger.info(f"  最大延迟: {max(successes):.2f} ms")
        logger.info(f"  平均延迟: {mean(successes):.2f} ms")
        logger.info(f"  标准差: {stdev(successes):.2f} ms")
    
    return successes


async def http_request_test(url, count=10):
    results = []
    connect_times = []
    tls_times = []
    logger.info(f"\n=== HTTP 请求测试 ({url}) ===")
    
    async with aiohttp.ClientSession() as session:
        for i in range(count):
            start = time.perf_counter()
            try:
                async with session.get(url, timeout=aiohttp.ClientTimeout(total=10)) as resp:
                    await resp.text()
                    elapsed = (time.perf_counter() - start) * 1000
                    results.append(elapsed)
                    
                    if hasattr(resp, 'timing') and resp.timing:
                        connect_time = resp.timing.connect * 1000
                        tls_time = (resp.timing.tls_handshake or 0) * 1000
                        connect_times.append(connect_time)
                        tls_times.append(tls_time)
                    
                    logger.info(f"HTTP请求 #{i+1}: {elapsed:.2f} ms")
            except asyncio.TimeoutError:
                logger.info(f"HTTP请求 #{i+1}: 超时")
                results.append(None)
            except Exception as e:
                logger.info(f"HTTP请求 #{i+1}: 失败 - {e}")
                results.append(None)
    
    successes = [r for r in results if r is not None]
    if successes:
        logger.info(f"\nHTTP请求统计:")
        logger.info(f"  成功次数: {len(successes)}/{count}")
        logger.info(f"  最小延迟: {min(successes):.2f} ms")
        logger.info(f"  最大延迟: {max(successes):.2f} ms")
        logger.info(f"  平均延迟: {mean(successes):.2f} ms")
        logger.info(f"  标准差: {stdev(successes):.2f} ms")
        
        if connect_times:
            logger.info(f"  TCP连接时间: {mean(connect_times):.2f} ± {stdev(connect_times):.2f} ms")
        if tls_times and any(t > 0 for t in tls_times):
            logger.info(f"  TLS握手时间: {mean([t for t in tls_times if t > 0]):.2f} ms")
    
    return successes


async def server_time_sync_test(count=30):
    offsets = []
    logger.info(f"\n=== 服务器时间同步测试 ({count}次采样) ===")
    
    async with aiohttp.ClientSession() as session:
        headers = {
            "Content-Type": "application/json",
            "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36",
        }
        
        for i in range(count):
            try:
                async with session.get(URL_GET_SEAT, headers=headers, timeout=aiohttp.ClientTimeout(total=5)) as resp:
                    if resp.headers.get("Date"):
                        server_time_str = resp.headers["Date"]
                        server_time = datetime.datetime.strptime(server_time_str, "%a, %d %b %Y %H:%M:%S %Z")
                        server_time = server_time.replace(tzinfo=datetime.timezone.utc)
                        local_time = datetime.datetime.now(datetime.timezone.utc)
                        offset = (server_time - local_time).total_seconds()
                        offsets.append(offset)
                        logger.info(f"时间采样 #{i+1}: 偏移 {offset:+.3f} 秒")
                    else:
                        logger.info(f"时间采样 #{i+1}: 无法获取服务器时间")
            except Exception as e:
                logger.info(f"时间采样 #{i+1}: 失败 - {e}")
            
            await asyncio.sleep(0.5)
    
    if offsets:
        logger.info(f"\n时间同步统计:")
        logger.info(f"  采样次数: {len(offsets)}")
        logger.info(f"  平均偏移: {mean(offsets):+.3f} 秒")
        logger.info(f"  最大偏移: {max(offsets):+.3f} 秒")
        logger.info(f"  最小偏移: {min(offsets):+.3f} 秒")
        logger.info(f"  波动范围: {max(offsets) - min(offsets):.3f} 秒")
        
        if abs(mean(offsets)) > 1:
            logger.warning("  ⚠️ 警告：时间偏移超过1秒，可能影响抢座准确性！")
        else:
            logger.info("  ✅ 时间同步良好，适合抢座")
    
    return offsets


async def main():
    logger.info("="*60)
    logger.info("网络性能检测工具 - libyy.qfnu.edu.cn")
    logger.info("="*60)
    logger.info(f"检测时间: {format_time(datetime.datetime.now())}")
    logger.info(f"目标服务器: {TARGET_HOST}")
    logger.info("="*60)
    
    await tcp_connect_test(TARGET_HOST, port=80, count=10)
    await http_request_test(URL_GET_SEAT, count=10)
    await http_request_test(URL_CAS, count=5)
    await server_time_sync_test(count=30)
    
    logger.info("\n" + "="*60)
    logger.info("检测完成！")
    logger.info("="*60)


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        logger.info("\n检测已停止")
