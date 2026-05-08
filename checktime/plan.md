# 计划：实现时间差检测系统

## 任务目标
在 `e:\Files\Desktop\QFNULibraryBook\checktime` 目录下实现一个系统，持续检测本地时间与服务器时间的差值，实时展示并计算平均值。

## 实现步骤

### 1. 创建目录结构
- 创建 `e:\Files\Desktop\QFNULibraryBook\checktime` 目录

### 2. 实现 `time_checker.py`
- 参考现有的 `get_server_time.py` 获取服务器时间的方法
- 使用 `aiohttp` 发送请求获取服务器 `Date` 头
- 转换为北京时间（前面）和 UTC 时间（后面）展示

### 3. 核心功能
- **单次检测**：发送 HTTP 请求获取服务器时间戳
- **持续检测**：使用 `asyncio` 定时循环，每秒检测一次
- **统计计算**：
  - 记录每次检测的时间差
  - 实时计算滑动平均值（最近 N 次）
  - 显示最大/最小偏移

### 4. 输出格式
```
2026-05-08 12:46:14.123 (北京时间) | 2026-05-08 04:46:14.123 (UTC)
偏移: -0.336 秒
平均偏移 (10次): -0.325 秒
最大: -0.401 秒 | 最小: -0.212 秒
```

### 5. 实现文件
- `time_checker.py` - 主程序，包含：
  - `get_server_time()` - 获取单次服务器时间
  - `calculate_offset()` - 计算时间差
  - `run_continuous_check()` - 持续检测循环
  - `calculate_average()` - 计算平均值

## 预计输出文件
- `e:\Files\Desktop\QFNULibraryBook\checktime\time_checker.py`