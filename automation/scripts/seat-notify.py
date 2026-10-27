"""抢座结果通知 —— 由 book-seat.sh / book-seat-userC.sh 调用。

原实现内联在 book-seat.sh 的 heredoc 里，有两个问题：
  1) 缺 sys.path，导致 ModuleNotFoundError: No module named 'notify'
  2) heredoc 被 bash 误解析，脚本退出码 2（Hermes 记为 script failed）
抽成独立文件后行为不变，仅补上 sys.path。

账号信息（日志文件名、姓名、密码）全部从 configs/userN.yml 读取，
调用方通过 --users 指定本次参与的账号，不再硬编码 user2 或明文密码。

2026-10-27 修复两处误导：
  1) 目标文案原先读 configs/userN.yml 的旧默认值；临时抢座配置在 book-seat.sh
     生成、通知之后才删除。存在 /tmp/userN-booking.yml 时优先使用，
     通知里的目标以实际抢座配置为准。
  2) 服务端限流发生在确认预约成功之后、日志记录之前，旧实现据此误报
     ⚠️/❌。现在每账号用个人预约接口回查一次：确实持有本次目标座位就改判 ✅。

用法:
  seat-notify.py --users configs/user2.yml configs/user1.yml configs/user3.yml
  seat-notify.py --users configs/user3.yml
"""
import argparse
import datetime
import os
import sys

_PROJECT_SRC = '/home/admin/MyQFNULibraryBook/src'
sys.path.insert(0, _PROJECT_SRC)

import requests  # noqa: E402

from api.constants import URL_CHECK_STATUS, DEFAULT_HEADERS  # noqa: E402
from auth.token import TokenManager  # noqa: E402
from config.config import AppConfig  # noqa: E402
from notify.notify import send_message  # noqa: E402

LOG_TEMPLATE = '/tmp/seat-%s.log'


def resolve_cfg_path(path):
    """存在抢座临时配置时优先用它：目标座位以实际抢座配置为准。"""
    base = os.path.basename(path)
    if base.endswith('.yml'):
        cand = '/tmp/%s-booking.yml' % base[:-4]
        if os.path.exists(cand):
            return cand
    return path


def rc(path):
    try:
        txt = open(path, encoding='utf-8', errors='replace').read()
    except Exception:
        return '无日志'
    if '预约成功' in txt:
        last = [l for l in txt.splitlines() if '你当前的座位是' in l]
        return '✅ 成功 ' + (last[-1].split('你当前的座位是')[-1].strip() if last else '')
    if '已由本账号持有' in txt:
        return '✅ 成功（本人已持有）'
    if '存在正在使用的座位' in txt:
        return '✅ 成功（座位使用中）'
    if '本次未成功' in txt:
        n = txt.count('本次未成功')
        return '❌ 未抢到（重试 %d 次）' % n
    return '⚠️ 异常结束'


def current(user, pwd):
    try:
        tm = TokenManager(user, pwd)
        h = {**DEFAULT_HEADERS, 'Authorization': tm.get_token()}
        rows = (requests.get(URL_CHECK_STATUS + '?per_page=50', headers=h, timeout=20)
                .json().get('data') or {}).get('data') or []
        for e in rows:
            if e.get('statusName') == '预约成功':
                return '%s %s' % (str(e.get('beginTime'))[:10], e.get('no'))
    except Exception as exc:
        return '查询失败:%s' % type(exc).__name__
    return '无有效预约'


def seat_label(cfg):
    """目标座位描述：优先用配置的座位号，缺省用楼层。"""
    seats = ','.join(str(s) for s in (cfg.seat_id or []))
    if seats and cfg.classrooms_name:
        return '%s %s' % (cfg.classrooms_name[0], seats)
    if seats:
        return seats
    return cfg.classrooms_name[0] if cfg.classrooms_name else '未指定'


def flatten_seat_ids(seat_id):
    """SEAT_ID 摊平成去前导零的座位号集合，用于与持有座位比对。"""
    flat = []
    for item in seat_id or []:
        if isinstance(item, list):
            flat.extend(item)
        else:
            flat.append(item)
    return {(str(s).lstrip('0') or '0') for s in flat}


def held_seat_no(cur):
    """从 'YYYY-MM-DD 0NN' 解析持有座位号；查询失败等异常形态返回 None。"""
    parts = (cur or '').split()
    if len(parts) != 2:
        return None
    return parts[1].lstrip('0') or '0'


def main():
    parser = argparse.ArgumentParser(description='图书馆抢座结果汇总通知')
    parser.add_argument(
        '--users', nargs='+', default=['configs/user2.yml'],
        help='本次参与的账号配置文件（相对项目根目录或绝对路径），至少一个'
    )
    args = parser.parse_args()

    configs = []
    for user_file in args.users:
        src = user_file if os.path.isabs(user_file) else os.path.join(
            os.path.dirname(_PROJECT_SRC), user_file)
        path = resolve_cfg_path(src)
        try:
            configs.append(AppConfig.from_yaml(path))
        except Exception as exc:
            print('[notify] 读取账号配置失败 %s: %s %s'
                  % (path, type(exc).__name__, exc))
    if not configs:
        print('[notify] 没有可用账号配置，退出')
        return 1

    # 用第一个账号的钉钉配置投递
    notify_cfg = configs[0]

    # 每账号只查一次个人预约：既复核状态，也供"当前有效预约"列表使用
    results = []
    for cfg in configs:
        status = rc(LOG_TEMPLATE % cfg.username)
        cur = current(cfg.username, cfg.password)
        held = held_seat_no(cur)
        if held is not None and not status.startswith('✅'):
            if held in flatten_seat_ids(cfg.seat_id):
                status = '✅ 成功（日志未确认，服务端持有 %s）' % cur
            else:
                status = '%s（当前持有 %s，非本次目标）' % (status, cur)
        results.append((cfg, status, cur))

    today = datetime.date.today()
    lines = ['📚 图书馆抢座结果 %s' % today.strftime('%Y-%m-%d'), '']
    for cfg, status, cur in results:
        lines.append('学号%s 目标%s: %s'
                     % (cfg.username, seat_label(cfg), status))
    lines += ['', '当前有效预约:']
    for cfg, status, cur in results:
        lines.append('  %s: %s' % (cfg.username, cur))

    try:
        ok = send_message(notify_cfg, chr(10).join(lines), '图书馆抢座结果')
        print('[notify] 推送结果:', ok)
    except Exception as exc:
        print('[notify] 推送失败:', type(exc).__name__, exc)
    return 0


if __name__ == '__main__':
    sys.exit(main())
