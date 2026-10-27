"""
图书馆座位预约脚本
用法: python get_seat.py [-c configs/studentA.yml]
"""
import os
import time
import random
import argparse
import logging
import queue
import threading
from datetime import datetime

from config.config import AppConfig
from auth.token import TokenManager, AuthenticationError
from notify.notify import send_message
from api.constants import URL_GET_SEAT, URL_CLASSROOM_SEAT, DEFAULT_HEADERS
from api.http import post_with_retry, RequestFailed
from api.exceptions import ReservationFailed
from crypto.aes import encrypt_seat_data
from classrooms import classroom_id_mapping, EXCLUDE_ID
from get_info import get_date, get_seat_info, get_segment, get_build_id, get_member_seat

logger = logging.getLogger(__name__)

# ── 服务端限流的实测结论（2026-10-19 在 /api/Seat/confirm 上实测）──────────────
# 归属：按账号（Bearer Token）计数，同一出口 IP 的其他账号不受影响。
# 额度：2 秒滑动窗口内最多 3 发。背靠背第 4 发、0.5s 间隔第 4 发均触发惩罚；
#       0.8s 间隔 8 发、1.0s 间隔 8 发、2.0s 间隔 10 发全部正常。
# 惩罚：code=-7 "访问频繁，请5分钟后重试"，响应掉到 ~60ms，持续 5 分钟。
#       一旦触发，当晚这个座位必然抢不到，所以余量优先于速度。
# 免计数：/api/Seat/seat（可用性查询）不吃 confirm 额度，实测连发 10 发后
#       confirm 仍正常，因此预热和轮询座位表可以自由使用它。
CONFIRM_WINDOW = 3.0   # 对实测 2.0s 边界留一档余量
CONFIRM_CAP = 3        # 窗口内允许的发数（放座瞬间的三连发正好用满额度）
STEADY_GAP = 1.0       # 稳态最小发间隔，实测 1.0s 均匀节奏安全
BURST_SECONDS = 8.0    # 放座后这么多秒内不做额外等待，把窗口额度全部用在争夺上
BURST_SENDS = 3        # 放座瞬间并发打满一个窗口的额度
BURST_GAP = 0.75       # 三连发的发间隔：0/0.75/1.5s 仍在同一个 2s 额度窗口内
BURST_DRAIN = 3.0      # 等待三连发响应的时长，超时不再等，交给稳态循环
PROBE_GAP = 1.2        # 已到本机放座时刻但服务端窗口仍未开时的降频探测间隔
WARM_GAP = 2.0         # 放座前预热的发间隔
RELEASE_HOUR, RELEASE_MIN = 19, 20   # 服务端放座时刻（响应文案"开放预约时间19:20"）
QUIET_BEFORE_RELEASE = 3.5           # 放座前静默，保证那一刻窗口内 0 发、额度全满


class ConfirmPacer:
    """把 /api/Seat/confirm 限制在「每窗口最多 CAP 发」内，超线时等窗口腾出名额。

    放座瞬间的三连发由多个线程同时调用 wait()，计数必须加锁，
    否则并发下可能一起放行，越过服务端的额度线。
    """

    def __init__(self):
        self._sent = []
        self._lock = threading.Lock()

    def last_sent(self):
        """最近一次放行的发送时刻；从未发送过则返回 0（视为可立即发送）。"""
        with self._lock:
            return self._sent[-1] if self._sent else 0.0

    def wait(self):
        while True:
            with self._lock:
                now = time.time()
                self._sent = [t for t in self._sent if now - t < CONFIRM_WINDOW]
                if len(self._sent) < CONFIRM_CAP:
                    self._sent.append(now)
                    return
                delay = CONFIRM_WINDOW - (now - self._sent[0]) + 0.05
            time.sleep(delay)


_pacer = ConfirmPacer()


def release_epoch(date_cfg):
    """返回本次抢座对应放座时刻的 epoch；不在窗口前则返回 None。"""
    if date_cfg != "tomorrow":
        return None
    now = datetime.now()
    release = now.replace(hour=RELEASE_HOUR, minute=RELEASE_MIN, second=0,
                           microsecond=0)
    if now >= release:
        return None
    return release.timestamp()


