# 图书馆预约取消 API 参考

## 端点
`POST http://libyy.qfnu.edu.cn/api/Space/cancel`

## 请求体
```json
{"id": "预约记录ID", "type": 1}
```
- `id`: 从 `GET /api/Member/seat` 响应的 `data.data[0].id` 字段获取
- `type`: 固定为 1

## 请求头
```python
{
    "Content-Type": "application/json",
    "Authorization": "bearer <token>",
    ...DEFAULT_HEADERS  # 需含 User-Agent、Origin、Referer 等
}
```

## 响应
```json
{"code": 1, "msg": "取消成功"}
```

## 预约状态字段说明

| status | 含义 | cancel | 可操作 |
|--------|------|--------|--------|
| `"2"` | 预约成功（未开始） | `1` | ✅ 可取消 |
| `"3"` | 使用中（已签到） | `"0"` | ❌ 不可取消，需签退 |

## 完整取消代码
```python
from auth.token import TokenManager
from api.constants import URL_CANCEL_SEAT, URL_CHECK_STATUS, DEFAULT_HEADERS
import requests

tm = TokenManager('学号', '密码')
token = tm.get_token()
headers = {**DEFAULT_HEADERS, 'Authorization': token}

# 1. 查当前预约
r = requests.get(URL_CHECK_STATUS, headers=headers, timeout=10)
data = r.json()
booking_id = data['data']['data'][0]['id']
cancelable = data['data']['data'][0]['cancel']
print(f"预约ID: {booking_id}, 可取消: {cancelable}")

# 2. 取消
body = {'id': booking_id, 'type': 1}
r = requests.post(URL_CANCEL_SEAT, json=body, headers=headers, timeout=10)
print(r.json()['msg'])  # "取消成功"
```