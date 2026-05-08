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

SERVER_TIME_OFFSET = 0
PREHEAT_DONE = False


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


# 状态检测函数，用来检查响应结果
def check_reservation_status():
    global FLAG, MESSAGE
    # 状态信息检测
    if isinstance(SEAT_RESULT, dict) and "msg" in SEAT_RESULT:
        status = SEAT_RESULT["msg"]
        # logger.info("预约状态：" + str(status))
        if status is not None:
            if status == "当前用户在该时段已存在座位预约，不可重复预约":
                logger.info("重复预约, 请检查选择的时间段或是否已经预约成功")
                check_book_seat()
                FLAG = True
            elif status == "预约成功":
                logger.info("预约成功")
                check_book_seat()
                FLAG = True
            elif status == "开放预约时间19:20":
                logger.info("未到预约时间")
            elif status == "您尚未登录":
                logger.info("没有登录，将重新尝试获取 token")
                get_auth_token()
            elif status == "该空间当前状态不可预约":
                logger.info("此位置已被预约或位置不可用")
            elif status == "取消成功":
                logger.info("取消成功")
                sys.exit()
            else:
                FLAG = True
                logger.info(f"未知状态信息: {status}")
        else:
            return await _fetch_server_time(session)
    except Exception as e:
        logger.error(f"获取服务器时间失败: {str(e)}")
        return SERVER_TIME_OFFSET


async def _fetch_server_time(session):
    global SERVER_TIME_OFFSET
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
            SERVER_TIME_OFFSET = offset
            logger.debug(f"实时校准 - 服务器时间偏移: {offset:+.3f}秒")
            return offset
    return SERVER_TIME_OFFSET


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
    # 发送POST请求并获取响应
    SEAT_RESULT = send_post_request_and_save_response(URL_GET_SEAT, post_data, request_headers)
    check_reservation_status()


# 随机获取座位
def random_get_seat(data):
    global MESSAGE
    # 随机选择一个字典
    random_dict = random.choice(data)
    # 获取该字典中 'id' 键对应的值
    select_id = random_dict["id"]
    # seat_no = random_dict['no']
    # logger.info(f"随机选择的座位为: {select_id} 真实位置: {seat_no}")
    return select_id