def check_book_seat(config, token_mgr, messages, auth_token):
    """检查是否存在已预约的座位，返回 True 表示已有座位"""
    try:
        res = get_member_seat(auth_token)
        if res is not None and "msg" in res and res["msg"] == "您尚未登录":
            auth_token = token_mgr.get_token()
        if res is not None and "data" in res:
            for entry in res["data"]["data"]:
                if entry["statusName"] == "预约成功":
                    seat_id = entry["name"]
                    name = entry["nameMerge"]
                    logger.info(f"预约成功：你当前的座位是 {name} {seat_id}")
                    messages.append(f"\n预约成功：你当前的座位是 {name} {seat_id}\n")
                    return True
                elif entry["statusName"] == "使用中" and config.date == "today":
                    logger.info("存在正在使用的座位")
                    return True
    except KeyError:
        logger.error("获取个人座位出现错误")
    return False


def check_reservation_status(seat_result, config, token_mgr, messages, gate=None):
    """
    状态检测函数。
    返回: True 表示已完成（成功/失败），False 表示需继续尝试
    gate: 可选的 {'open': bool}，标记服务端放座窗口是否已经真的打开。
          两台服务器时钟只有 ±1s 的同步把握（2026-10-19 用 HTTP Date 头实测，
          秒级精度无法压得更细），所以不能假定放座发生在本机 19:20:00.000，
          需要这个信号决定额度是继续留着探测、还是立即全部打出。

          只有明确证明"已过时间闸门"的业务状态才置真：
            预约成功 / 该空间当前状态不可预约 / 已存在座位预约
          实测依据（2026-10-18 日志）：放座前一律回"开放预约时间19:20"，
          放座后同一座位回"该空间当前状态不可预约"，两者互斥，可作开闸凭证。
          "您尚未登录"和未知状态对窗口毫无信息量，若误判为已开，
          会把三连发额度白烧在仍然关闭的窗口上，因此一律不置真。
    """
    GATE_OPEN_MESSAGES = (
        "预约成功",
        "该空间当前状态不可预约",
        "当前用户在该时段已存在座位预约，不可重复预约",
    )
    if isinstance(seat_result, dict) and "msg" in seat_result:
        status = seat_result["msg"]
        if status is not None:
            if gate is not None and status in GATE_OPEN_MESSAGES:
                gate['open'] = True
            if status == "当前用户在该时段已存在座位预约，不可重复预约":
                logger.info("重复预约, 请检查选择的时间段或是否已经预约成功")
                check_book_seat(config, token_mgr, messages, token_mgr.get_token())
                return True
            elif status == "预约成功":
                logger.info("预约成功")
                check_book_seat(config, token_mgr, messages, token_mgr.get_token())
                return True
            elif status == "开放预约时间19:20":
                logger.info("未到预约时间")
            elif status == "您尚未登录":
                logger.info("没有登录，将重新尝试获取 token")
                token_mgr.get_token()
            elif status == "该空间当前状态不可预约":
                logger.info("此位置已被预约或位置不可用")
                if gate is not None:
                    gate['blocked'] = True   # 交回主循环判断是不是本账号自己占着
            elif status == "取消成功":
                logger.info("取消成功")
                return True
            elif "访问频繁" in status:
                # 服务端限流（"访问频繁，请5分钟后重试"，实测为 5 分钟窗口）。
                # 既不能当成功（会带着 0 个座位静默退出），也不能高频重试
                # （会不断重置窗口，5 分钟永远解不开）。直接终止并通知。
                logger.error(f"触发服务端限流: {status}")
                messages.append(f"\n触发服务端限流: {status}")
                send_message(config, "\n".join(messages),
                             f"脚本执行通知 - 学号: {config.username}")
                raise ReservationFailed(f"服务端限流: {status}")
            else:
                # 未知状态一律不视为成功。原实现 return True 会把限流/异常
                # 当成已完成，导致假成功。改为继续重试。
                logger.warning(f"未知状态信息（不视为成功，继续重试）: {status}")
                messages.append(f"\n未知状态: {status}")
                return False
        else:
            logger.info(seat_result)
    else:
        # 服务端削峰时会返回 msg=null 的快速拒绝（实测 ~60ms，正常响应 ~110-150ms）。
        # 这不是登录态问题——重登会触发滑块验证、打出更多请求，只会把限流锁得更死。
        # 原实现直接抛 ReservationFailed 会让整个抢座进程退赛（今日 A、B 皆因此退出）。
        #
        # 2026-10-19 实测修正：本账号自己超额的签名是 code=-7 "访问频繁，请5分钟后重试"，
        # 不是 msg=null；msg=null 是放座瞬间全校并发下服务端的削峰响应。因此这里退避
        # 3 秒会白扔放座后的黄金时间，改为立即回到循环顶，由 _pacer 统一控制在安全额度内。
        logger.warning(
            "未能获取有效的座位预约状态（服务端削峰），交由额度闸门控速后重试: %s", str(seat_result)[:200]
        )
    return False


