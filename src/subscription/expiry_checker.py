#!/usr/bin/env python3
import sys
import os

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

from datetime import datetime
from src.user.user_manager import UserManager
from src.subscription.cron_manager import CronManager
from src.notify.admin_notify import notify_expiring_soon, notify_expired


def check_expiring_subscriptions(days_before: int = 3):
    user_mgr = UserManager()
    subscribed_users = user_mgr.list_subscribed_users()

    for user in subscribed_users:
        if user.get('status') != 'active':
            continue

        expires_str = user.get('expires_at', '')
        if not expires_str:
            continue

        try:
            expires = datetime.strptime(expires_str, '%Y-%m-%d')
            now = datetime.now()
            days_left = (expires - now).days

            if 0 < days_left <= days_before:
                notify_expiring_soon(user['username'], days_left)
                print(f'用户 {user["username"]} 订阅即将到期，剩余 {days_left} 天')

        except ValueError:
            continue


def check_expired_subscriptions():
    user_mgr = UserManager()
    cron_mgr = CronManager()
    subscribed_users = user_mgr.list_subscribed_users()

    for user in subscribed_users:
        if user.get('status') != 'active':
            continue

        expires_str = user.get('expires_at', '')
        if not expires_str:
            continue

        try:
            expires = datetime.strptime(expires_str, '%Y-%m-%d')
            now = datetime.now()

            if expires < now:
                user_mgr.update_subscription(user['username'], user['plan_type'], 0)
                cron_mgr.remove_user_tasks(user['username'])
                notify_expired(user['username'])
                print(f'用户 {user["username"]} 订阅已到期，定时任务已停止')

        except ValueError:
            continue


if __name__ == '__main__':
    print('=== 检测即将到期的订阅 ===')
    check_expiring_subscriptions()
    print()
    print('=== 检测已到期的订阅 ===')
    check_expired_subscriptions()
    print('检测完成')
