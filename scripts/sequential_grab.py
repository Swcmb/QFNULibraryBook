#!/usr/bin/env python3
"""
顺序抢座脚本（cron 定时任务入口）

按 configs/admin.yml 中的 GRAB_ORDER 顺序对每个账号执行抢座，
单账号失败不影响后续账号，每个账号之间间隔 5 秒防止接口风控。

退出码：
    0 = 全部成功
    1 = 部分失败
    2 = 全部失败
"""
import logging
import os
import sys
import time
from datetime import datetime
from typing import Dict, List

import yaml

# 固化 src/ 目录到 sys.path，确保 from get_seat import run_seat_reservation 可用
sys.path.insert(
    0,
    os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "src"),
)

from config.config import AppConfig  # noqa: E402
from auth.token import TokenManager  # noqa: E402
from get_seat import run_seat_reservation  # noqa: E402

# 路径常量
_PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
_CONFIGS_DIR = os.path.join(_PROJECT_ROOT, "configs")
_USERS_INDEX = os.path.join(_CONFIGS_DIR, "users.yml")
_ADMIN_CFG = os.path.join(_CONFIGS_DIR, "admin.yml")
_LOG_DIR = "/var/log/qfnu-library"
_GRAB_LOG = os.path.join(_LOG_DIR, "grab.log")

# 日志配置（同时输出到 stderr 和 grab.log 文件）
os.makedirs(_LOG_DIR, exist_ok=True)
logger = logging.getLogger("sequential_grab")
logger.setLevel(logging.INFO)
_formatter = logging.Formatter("%(asctime)s [%(levelname)s] %(message)s")
_fh = logging.FileHandler(_GRAB_LOG, mode="a", encoding="utf-8")
_fh.setFormatter(_formatter)
logger.addHandler(_fh)
_sh = logging.StreamHandler(sys.stderr)
_sh.setFormatter(_formatter)
logger.addHandler(_sh)


def load_yaml(path: str) -> dict:
    """加载 YAML 文件，文件不存在时返回空字典"""
    if not os.path.exists(path):
        return {}
    with open(path, "r", encoding="utf-8") as f:
        return yaml.safe_load(f) or {}


def build_username_to_path() -> Dict[str, str]:
    """根据 users.yml 构造 学号 -> 配置文件绝对路径 的映射"""
    raw = load_yaml(_USERS_INDEX)
    users = raw.get("users", []) if isinstance(raw, dict) else []
    mapping: Dict[str, str] = {}
    for entry in users:
        cfg_rel = entry.get("config", "")
        cfg_path = cfg_rel if os.path.isabs(cfg_rel) else os.path.join(_CONFIGS_DIR, cfg_rel)
        cfg_data = load_yaml(cfg_path)
        username = cfg_data.get("USERNAME")
        if username:
            mapping[username] = cfg_path
    return mapping


def run_one_user(username: str, cfg_path: str) -> bool:
    """对单个用户执行抢座，返回是否成功"""
    try:
        cfg = AppConfig.from_yaml(cfg_path)
        if not cfg.username or not cfg.password:
            logger.error(f"[{username}] 用户名或密码为空，跳过")
            return False

        logger.info(f"[{username}] 开始抢座（mode={cfg.mode}, date={cfg.date}）")
        token_mgr = TokenManager(cfg.username, cfg.password)
        run_seat_reservation(cfg, token_mgr)
        logger.info(f"[{username}] 抢座成功")
        return True
    except Exception as e:
        logger.error(f"[{username}] 抢座失败: {e}")
        return False


def main() -> int:
    """顺序抢座入口"""
    started_at = datetime.now()
    logger.info(f"=== 顺序抢座任务启动 {started_at.isoformat()} ===")

    admin_cfg = load_yaml(_ADMIN_CFG)
    order: List[str] = admin_cfg.get("GRAB_ORDER", [])
    if not order:
        logger.warning("GRAB_ORDER 为空，无任务可执行")
        return 0

    username_to_path = build_username_to_path()

    success_count = 0
    fail_count = 0
    for idx, username in enumerate(order, 1):
        logger.info(f"--- [{idx}/{len(order)}] 处理账号 {username} ---")
        cfg_path = username_to_path.get(username)
        if not cfg_path:
            logger.error(f"[{username}] 配置文件缺失，跳过")
            fail_count += 1
            continue

        ok = run_one_user(username, cfg_path)
        if ok:
            success_count += 1
        else:
            fail_count += 1

        # 账号间间隔 5 秒（最后一个不等待）
        if idx < len(order):
            time.sleep(5)

    elapsed = (datetime.now() - started_at).total_seconds()
    logger.info(
        f"=== 任务结束 成功 {success_count}/{len(order)} 失败 {fail_count} 耗时 {elapsed:.1f}s ==="
    )

    if fail_count == 0:
        return 0
    if success_count == 0:
        return 2
    return 1


if __name__ == "__main__":
    sys.exit(main())
