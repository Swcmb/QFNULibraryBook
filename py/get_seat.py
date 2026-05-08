import asyncio
import datetime
import json
import logging
import os
import sys
import time

import aiohttp
import yaml
from telegram import Bot

from get_bearer_token import get_bearer_token
from get_info import get_date, get_segment, get_build_id, encrypt, get_member_seat, classroom_id_mapping

import base64
import hmac
import hashlib
import urllib.parse


logging.basicConfig(level=logging.WARNING)
logger = logging.getLogger(__name__)

URL_GET_SEAT = "http://libyy.qfnu.edu.cn/api/Seat/confirm"
URL_CHECK_OUT = "http://libyy.qfnu.edu.cn/api/Space/checkout"
URL_CANCEL_SEAT = "http://libyy.qfnu.edu.cn/api/Space/cancel"

CHANNEL_ID = ""
TELEGRAM_BOT_TOKEN = ""
MODE = ""
CLASSROOMS_NAME = ""
SEAT_ID = []
DATE = ""
USERNAME = ""
PASSWORD = ""
GITHUB = ""
BARK_URL = ""
BARK_EXTRA = ""
ANPUSH_TOKEN = ""
ANPUSH_CHANNEL = ""
DD_BOT_SECRET = ""
DD_BOT_TOKEN = ""
PUSH_METHOD = ""

TARGET_SEAT_IDS = []
PRIORITY_SEAT_ID = ""
MAX_CONCURRENT_REQUESTS = 10


def read_config_from_yaml():
    global CHANNEL_ID, TELEGRAM_BOT_TOKEN, CLASSROOMS_NAME, MODE, SEAT_ID, DATE, USERNAME, PASSWORD, GITHUB, BARK_EXTRA, BARK_URL, ANPUSH_TOKEN, ANPUSH_CHANNEL, PUSH_METHOD, DD_BOT_TOKEN, DD_BOT_SECRET, TARGET_SEAT_IDS, PRIORITY_SEAT_ID, MAX_CONCURRENT_REQUESTS
    current_dir = os.path.dirname(os.path.abspath(__file__))
    config_file_path = os.path.join(current_dir, "config.yml")
    with open(config_file_path, "r", encoding="utf-8") as yaml_file:
        config = yaml.safe_load(yaml_file)
        CHANNEL_ID = config.get("CHANNEL_ID", "")
        TELEGRAM_BOT_TOKEN = config.get("TELEGRAM_BOT_TOKEN", "")
        CLASSROOMS_NAME = config.get("CLASSROOMS_NAME", [])
        MODE = config.get("MODE", "")
        SEAT_ID = config.get("SEAT_ID", [])
        DATE = config.get("DATE", "")
        USERNAME = config.get("USERNAME", "")
        PASSWORD = config.get("PASSWORD", "")
        GITHUB = config.get("GITHUB", "")
        BARK_URL = config.get("BARK_URL", "")
        BARK_EXTRA = config.get("BARK_EXTRA", "")
        ANPUSH_TOKEN = config.get("ANPUSH_TOKEN", "")
        ANPUSH_CHANNEL = config.get("ANPUSH_CHANNEL", "")
        DD_BOT_TOKEN = config.get("DD_BOT_TOKEN", "")
        DD_BOT_SECRET = config.get("DD_BOT_SECRET", "")
        PUSH_METHOD = config.get("PUSH_METHOD", "")
        
        TARGET_SEAT_IDS = config.get("TARGET_SEAT_IDS", ["228", "216", "204", "192"])
        PRIORITY_SEAT_ID = config.get("PRIORITY_SEAT_ID", "228")
        MAX_CONCURRENT_REQUESTS = config.get("MAX_CONCURRENT_REQUESTS", 10)


FLAG = False
SEAT_RESULT = {}
USED_SEAT = []
MESSAGE = ""
AUTH_TOKEN = ""
NEW_DATE = ""
TOKEN_TIMESTAMP = None
TOKEN_EXPIRY_DELTA = datetime.timedelta(hours=1, minutes=30)


