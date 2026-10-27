# 取消预约 API

## 端点
`POST http://libyy.qfnu.edu.cn/api/Space/cancel`

## 请求体
```json
{"id": "预约记录ID", "type": 1}
```

## 示例
```python
from auth.token import TokenManager
from api.constants import URL_CANCEL_SEAT, DEFAULT_HEADERS
import requests

tm = TokenManager('学号', '密码')
token = tm.get_token()
headers = {**DEFAULT_HEADERS, 'Authorization': token}

# 查当前预约 → 获取 id
r = requests.get(URL_CHECK_STATUS, headers=headers, timeout=10)
book_id = r.json()['data']['data'][0]['id']

# 取消
body = {'id': book_id, 'type': 1}
r = requests.post(URL_CANCEL_SEAT, json=body, headers=headers, timeout=10)
# 返回 {"code": 1, "msg": "取消成功"}
```

## 判断能否取消
查预约状态时，`cancel` 字段为 `1` 表示可取消，`0` 表示不可取消。
- 明天的预约（未签到）：cancel=1，可取消
- 今天的预约（已签到/使用中）：cancel=0，不可取消