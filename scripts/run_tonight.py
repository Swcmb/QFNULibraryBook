"""
2026-10-11 一次性抢座调度器 —— 两个进程，19:18 与 19:19:30 分别起跑。

why: 单进程 run_all.py 会把三账号塞进同一 IP 的并发池，实测服务端按出口 IP 限流
     （60 次/分 在第 4 次即触发快速拒绝，且静默数分钟）。拆成两个独立进程后，
     三楼两账号共享 1 个 IP 配额、五楼账号独立，仍在 6 秒间隔的安全区间内。

用法:
  python scripts/run_tonight.py          # 前台等待并启动
  python scripts/run_tonight.py --dry    # 只打印计划，不执行
"""
import argparse
import os
import subprocess
import sys
import time
from datetime import datetime

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

# 19:19:00 —— 三楼两账号（<姓名B> 226 / <姓名A> 252）
# 19:19 而非 19:18：服务端 19:20 才开放预约，提前起跑只是热身。6 秒间隔下每账号
# 每分钟约 20 次请求、两账号约 40 次，而实测安全线是每 60 秒约 20–23 次。19:18 起跑
# 会在窗口开放前先打出约 80 发把配额耗尽，19:20 一开窗就被限流锁住。19:19 起跑把这段
# 洪峰砍半，热身时长 60 秒远高于登录+滑块实测所需的 5 秒。
PLAN_MAIN = {
    "start": (19, 19, 0),
    "users": "configs/users.yml",
    "label": "三楼双账号",
}

# 19:19:30 —— 五楼<姓名C>（mode=5 / 198），晚 30 秒避开同一 IP 峰值
PLAN_ZHAOBIN = {
    "start": (19, 19, 30),
    "users": "configs/users_userC.yml",
    "label": "五楼<姓名C>",
}


def wait_until(target, dry=False):
    """睡到指定时刻。返回实际等待秒数。"""
    now = datetime.now()
    target_dt = now.replace(hour=target[0], minute=target[1],
                            second=target[2], microsecond=0)
    wait_s = (target_dt - now).total_seconds()
    if dry:
        print(f"[dry] 距 {target_dt.strftime('%H:%M:%S')} 约 {wait_s:.0f}s")
        return wait_s
    if wait_s <= 0:
        print(f"目标时刻 {target_dt.strftime('%H:%M:%S')} 已过，立即启动")
        return 0
    print(f"等待至 {target_dt.strftime('%H:%M:%S')}（{wait_s:.0f}s）...", flush=True)
    while wait_s > 0:
        time.sleep(min(5, wait_s))
        wait_s = (target_dt - datetime.now()).total_seconds()
    return True


def launch(plan, dry=False):
    """拉起一个抢座子进程"""
    cmd = [sys.executable, os.path.join(REPO, "scripts", "run_all.py"),
           "seat", "-u", plan["users"], "--notify-mode", "each"]
    print(f"[{'dry' if dry else 'launch'}] {plan['label']} "
          f"@ {'.'.join(str(x) for x in plan['start'])} :: {' '.join(cmd[-5:])}",
          flush=True)
    if dry:
        return None
    env = dict(os.environ)
    env["PYTHONPATH"] = os.path.join(REPO, "src")
    return subprocess.Popen(cmd, cwd=REPO, env=env)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--dry", action="store_true", help="只打印计划")
    args = parser.parse_args()

    print(f"启动时间 {datetime.now():%H:%M:%S}  repo={REPO}", flush=True)
    wait_until(PLAN_MAIN["start"], args.dry)
    procs = [("main", launch(PLAN_MAIN, args.dry))]

    wait_until(PLAN_ZHAOBIN["start"], args.dry)
    procs.append(("userC", launch(PLAN_ZHAOBIN, args.dry)))

    if args.dry:
        print("[dry] 计划结束，未执行任何抢座请求")
        return 0

    rc = 0
    for name, p in procs:
        if p is None:
            continue
        code = p.wait()
        print(f"[done] {name} exit={code}", flush=True)
        if code != 0:
            rc = 1
    return rc


if __name__ == "__main__":
    sys.exit(main())