def dingtalk(text, desp, DD_BOT_TOKEN, DD_BOT_SECRET=None):
    url = f"https://oapi.dingtalk.com/robot/send?access_token={DD_BOT_TOKEN}"
    headers = {"Content-Type": "application/json"}
    payload = {"msgtype": "text", "text": {"content": f"{text}\n{desp}"}}

    if DD_BOT_TOKEN and DD_BOT_SECRET:
        timestamp = str(round(time.time() * 1000))
        secret_enc = DD_BOT_SECRET.encode("utf-8")
        string_to_sign = f"{timestamp}\n{DD_BOT_SECRET}"
        string_to_sign_enc = string_to_sign.encode("utf-8")
        hmac_code = hmac.new(secret_enc, string_to_sign_enc, digestmod=hashlib.sha256).digest()
        sign = urllib.parse.quote_plus(base64.b64encode(hmac_code).decode("utf-8").strip())
        url = f"{url}&timestamp={timestamp}&sign={sign}"

    response = requests.post(url, headers=headers, data=json.dumps(payload))

    try:
        data = response.json()
        if response.status_code == 200 and data.get("errcode") == 0:
            logger.info("钉钉发送通知消息成功")
        else:
            logger.error(f"钉钉发送通知消息失败\n{data.get('errmsg')}")
    except Exception as e:
        logger.error(f"钉钉发送通知消息失败\n{e}")

    return response.json()


def send_message_bark():
    try:
        import requests
        response = requests.get(BARK_URL + MESSAGE + BARK_EXTRA)
        if response.status_code == 200:
            logger.info("成功推送消息到 Bark")
            return response.text
        else:
            logger.error(f"推送到 Bark 的 GET请求失败，状态码：{response.status_code}")
            return None
    except requests.exceptions.RequestException:
        logger.info("GET请求异常, 你的 BARK 链接不正确")
        return None


def send_message_anpush():
    import requests
    url = "https://api.anpush.com/push/" + ANPUSH_TOKEN
    payload = {"title": "预约通知", "content": MESSAGE, "channel": ANPUSH_CHANNEL}
    headers = {"Content-Type": "application/x-www-form-urlencoded"}
    requests.post(url, headers=headers, data=payload)


async def send_message_telegram():
    try:
        bot = Bot(token=TELEGRAM_BOT_TOKEN)
        await bot.send_message(chat_id=CHANNEL_ID, text=MESSAGE)
        logger.info("成功推送消息到 Telegram")
    except Exception as e:
        logger.info(f"发送消息到 Telegram 失败")
        return e


def send_message():
    if PUSH_METHOD == "TG":
        asyncio.run(send_message_telegram())
    if PUSH_METHOD == "ANPUSH":
        send_message_anpush()
    if PUSH_METHOD == "BARK":
        send_message_bark()
    if PUSH_METHOD == "DD":
        dingtalk(f"脚本执行通知 - 学号: {USERNAME}", MESSAGE, DD_BOT_TOKEN, DD_BOT_SECRET)


def get_auth_token():
    global TOKEN_TIMESTAMP, AUTH_TOKEN, MESSAGE
    try:
        if not USERNAME or not PASSWORD:
            raise ValueError("未找到用户名或密码")

        if TOKEN_TIMESTAMP is None or (datetime.datetime.now() - TOKEN_TIMESTAMP) > TOKEN_EXPIRY_DELTA:
            name, token = get_bearer_token(USERNAME, PASSWORD)
            if token is None:
                logging.error("获取 token 失败，账号密码错误或者网络错误。")
                MESSAGE += "\n获取 token 失败，账号密码错误或者网络错误。"
                send_message()
                sys.exit()
            else:
                logger.info("成功获取授权码")
                AUTH_TOKEN = "bearer" + str(token)
                TOKEN_TIMESTAMP = datetime.datetime.now()
        else:
            logger.info("使用现有授权码")
    except Exception as e:
        logger.error(f"获取授权码时发生异常: {str(e)}")
        sys.exit()


def check_book_seat():
    global MESSAGE, FLAG
    try:
        res = get_member_seat(AUTH_TOKEN)
        if res is not None and "msg" in res and res["msg"] == "您尚未登录":
            get_auth_token()
        if res is not None and "data" in res:
            for entry in res["data"]["data"]:
                if entry["statusName"] == "预约成功":
                    seat_id = entry["name"]
                    name = entry["nameMerge"]
                    logger.info(f"预约成功：你当前的座位是 {name} {seat_id}")
                    FLAG = True
                    MESSAGE += f"\n预约成功：你当前的座位是 {name} {seat_id}\n"
                    send_message()
                    break
                elif entry["statusName"] == "使用中" and DATE == "today":
                    logger.info("存在正在使用的座位")
                    FLAG = True
                    break
    except KeyError:
        logger.error("获取个人座位出现错误")


async def async_post(session, url, json_data, headers):
    try:
        async with session.post(url, json=json_data, headers=headers, timeout=aiohttp.ClientTimeout(total=30)) as resp:
            return await resp.json()
    except Exception as e:
        logger.error(f"异步请求异常: {str(e)}")
        return None


