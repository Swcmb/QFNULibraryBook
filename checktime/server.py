import asyncio
import datetime
import logging
import os
from aiohttp import web

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

BEIJING_TZ = datetime.timezone(datetime.timedelta(hours=8))
URL_GET_SEAT = "http://libyy.qfnu.edu.cn/api/Seat/confirm"

MAX_SAMPLES = 30

offset_history = []
max_offset = None
min_offset = None


def utc_to_beijing(utc_time):
    return utc_time.astimezone(BEIJING_TZ)


async def get_server_time():
    global offset_history, max_offset, min_offset

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

                    offset_history.append(offset)
                    if len(offset_history) > MAX_SAMPLES:
                        offset_history.pop(0)

                    if max_offset is None or offset > max_offset:
                        max_offset = offset
                    if min_offset is None or offset < min_offset:
                        min_offset = offset

                    avg_offset = sum(offset_history) / len(offset_history)

                    server_beijing = utc_to_beijing(server_time)
                    local_beijing = utc_to_beijing(local_time)

                    return {
                        "local_beijing": local_beijing.strftime("%Y-%m-%d %H:%M:%S.%f")[:-3],
                        "local_utc": local_time.strftime("%Y-%m-%d %H:%M:%S.%f")[:-3],
                        "server_beijing": server_beijing.strftime("%Y-%m-%d %H:%M:%S.%f")[:-3],
                        "server_utc": server_time.strftime("%Y-%m-%d %H:%M:%S.%f")[:-3],
                        "offset": offset,
                        "offset_str": f"{offset:+.3f}s",
                        "avg_offset": avg_offset,
                        "avg_offset_str": f"{avg_offset:+.3f}s",
                        "count": len(offset_history),
                        "max_offset": max_offset,
                        "max_offset_str": f"{max_offset:+.3f}s",
                        "min_offset": min_offset,
                        "min_offset_str": f"{min_offset:+.3f}s"
                    }
    except Exception as e:
        logger.error(f"获取失败: {e}")
    return None


async def api_time(request):
    data = await get_server_time()
    if data:
        return web.json_response(data)
    return web.json_response({"error": "获取失败"}, status=500)


async def index(request):
    path = os.path.join(os.path.dirname(__file__), 'index.html')
    return web.FileResponse(path)


async def init_app():
    app = web.Application()
    app.router.add_get('/api/time', api_time)
    app.router.add_get('/', index)
    return app


if __name__ == '__main__':
    import aiohttp
    app = init_app()
    web.run_app(app, host='0.0.0.0', port=8000)