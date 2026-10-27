"""
只读诊断 —— 按房间分别核查目标座位，修正 probe_seat_map.py 的字典覆盖问题。

不发起任何下单请求。
"""
import logging
import sys

sys.path.insert(0, "src")
logging.disable(logging.INFO)

from config.config import AppConfig
from auth.token import TokenManager
from get_info import get_date, get_build_id, get_segment, get_seat_info

# 目标：(座位号, 房间名, 期望的 build_id)
TARGETS = [
    ("226", "东校区图书馆-三层自习室", 22),
    ("252", "东校区图书馆-三层自习室", 22),
    ("198", "东校区图书馆-五楼自习区（南）（东区房间静音）", 49),
]

cfg = AppConfig.from_yaml("configs/user3.yml")
tm = TokenManager(cfg.username, cfg.password)
tm.get_token()
day = get_date("tomorrow")
print("目标日期 =", day)

for room in sorted({t[1] for t in TARGETS}):
    bid = get_build_id(room)
    seg = get_segment(bid, day)
    seats = {str(s["no"]): s["id"] for s in get_seat_info(bid, seg, day)}
    print(f"\n房间: {room}  build_id={bid}  空闲={len(seats)}")

    for no, r, exp_bid in TARGETS:
        if r != room:
            continue
        mark = "OK " if bid == exp_bid else "!! build_id 不符"
        print(f"  座位 {no} -> 系统ID {seats.get(no, '不在空闲集合')}   {mark}")

# 交叉核对：目标座位号在另一房间是否也存在
print("\n=== 座位号跨房间存在性交叉核对 ===")
for room in sorted({t[1] for t in TARGETS}):
    bid = get_build_id(room)
    seg = get_segment(bid, day)
    seats = {str(s["no"]) for s in get_seat_info(bid, seg, day)}
    print(f"  {room[:20]:<22} 含226={('226' in seats)} "
          f"含252={('252' in seats)} 含198={('198' in seats)}")