# 选座主要逻辑
def select_seat(build_id, segment, nowday):
    global MESSAGE, FLAG
    retries = 0  # 添加重试计数器

    while not FLAG and retries < 100:
        logger.info(f"开始第 {retries+1} 次尝试获取座位")
        retries += 1

        # 获取空闲位置
        data = get_seat_info(build_id, segment, nowday)
        # print(f'info:   空闲位置: {data}, {len(data)}')

        if not data:
            logger.warning("获取座位信息失败，可能是时间段内不存在或该区域暂不可用")

            for key, value in classroom_id_mapping.items():
                if value == build_id:
                    classname = key
                    break
            MESSAGE += f"\n[{classname}]: 获取座位信息失败，可能是时间段内不存在或该区域暂不可用"
            # send_message()
            break
            # sys.exit()
        else:
            # 模式 1: 选择指定范围内有插座的位置
            if MODE == '1':
                seat_id_range = []
                for ran in SEAT_ID:
                    seat_id_range.extend(list(map(str, list(range(ran[0], ran[1]+1)))))
                
                # 位置筛选条件
                new_data = [d for d in data if (d["id"] not in EXCLUDE_ID) and (d['id'] in seat_id_range)]
                # print(f'info:   位置范围: {seat_id_range}')
                # print(f'info:   指定范围内有插座位置: {new_data}')
                # break

                if new_data:
                    select_id = random_get_seat(new_data)
                    logger.info(f"随机选择的座位为: {select_id}")
                    post_to_get_seat(select_id, segment)
                continue
            # 模式 2: 选择有插座的位置
            elif MODE == '2':
                # 位置筛选条件
                new_data = [d for d in data if d["id"] not in EXCLUDE_ID]
                if new_data:
                    select_id = random_get_seat(new_data)
                    logger.info(f"随机选择的座位为: {select_id}")
                    post_to_get_seat(select_id, segment)
                continue
            # 模式 3: 随机选择
            elif MODE == '3':
                select_id = random_get_seat(data)
                logger.info(f"随机选择的座位为: {select_id}")
                post_to_get_seat(select_id, segment)
                continue
            # 模式 4: 东校区图书馆三层自习室指定座位优先
            elif MODE == '4':
                # 东校区图书馆三层自习室的build_id是22
                if build_id != 22:
                    logger.info("模式4只适用于东校区图书馆三层自习室，跳过当前教室")
                    continue
                
                # 调试：打印实际返回的座位信息
                if data:
                    logger.info(f"调试: 实际返回的前5个座位: {data[:5]}")
                
                # 合并所有指定座位列表
                target_seats = ['228']
                # 合并所有优先座位列表
                priority_seats = ['228']
                
                # 筛选出在指定座位列表中的空闲座位（根据no字段，去除前导零进行比较）
                available_target_seats = []
                for seat in data:
                    # 去除no字段的前导零
                    seat_no = seat['no'].lstrip('0')
                    # 如果去除前导零后为空，则表示是0号座位
                    if not seat_no:
                        seat_no = '0'
                    if seat_no in target_seats:
                        available_target_seats.append(seat)
                
                # 调试：打印筛选结果
                logger.info(f"调试: 可用座位数量: {len(data)}, 符合条件的座位数量: {len(available_target_seats)}")
                if available_target_seats:
                    logger.info(f"调试: 符合条件的座位: {[(seat['id'], seat['no']) for seat in available_target_seats]}")
                
                if available_target_seats:
                    # 优先选择优先座位列表中的座位
                    priority_available = []
                    for seat in available_target_seats:
                        # 去除no字段的前导零
                        seat_no = seat['no'].lstrip('0')
                        if not seat_no:
                            seat_no = '0'
                        if seat_no in priority_seats:
                            priority_available.append(seat)
                    
                    if priority_available:
                        # 随机选择一个优先座位
                        selected_seat = random.choice(priority_available)
                        select_id = selected_seat["id"]
                        logger.info(f"优先选择的座位为: {selected_seat['no']} (系统ID: {select_id})")
                    else:
                        # 没有优先座位时，从指定座位中随机选择
                        selected_seat = random.choice(available_target_seats)
                        select_id = selected_seat["id"]
                        logger.info(f"从指定座位中选择的座位为: {selected_seat['no']} (系统ID: {select_id})")
                    post_to_get_seat(select_id, segment)
                else:
                    logger.info("指定座位列表中无可用座位，立即重试")
                continue
            else:
                logger.error(f"未知的模式: {MODE}")
                break
        
        if delta > 5:
            await asyncio.sleep(delta - 5)
            if enable_realtime_calibration and session:
                await get_server_time_offset(session)
        
        now = datetime.datetime.now()
        delta = (target_time - now).total_seconds()
    
    if delta > 0.1:
        await asyncio.sleep(delta - 0.03)
        if enable_realtime_calibration and session:
            await get_server_time_offset(session)
    
    while datetime.datetime.now() < target_time:
        pass


async def preheat_requests(session, segment, auth_token):
    global FLAG, PREHEAT_DONE, MESSAGE
    logger.info("开始预热请求...")
    
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
    
    while not PREHEAT_DONE and not FLAG:
        try:
            origin_data = '{{"seat_id":"{}","segment":"{}"}}'.format(PRIORITY_SEAT_ID, segment)
            aes_data = await async_encrypt(str(origin_data))
            post_data = {"aesjson": aes_data}
            

    # 如果超过最大重试次数仍然没有获取到座位,则退出程序
    if retries >= 1000:
        logger.error("超过最大重试次数,无法获取座位")
        MESSAGE += "\n超过最大重试次数,无法获取座位"
        send_message()
        sys.exit()


def check_time():
    global MESSAGE
    get_info_and_select_seat()


# 主函数
def get_info_and_select_seat():
    global AUTH_TOKEN, NEW_DATE, MESSAGE
    try:
        NEW_DATE = get_date(DATE)
        get_auth_token()
        
        await get_server_time_offset()
        
        for i in CLASSROOMS_NAME:
            build_id = get_build_id(i)
            if build_id != 22:
                logger.info("当前只支持东校区图书馆-三层自习室")
                continue
            
            segment = get_segment(build_id, NEW_DATE)
            
            await select_seat_concurrent(build_id, segment, NEW_DATE)

    except KeyboardInterrupt:
        logger.info("主动退出程序")


if __name__ == "__main__":
    try:
        read_config_from_yaml()
        asyncio.run(get_info_and_select_seat())
    except KeyboardInterrupt:
        logger.info("主动退出程序")