def holds_target_seat(config, token_mgr, seat_no, nowday):
    """
    服务端回"该空间当前状态不可预约"时，判断这个座位是不是本账号自己占着的。

    2026-10-19 19:20 实测：<姓名B>名下已有目标座位，再发 confirm 得到的是
    "该空间当前状态不可预约"，并非"当前用户在该时段已存在座位预约"。模式5 永不降级，
    于是 100 发全部烧在自己已经占住的那个座位上，最后以 ReservationFailed 收场。
    命中"本人已持有该日期该座位"就直接判定完成。
    """
    try:
        res = get_member_seat(token_mgr.get_token())
        if not res or "data" not in res:
            return False
        want_day = str(nowday)[-5:]           # 记录里是 MM-DD，配置是 YYYY-MM-DD
        for entry in res["data"].get("data", []):
            if (str(entry.get("name")) == str(seat_no)
                    and str(entry.get("day")) == want_day
                    and entry.get("statusName") in ("预约成功", "使用中")):
                logger.info("目标座位 %s(%s) 已由本账号持有，判定为已完成", seat_no, nowday)
                return True
        return False
    except Exception as exc:
        logger.warning("查询本人座位失败，按未持有处理: %s", exc)
        return False


def _raw_confirm(select_id, segment, config, token_mgr, max_retries=1):
    """发一次 /api/Seat/confirm，只返回服务端原始 JSON，不做状态判定。

    每次真实发送都先过 _pacer.wait 的额度闸门；max_retries=1 表示不重试，
    三连发用这个形态保证"一发慢响应不拖住下一发"。
    """
    auth_token = token_mgr.get_token()
    origin_data = '{{"seat_id":"{}","segment":"{}"}}'.format(select_id, segment)
    aes_data = encrypt_seat_data(str(origin_data))

    post_data = {"aesjson": aes_data}
    request_headers = {**DEFAULT_HEADERS, "Authorization": auth_token}
    return post_with_retry(URL_GET_SEAT, post_data, request_headers,
                           max_retries=max_retries, retry_delay=1, timeout=15,
                           pre_send=_pacer.wait)


def _post_confirm_async(select_id, segment, config, token_mgr, results):
    """后台线程发一发 confirm，结果（含异常）放进队列。"""
    try:
        results.put(_raw_confirm(select_id, segment, config, token_mgr))
    except Exception as exc:
        results.put({"_error": repr(exc)})


