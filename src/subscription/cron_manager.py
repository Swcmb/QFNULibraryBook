import os
import subprocess
from typing import List, Optional

logger = __import__('logging').getLogger(__name__)

PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
SCRIPTS_DIR = os.path.join(PROJECT_ROOT, 'scripts')


class CronManager:
    def __init__(self):
        os.makedirs(SCRIPTS_DIR, exist_ok=True)

    def _get_crontab(self) -> List[str]:
        try:
            result = subprocess.run(
                ['crontab', '-l'],
                capture_output=True,
                text=True,
                check=True
            )
            return result.stdout.strip().split('\n') if result.stdout else []
        except subprocess.CalledProcessError:
            return []

    def _set_crontab(self, lines: List[str]) -> bool:
        try:
            process = subprocess.Popen(
                ['crontab', '-'],
                stdin=subprocess.PIPE,
                text=True
            )
            process.communicate(input='\n'.join(lines))
            return process.returncode == 0
        except Exception as e:
            logger.error(f'设置 crontab 失败: {e}')
            return False

    def _generate_user_script(self, username: str, config_path: str, task_type: str) -> str:
        script_name = f'user_{username}_{task_type}.sh'
        script_path = os.path.join(SCRIPTS_DIR, script_name)

        script_content = f'''#!/bin/bash
cd {PROJECT_ROOT}
python3 scripts/run_all.py --config {config_path} --{task_type}
'''

        with open(script_path, 'w') as f:
            f.write(script_content)

        os.chmod(script_path, 0o755)
        return script_path

    def add_user_checkin_task(self, username: str, config_path: str, time_str: str = '08:01') -> bool:
        return self._add_user_task(username, config_path, 'checkin', time_str)

    def add_user_signout_task(self, username: str, config_path: str, time_str: str = '21:01') -> bool:
        return self._add_user_task(username, config_path, 'signout', time_str)

    def _add_user_task(self, username: str, config_path: str, task_type: str, time_str: str) -> bool:
        try:
            self.remove_user_task(username, task_type)

            script_path = self._generate_user_script(username, config_path, task_type)
            minute, hour = time_str.split(':')

            cron_line = f'{minute} {hour} * * * {script_path} 2>&1 >> /var/log/qfnu-library/{task_type}.log'
            cron_line += f' # qfnu-sub:{username}:{task_type}'

            current_lines = self._get_crontab()
            current_lines.append(cron_line)

            success = self._set_crontab(current_lines)
            if success:
                logger.info(f'用户 {username} 的 {task_type} 定时任务已添加: {time_str}')
            return success
        except Exception as e:
            logger.error(f'添加定时任务失败: {e}')
            return False

    def remove_user_task(self, username: str, task_type: str) -> bool:
        try:
            current_lines = self._get_crontab()
            comment = f'# qfnu-sub:{username}:{task_type}'

            new_lines = [line for line in current_lines if comment not in line]

            if len(new_lines) != len(current_lines):
                success = self._set_crontab(new_lines)
                if success:
                    logger.info(f'用户 {username} 的 {task_type} 定时任务已移除')

                script_path = os.path.join(SCRIPTS_DIR, f'user_{username}_{task_type}.sh')
                if os.path.exists(script_path):
                    os.remove(script_path)

                return success
            return True
        except Exception as e:
            logger.error(f'移除定时任务失败: {e}')
            return False

    def remove_user_tasks(self, username: str) -> bool:
        try:
            checkin_ok = self.remove_user_task(username, 'checkin')
            signout_ok = self.remove_user_task(username, 'signout')
            return checkin_ok and signout_ok
        except Exception as e:
            logger.error(f'移除用户所有任务失败: {e}')
            return False

    def check_task_exists(self, username: str, task_type: str) -> bool:
        try:
            current_lines = self._get_crontab()
            comment = f'# qfnu-sub:{username}:{task_type}'
            return any(comment in line for line in current_lines)
        except Exception:
            return False

    def list_user_tasks(self, username: str) -> List[dict]:
        try:
            current_lines = self._get_crontab()
            tasks = []
            for line in current_lines:
                if f'# qfnu-sub:{username}:' in line:
                    parts = line.split('# qfnu-sub:')[1].split(':')
                    task_type = parts[1].strip()
                    tasks.append({'type': task_type, 'cron_line': line})
            return tasks
        except Exception as e:
            logger.error(f'获取用户任务列表失败: {e}')
            return []
