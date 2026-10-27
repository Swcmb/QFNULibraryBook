"""
只读诊断脚本 —— 查询三个账号近期的预约记录，不发起任何下单请求。

用途: 起跑前确认各账号当前是否持有既存预约，判断 tomorrow 窗口是否可用。
"""
import logging
import sys

sys.path.insert(0, "src")
logging.disable(logging.INFO)

from config.config import AppConfig
from auth.token import TokenManager
from get_info import get_member_seat

# status 语义来自 MEMORY.md L19: cancel=1 可取消, cancel=0 不可取消(已签到使用中)
STATUS_NOTE = {
    "1": "待审核/待使用", "2": "已预约未签到", "3": "使用中",
    "4": "已签到", "5": "已签退", "6": "已取消",
}

for f in ["configs/user1.yml", "configs/user2.yml", "configs/user3.yml"]:
    c = AppConfig.from_yaml(f)
    tm = TokenManager(c.username, c.password)
    r = get_member_seat(tm.get_token())
    rows = r.get("data", {}).get("data", []) if isinstance(r, dict) else []
    total = r.get("data", {}).get("total") if isinstance(r, dict) else "?"
    print(f"--- {c.username}  累计记录={total}")
    for x in rows[:4]:
        st = str(x.get("status"))
        note = STATUS_NOTE.get(st, "未知")
        print(f"    id={x.get('id')} status={st}({note}) space={x.get('space')} "
              f"cancel={x.get('cancel')} {x.get('beginTime')} -> {x.get('endTime')}")