def _first_window_burst(seat_no, seat_id, segment, config, token_mgr, messages, gate):
    """放座瞬间的三连发：发送与响应解耦。

    2026-10-23 实测：<姓名C>的第一发 confirm 在服务端排队 2.08s 才返回
    "此位置已被预约"，串行结构在这 2 秒里发不出第二发，198 已被别人订走；
    同晚<姓名A>、<姓名B>分别靠第 2、3 发命中。这里把 BURST_SENDS 发额度
    在同一个窗口内并发打满，任何一发慢响应都不再拖住后面的发。

    返回 (是否已拿到座位, 已发数)。
    """
    results = queue.Queue()
    sent = 0
    for i in range(BURST_SENDS):
        if i:
            time.sleep(BURST_GAP)
        threading.Thread(target=_post_confirm_async,
                         args=(seat_id, segment, config, token_mgr, results),
                         daemon=True).start()
        sent += 1

    deadline = time.time() + BURST_DRAIN
    received = 0
    while received < sent:
        left = deadline - time.time()
        if left <= 0:
            break
        try:
            item = results.get(timeout=left)
        except queue.Empty:
            break
        received += 1
        if "_error" in item:
            logger.warning("首发窗口请求异常: %s", item["_error"])
            continue
        if check_reservation_status(item, config, token_mgr, messages, gate):
            logger.info(f"首发窗口命中座位 {seat_no}（已发 {sent} 发）")
            return True, sent

    return False, sent


def post_to_get_seat(select_id, segment, config, token_mgr, messages, gate=None):
    """发送预约请求"""
    try:
        # max_retries 只给 3：内层每次重试都是一发真实的 /api/Seat/confirm 请求，
        # 所以逐次发送都挂 _pacer.wait 过额度闸门（实测额度见文件头），
        # 超时重发再多也不会越过 3 发/窗口的线。
        seat_result = _raw_confirm(select_id, segment, config, token_mgr, max_retries=3)
    except RequestFailed:
        messages.append("\n超过最大重试次数,请求失败。")
        title = f"脚本执行通知 - 学号: {config.username}"
        send_message(config, "\n".join(messages), title)
        raise ReservationFailed("超过最大重试次数,请求失败。")

    return check_reservation_status(seat_result, config, token_mgr, messages, gate)


def random_get_seat(data):
    """从座位列表中随机选一个"""
    random_dict = random.choice(data)
    return random_dict["id"]


def get_all_seats(build_id, segment, nowday):
    """返回该教室的全量座位列表（含已预约），用于建立 座位号->系统id 映射。"""
    post_data = {
        "area": build_id,
        "segment": segment,
        "day": nowday,
        "startTime": "08:00",
        "endTime": "22:00",
    }
    res = post_with_retry(
        URL_CLASSROOM_SEAT, post_data, DEFAULT_HEADERS,
        max_retries=10, retry_delay=1, timeout=15
    )
    return res.get("data") or []


def _flat_target_seats(config):
    """把配置里的 SEAT_ID 摊平成座位号字符串列表。"""
    flat = []
    for item in config.seat_id:
        if isinstance(item, list):
            flat.extend(item)
        else:
            flat.append(item)
    return [str(s) for s in flat]


def _mode5_targets(build_id, segment, nowday, config):
    """模式5：返回 [(座位号, 系统id)]，取自全量座位表（含已预约，故不受空闲过滤影响）。"""
    try:
        all_seats = get_all_seats(build_id, segment, nowday)
    except Exception as exc:
        logger.warning(f"获取全量座位列表失败: {exc}")
        return None
    id_map = {(str(s["no"]).lstrip("0") or "0"): s["id"] for s in all_seats}
    return [(no, id_map[no]) for no in _flat_target_seats(config) if no in id_map]


def _warm_up_before_release(targets, segment, config, token_mgr, messages, release_ts):
    """
    放座前预热：按 WARM_GAP 节奏发 confirm，把 token、座位ID、加密 payload、
    网络链路在放座之前全部验证一遍——这就是"提前多发送几个"的安全形态。

    实测依据（文件头常量注释）：预热按 2 秒一发远未触到 3 发/2 秒的线；
    并且必须在放座前 QUIET_BEFORE_RELEASE 秒停手，让放座瞬间的额度窗口是全空的，
    3 发额度全部留给那一刻。预热轮次不计入正式抢座的 100 次额度。

    返回 True 表示已经拿到座位，主循环无需再跑。
    """
    if not targets:
        return False
    seat_no, sys_id = targets[0]
    warmed = 0
    while time.time() < release_ts - QUIET_BEFORE_RELEASE:
        try:
            if post_to_get_seat(sys_id, segment, config, token_mgr, messages):
                logger.info(f"预热阶段已完成预约: {seat_no}")
                return True
        except ReservationFailed as exc:
            # 预热期就撞上服务端响应，说明额度或服务端状态异常。
            # 继续打只会加重惩罚，停手并把机会留给放座后的正式循环。
            logger.error(f"预热阶段异常，停止预热: {exc}")
            return False
        except Exception as exc:
            logger.warning(f"预热阶段请求异常，停止预热: {exc}")
            return False
        warmed += 1
        logger.info(f"预热第 {warmed} 发完成（座位 {seat_no}），{WARM_GAP}s 后继续")
        time.sleep(max(0.0, WARM_GAP - (time.time() - _pacer.last_sent())))
    return False


