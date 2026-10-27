"""起跑前验证钉钉通知链路是否真的可用。

why: 通知是用户唯一的结果反馈渠道。若钉钉通道在今晚失效，抢座成败用户都收不到，
     等于盲跑。此脚本只请求钉钉开放平台，与 libyy.qfnu.edu.cn 无关，
     不消耗抢座服务的出口 IP 配额。
"""
import os
import sys

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(REPO, "src"))
sys.path.insert(0, os.path.join(REPO, "scripts"))

from run_all import UsersConfig, load_user_configs  # noqa: E402
from notify.notify import send_message  # noqa: E402

uc = UsersConfig(os.path.join(REPO, "configs/users.yml"))
cfg = load_user_configs(uc.users[0])
if cfg is None:
    print("配置加载失败")
    sys.exit(1)

ok = send_message(
    cfg,
    "【起跑前自检】19:18 抢座通知通道测试。\n"
    "看到这条消息说明钉钉推送正常，19:18 起跑后你会收到真实结果。",
    "图书馆抢座 · 通知通道自检",
)
print(f"\nsend_message 返回: {ok}")