async def async_encrypt(text):
    loop = asyncio.get_event_loop()
    return await loop.run_in_executor(None, encrypt, text)


async def async_post_to_get_seat(session, select_id, segment, auth_token):
    origin_data = '{{"seat_id":"{}","segment":"{}"}}'.format(select_id, segment)
    aes_data = await async_encrypt(str(origin_data))
    
    post_data = {"aesjson": aes_data}
    request_headers = {
        "Content-Type": "application/json",
        "Connection": "keep-alive",
        "Accept": "application/json, text/plain, */*",
        "lang": "zh",
        "X-Requested-With": "XMLHttpRequest",
        "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36 Edg/122.0.0.0",
        "Origin": "http://libyy.qfnu.edu.cn",
        "Referer": "http://libyy.qfnu.edu.cn/h5/index.html",
        "Accept-Encoding": "gzip, deflate",
        "Accept-Language": "zh-CN,zh;q=0.9,en;q=0.8,en-GB;q=0.7,en-US;q=0.6,pl;q=0.5",
        "Authorization": auth_token,
    }
    
    return await async_post(session, URL_GET_SEAT, post_data, request_headers)


async def precise_sleep(target_time):
    now = datetime.datetime.now()
    delta = (target_time - now).total_seconds()
    
    if delta > 2:
        await asyncio.sleep(delta - 1)
        now = datetime.datetime.now()
        delta = (target_time - now).total_seconds()
    
    if delta > 0.05:
        await asyncio.sleep(delta - 0.02)
    
    while datetime.datetime.now() < target_time:
        pass


async def select_seat_concurrent(build_id, segment, nowday):
    global MESSAGE, FLAG
    
    async with aiohttp.ClientSession(connector=aiohttp.TCPConnector(limit=200)) as session:
        while not FLAG:
            tasks = []
            
            if PRIORITY_SEAT_ID and PRIORITY_SEAT_ID in TARGET_SEAT_IDS:
                for _ in range(5):
                    tasks.append(asyncio.create_task(async_post_to_get_seat(session, PRIORITY_SEAT_ID, segment, AUTH_TOKEN)))
            
            for seat_id in TARGET_SEAT_IDS:
                if seat_id != PRIORITY_SEAT_ID:
                    for _ in range(10):
                        tasks.append(asyncio.create_task(async_post_to_get_seat(session, seat_id, segment, AUTH_TOKEN)))
            
            completed, pending = await asyncio.wait(tasks, return_when=asyncio.FIRST_COMPLETED)
            
            for task in completed:
                try:
                    result = task.result()
                    if result is None:
                        continue
                    if isinstance(result, dict) and "msg" in result:
                        if result["msg"] == "预约成功":
                            for p in pending:
                                p.cancel()
                            
                            FLAG = True
                            logger.info(f"座位预约成功")
                            MESSAGE += "\n座位预约成功\n"
                            check_book_seat()
                            send_message()
                            return
                        elif result["msg"] == "当前用户在该时段已存在座位预约，不可重复预约":
                            for p in pending:
                                p.cancel()
                            
                            FLAG = True
                            logger.info("已存在预约")
                            check_book_seat()
                            send_message()
                            return
                except asyncio.CancelledError:
                    pass
                except Exception as e:
                    logger.error(f"处理结果时异常: {str(e)}")
            
            for p in pending:
                p.cancel()


async def get_info_and_select_seat():
    global AUTH_TOKEN, NEW_DATE, MESSAGE
    try:
        NEW_DATE = get_date(DATE)
        get_auth_token()
        
        for i in CLASSROOMS_NAME:
            build_id = get_build_id(i)
            if build_id != 22:
                logger.info("当前只支持东校区图书馆-三层自习室")
                continue
            
            segment = get_segment(build_id, NEW_DATE)
            
            target_time = datetime.datetime.now().replace(hour=19, minute=20, second=0, microsecond=0)
            if datetime.datetime.now() > target_time:
                target_time = target_time + datetime.timedelta(days=1)
            
            logger.info(f"等待到 {target_time} 开始抢座...")
            
            await precise_sleep(target_time - datetime.timedelta(milliseconds=80))
            
            await select_seat_concurrent(build_id, segment, NEW_DATE)

    except KeyboardInterrupt:
        logger.info("主动退出程序")


if __name__ == "__main__":
    try:
        read_config_from_yaml()
        asyncio.run(get_info_and_select_seat())
    except KeyboardInterrupt:
        logger.info("主动退出程序")