def select_seat(build_id, segment, nowday, config, token_mgr, messages):
    """选座主逻辑"""
    flag = False
    retries = 0
    last_round = None
    target_id_map = None      # 座位号 -> 系统 id（模式5 用，只取一次）
    release_ts = release_epoch(config.date)   # 放座瞬间；不在窗口前为 None

    if release_ts is not None and config.mode == "5":
        # 提前建好映射并预热，让 100 次额度完整留给放座后的争夺
        pre_targets = _mode5_targets(build_id, segment, nowday, config)
        if pre_targets:
            target_id_map = {no: sid for no, sid in pre_targets}
            if _warm_up_before_release(pre_targets, segment, config,
                                       token_mgr, messages, release_ts):
                return True

    # 只睡一次到放座瞬间；之后完全交给额度闸门控速
    waited_for_release = release_ts is None
    contest_at = None
    gate = {'open': False}   # 服务端放座窗口是否真的打开了（由 confirm 响应判断）

    while not flag and retries < 100:
        logger.info(f"开始第 {retries + 1} 次尝试获取座位")

        if not waited_for_release:
            _left = release_ts - time.time()
            if _left > 0:
                logger.info(f"静默等待放座瞬间，剩余 {_left:.2f}s（额度窗口已空出）")
                time.sleep(_left)
            contest_at = release_ts
            waited_for_release = True

        if retries > 0 and last_round is not None:
            # 放座后的前 BURST_SECONDS 秒不额外等待：实测额度是 3 发/窗口，
            # 让闸门把这三发全部用在放座瞬间的争夺上，而不是摊成均匀的 1 发/秒。
            # 过了这段时间再回到 STEADY_GAP，把 100 次额度铺到更长的时间里。
            _in_burst = (contest_at is not None
                         and time.time() - contest_at <= BURST_SECONDS)
            if not _in_burst:
                time.sleep(max(0.0, STEADY_GAP - (time.time() - last_round)))
            elif not gate['open']:
                # 本机已经到了 19:20，但服务端还在回"开放预约时间19:20"：
                # 两台时钟只有 ±1s 的同步把握，此刻把三连发额度打在必定被拒的请求上，
                # 换来的是随后约 2.7s 的闸门空窗。改成 PROBE_GAP 降频探测，
                # 一旦某个响应证明窗口已开，下一轮立刻不再等待、把额度全部打出。
                time.sleep(max(0.0, PROBE_GAP - (time.time() - last_round)))

        # 放座瞬间改用并发三连发：单座位的模式5 在额度窗口内一次打满 3 发，
        # 不能因为某一发在服务端排队（2026-10-23 首发排队 2.08s）就错过整个窗口。
        _target_seats = _flat_target_seats(config) if config.mode == "5" else []
        if (len(_target_seats) == 1 and target_id_map is not None
                and _target_seats[0] in target_id_map
                and contest_at is not None
                and time.time() - contest_at <= BURST_SECONDS):
            _seat_no = _target_seats[0]
            _got, _sent = _first_window_burst(
                _seat_no, target_id_map[_seat_no], segment,
                config, token_mgr, messages, gate)
            retries += _sent
            last_round = time.time()
            if _got:
                return True
            continue

        last_round = time.time()
        retries += 1

        if config.mode == "5" and target_id_map is not None:
            # 模式5 直连已经有 座位号->系统id 映射，不需要空闲列表。
            # 跳过这一发可用性查询，是为了让放座后的第一发 confirm 落在
            # 19:20:00.00x 而不是 19:20:00.4x（实测该查询单发 ~0.4s）。
            data = []
        else:
            data = get_seat_info(build_id, segment, nowday)

            if not data:
                logger.warning("获取座位信息失败，可能是时间段内不存在或该区域暂不可用")
                # 反向查找教室名称
                classname = build_id
                for key, value in classroom_id_mapping.items():
                    if value == build_id:
                        classname = key
                        break
                messages.append(f"\n[{classname}]: 获取座位信息失败")
                break

        if config.mode == "1":
            # 模式 1: 指定范围内有插座的位置
            seat_id_range = []
            for ran in config.seat_id:
                seat_id_range.extend(list(map(str, list(range(ran[0], ran[1] + 1)))))
            new_data = [d for d in data if (d["id"] not in EXCLUDE_ID) and (d["id"] in seat_id_range)]
            if new_data:
                select_id = random_get_seat(new_data)
                logger.info(f"随机选择的座位为: {select_id}")
                if post_to_get_seat(select_id, segment, config, token_mgr, messages):
                    flag = True
            continue

        elif config.mode == "2":
            # 模式 2: 有插座的位置
            new_data = [d for d in data if d["id"] not in EXCLUDE_ID]
            if new_data:
                select_id = random_get_seat(new_data)
                logger.info(f"随机选择的座位为: {select_id}")
                if post_to_get_seat(select_id, segment, config, token_mgr, messages):
                    flag = True
            continue

        elif config.mode == "3":
            # 模式 3: 随机选择
            select_id = random_get_seat(data)
            logger.info(f"随机选择的座位为: {select_id}")
            if post_to_get_seat(select_id, segment, config, token_mgr, messages):
                flag = True
            continue

        elif config.mode == "4":
            # 模式 4: 指定座位优先（适用于所有教室）
            # ⚠️ 约束：模式 4 和模式 5 永不降级、永不切到其他座位。指定的座位抢不到
            #    就一直重试到 100 次上限，宁可 0 结果也不坐别的位置。勿再添加降级逻辑。

            if data:
                logger.info(f"调试: 实际返回的前5个座位: {data[:5]}")

            # 从配置文件 SEAT_ID 读取目标座位号，第一个为优先选择
            target_seats_raw = config.seat_id
            target_seats_flat = []
            for item in target_seats_raw:
                if isinstance(item, list):
                    target_seats_flat.extend(item)
                else:
                    target_seats_flat.append(item)
            target_seats = [str(s) for s in target_seats_flat]
            priority_seats = target_seats[:1] if target_seats else []

            available_target_seats = []
            for seat in data:
                seat_no = seat["no"].lstrip("0") or "0"
                if seat_no in target_seats:
                    available_target_seats.append(seat)

            logger.info(
                f"调试: 可用座位数量: {len(data)}, 符合条件的座位数量: {len(available_target_seats)}"
            )
            if available_target_seats:
                logger.info(
                    f"调试: 符合条件的座位: {[(s['id'], s['no']) for s in available_target_seats]}"
                )

            if available_target_seats:
                priority_available = [
                    s for s in available_target_seats
                    if (s["no"].lstrip("0") or "0") in priority_seats
                ]
                if priority_available:
                    selected_seat = random.choice(priority_available)
                    select_id = selected_seat["id"]
                    logger.info(f"优先选择的座位为: {selected_seat['no']} (系统ID: {select_id})")
                else:
                    selected_seat = random.choice(available_target_seats)
                    select_id = selected_seat["id"]
                    logger.info(f"从指定座位中选择的座位为: {selected_seat['no']} (系统ID: {select_id})")
                if post_to_get_seat(select_id, segment, config, token_mgr, messages):
                    flag = True
            else:
                logger.info("指定座位列表中无可用座位，立即重试")
            continue

        elif config.mode == "5":
            # 模式 5: 指定座位直连——只提交 SEAT_ID 写明的座位，不切换到其他座位
            # ⚠️ 约束：模式 4 和模式 5 永不降级、永不切到其他座位。指定的座位抢不到
            #    就一直重试到 100 次上限，宁可 0 结果也不坐别的位置。勿再添加降级逻辑。

            target_seats_raw = config.seat_id
            target_seats_flat = []
            for item in target_seats_raw:
                if isinstance(item, list):
                    target_seats_flat.extend(item)
                else:
                    target_seats_flat.append(item)
            target_seats = [str(s) for s in target_seats_flat]

            if target_id_map is None:
                # 座位号 -> 系统 id 取自全量座位列表
                # （get_seat_info 只返回空闲座位，已预约的座位不在其中）
                try:
                    _all_seats = get_all_seats(build_id, segment, nowday)
                except Exception as _exc:
                    logger.warning(f"获取全量座位列表失败: {_exc}")
                    _all_seats = data
                target_id_map = {
                    (str(_s["no"]).lstrip("0") or "0"): _s["id"] for _s in _all_seats
                }

            for seat_no in target_seats:
                seat_id = target_id_map.get(seat_no)
                if seat_id is None:
                    logger.info(f"座位号 {seat_no} 不在本教室座位列表中")
                    continue
                logger.info(f"模式5 直连: 向服务端请求座位 {seat_no} (ID={seat_id})")
                if post_to_get_seat(seat_id, segment, config, token_mgr, messages, gate):
                    flag = True
                    break
                if gate.get('blocked') and holds_target_seat(config, token_mgr,
                                                              seat_no, nowday):
                    flag = True
                    break
                logger.info(f"座位 {seat_no} 本次未成功，继续重试")
            continue

            continue

        else:
            logger.error(f"未知的模式: {config.mode}")
            break

    if retries >= 100:
        logger.error("超过最大重试次数,无法获取座位")
        messages.append("\n超过最大重试次数,无法获取座位")
        title = f"脚本执行通知 - 学号: {config.username}"
        send_message(config, "\n".join(messages), title)
        raise ReservationFailed("超过最大重试次数,无法获取座位")


