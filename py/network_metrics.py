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


async def measure_rtt(count=20):
    rtts = []
    logger.info(f"\n=== 往返时延 (RTT) 测试 ({count}次) ===")
    
    async with aiohttp.ClientSession() as session:
        headers = {
            "Content-Type": "application/json",
            "User-Agent": "Mozilla/5.0",
        }
        
        for i in range(count):
            start = time.perf_counter()
            try:
                async with session.get(URL_GET_SEAT, headers=headers, timeout=aiohttp.ClientTimeout(total=5)) as resp:
                    await resp.text()
                    elapsed = (time.perf_counter() - start) * 1000
                    rtts.append(elapsed)
                    logger.info(f"RTT #{i+1}: {elapsed:.2f} ms")
            except Exception as e:
                logger.info(f"RTT #{i+1}: 失败 - {e}")
    
    if rtts:
        avg_rtt = mean(rtts)
        logger.info(f"\n往返时延统计:")
        logger.info(f"  最小 RTT: {min(rtts):.2f} ms")
        logger.info(f"  最大 RTT: {max(rtts):.2f} ms")
        logger.info(f"  平均 RTT: {avg_rtt:.2f} ms")
        logger.info(f"  标准差: {stdev(rtts):.2f} ms")
        return avg_rtt
    return None


async def measure_bandwidth(url, timeout=30):
    logger.info(f"\n=== 带宽测试 ===")
    
    async with aiohttp.ClientSession() as session:
        try:
            start = time.perf_counter()
            async with session.get(url, timeout=aiohttp.ClientTimeout(total=timeout)) as resp:
                data = await resp.read()
                elapsed = time.perf_counter() - start
                
                file_size = len(data)
                speed_bps = (file_size * 8) / elapsed
                speed_mbps = speed_bps / 1_000_000
                speed_mb_s = file_size / (1_000_000 * elapsed)
                
                logger.info(f"下载大小: {file_size / 1024:.2f} KB")
                logger.info(f"下载时间: {elapsed:.2f} 秒")
                logger.info(f"下载速度: {speed_mbps:.2f} Mbps")
                logger.info(f"下载速度: {speed_mb_s:.2f} MB/s")
                
                return speed_mbps
        except Exception as e:
            logger.info(f"带宽测试失败: {e}")
            return None


async def main():
    logger.info("="*60)
    logger.info("网络性能指标测试")
    logger.info("="*60)
    logger.info(f"测试时间: {datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    logger.info("="*60)
    
    avg_rtt = await measure_rtt(count=20)
    
    test_file_urls = [
        "http://speedtest.tele2.net/10MB.zip",
        "http://libyy.qfnu.edu.cn/h5/index.html",
    ]
    
    speeds = []
    for url in test_file_urls:
        speed = await measure_bandwidth(url)
        if speed:
            speeds.append(speed)
    
    if speeds:
        avg_speed = mean(speeds)
        logger.info(f"\n平均带宽: {avg_speed:.2f} Mbps")
    else:
        avg_speed = None
        logger.info("\n⚠️ 无法测量带宽")
    
    if avg_rtt and avg_speed:
        bdp_bits = (avg_speed * 1_000_000) * (avg_rtt / 1000)
        bdp_bytes = bdp_bits / 8
        bdp_kb = bdp_bytes / 1024
        
        logger.info(f"\n=== 时延带宽积 (BDP) ===")
        logger.info(f"  带宽: {avg_speed:.2f} Mbps")
        logger.info(f"  往返时延: {avg_rtt:.2f} ms")
        logger.info(f"  BDP (比特): {bdp_bits:.0f} bits")
        logger.info(f"  BDP (字节): {bdp_bytes:.0f} bytes")
        logger.info(f"  BDP (KB): {bdp_kb:.2f} KB")
        
        if bdp_kb < 10:
            logger.info("  ✅ BDP较小，网络响应快")
        elif bdp_kb < 100:
            logger.info("  ⚠️ BDP中等，建议使用较大的TCP窗口")
        else:
            logger.info("  ⚠️ BDP较大，可能影响实时抢座")
    
    logger.info("\n" + "="*60)
    logger.info("测试完成！")
    logger.info("="*60)


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        logger.info("\n测试已停止")