def run_seat_reservation(config: AppConfig, token_mgr: TokenManager):
    """预约主函数"""
    messages = []
    try:
        new_date = get_date(config.date)
        auth_token = token_mgr.get_token()

        for classroom_name in config.classrooms_name:
            build_id = get_build_id(classroom_name)
            segment = get_segment(build_id, new_date)
            select_seat(build_id, segment, new_date, config, token_mgr, messages)

        # 推送最终结果
        if messages:
            title = f"脚本执行通知 - 学号: {config.username}"
            send_message(config, "\n".join(messages), title)

    except AuthenticationError as e:
        logger.error(str(e))
        messages.append(f"\n{e}")
        title = f"脚本执行通知 - 学号: {config.username}"
        send_message(config, "\n".join(messages), title)
        raise ReservationFailed(f"登录认证失败: {e}") from e
    except KeyboardInterrupt:
        logger.info("主动退出程序，程序将退出。")


if __name__ == "__main__":
    # 带毫秒时间戳：抢座成败要看"放座后第一发落在 19:20:00.0xx"，
    # 没有毫秒就只剩一条无法证明的时间线（2026-10-18 的日志正因此量不出耗时）。
    logging.basicConfig(level=logging.INFO,
                        format="%(asctime)s.%(msecs)03d %(levelname)s %(name)s: %(message)s",
                        datefmt="%H:%M:%S")

    parser = argparse.ArgumentParser(description="图书馆座位预约脚本")
    parser.add_argument("-c", "--config", help="指定配置文件路径，默认为 configs/template.yml")
    args = parser.parse_args()

    try:
        config = AppConfig.from_yaml(args.config)
        token_mgr = TokenManager(config.username, config.password)
        run_seat_reservation(config, token_mgr)
    except KeyboardInterrupt:
        logger.info("主动退出程序，程序将退出。")
