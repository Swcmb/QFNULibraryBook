# QFNULibraryBook

面向曲阜师范大学图书馆预约系统的 Python 自动化工具，覆盖座位预约、签到、签退、座位信息查询与多账号批处理。

[![Python](https://img.shields.io/badge/Python-3.10%2B-3776AB?logo=python&logoColor=white)](https://www.python.org/)
[![License](https://img.shields.io/badge/License-CC%20BY--NC%204.0-blue.svg)](LICENSE)

项目基于图书馆预约系统 [libyy.qfnu.edu.cn](http://libyy.qfnu.edu.cn/) 的现有接口实现。接口、开放时间和业务规则可能随学校系统调整，请以图书馆官方页面中的实际状态为准。

## 目录

- [功能概览](#功能概览)
- [快速开始](#快速开始)
- [配置说明](#配置说明)
- [预约模式](#预约模式)
- [常用命令](#常用命令)
- [多账号运行](#多账号运行)
- [自动化与 Agent Skill](#自动化与-agent-skill)
- [项目结构](#项目结构)
- [测试](#测试)
- [使用须知](#使用须知)
- [致谢与许可](#致谢与许可)

## 功能概览

- **座位预约**：支持按座位范围、插座条件、随机座位及指定座位进行选择。
- **预约时序控制**：围绕代码中配置的次日放座时间安排请求，并对预约确认请求进行节奏控制。
- **签到与签退**：通过独立命令完成签到、签退，并查询当前账号的座位状态。
- **多账号批处理**：使用线程池为多个配置执行预约、签到或签退，可设置并发数及通知模式。
- **消息通知**：支持 Telegram、钉钉、Bark 和 AnPush。
- **教室映射与座位数据**：集中维护教室名称、系统 ID 和座位信息；可使用管理工具抓取座位快照。
- **自动化脚本与 Agent Skill**：提供服务器定时任务脚本，以及可供兼容 Agent 使用的图书馆预约工作流说明。

## 快速开始

### 1. 环境准备

需要 Python 3.10 或更高版本。

~~~bash
git clone https://github.com/Swcmb/QFNULibraryBook.git
cd QFNULibraryBook

python -m venv .venv
~~~

激活虚拟环境后安装依赖：

**Windows PowerShell**

~~~powershell
.\.venv\Scripts\Activate.ps1
python -m pip install --upgrade pip
python -m pip install -r requirements.txt
~~~

**Linux / macOS**

~~~bash
source .venv/bin/activate
python -m pip install --upgrade pip
python -m pip install -r requirements.txt
~~~

### 2. 创建本地配置

复制模板，在本地配置中填写自己的账号与预约参数。不要把包含真实学号、密码或通知凭据的文件提交到 Git。

**Windows PowerShell**

~~~powershell
Copy-Item configs/template.yml configs/local.yml
Add-Content .git/info/exclude "configs/local.yml"
~~~

**Linux / macOS**

~~~bash
cp configs/template.yml configs/local.yml
printf '\nconfigs/local.yml\n' >> .git/info/exclude
~~~

以上命令会把 **configs/local.yml** 加入本地 Git 忽略规则。随后编辑该文件，至少检查以下配置：

~~~yaml
USERNAME: "YOUR_STUDENT_ID"
PASSWORD: "YOUR_PASSWORD"

MODE: "5"
SEAT_ID:
  - 226
CLASSROOMS_NAME:
  - 东校区图书馆-三楼自修区
DATE: "tomorrow"

# 留空表示关闭通知；可选 TG / DD / BARK / ANPUSH
PUSH_METHOD: ""
~~~

教室名称必须与 [src/classrooms.py](src/classrooms.py) 中的映射名称一致。通知渠道启用后，还需在配置中填写相应的 Token、密钥或频道 ID；字段示例见 [configs/template.yml](configs/template.yml)。

### 3. 执行预约、签到或签退

在项目根目录运行：

~~~bash
# 预约
python src/get_seat.py -c configs/local.yml

# 签到
python src/check_in.py -c configs/local.yml

# 签退
python src/sign_out.py -c configs/local.yml
~~~

脚本会输出执行日志。预约是否成功、座位是否仍有效以及签到/签退状态，都应结合日志和图书馆官方页面核实。

## 配置说明

| 配置项 | 作用 |
| --- | --- |
| **USERNAME / PASSWORD** | 图书馆账号凭据 |
| **MODE** | 预约模式，取值为 1 至 5 |
| **SEAT_ID** | 根据模式填写系统座位 ID 范围或座位号，具体见下表 |
| **CLASSROOMS_NAME** | 要预约的教室名称列表，名称须与代码映射一致 |
| **DATE** | 预约日期：today 或 tomorrow |
| **PUSH_METHOD** | 通知渠道：TG、DD、BARK、ANPUSH；留空表示关闭通知 |
| **SUSPEND** | 自动化任务可使用的暂停开关，具体行为以相应脚本实现为准 |

代码中的默认放座时刻为 **19:20**。运行主机的本地时区应与预约系统使用的时区一致；若学校调整开放时间，请先检查并更新程序中的时序设置。

## 预约模式

| 模式 | 选择规则 | SEAT_ID 的含义 |
| --- | --- | --- |
| **1** | 在指定范围中随机选择符合条件的有插座座位，并排除已维护的无插座座位 ID | 系统座位 ID 的闭区间，例如 [[7480, 7519], [7544, 7567]] |
| **2** | 在当前教室的可用座位中选择有插座的座位 | 不用于指定目标座位 |
| **3** | 在当前教室的可用座位中随机选择 | 不用于指定目标座位 |
| **4** | 仅在指定座位号中选择；列表首项优先，其余项作为候选 | 座位号，例如 [226, 228] |
| **5** | 直接提交指定座位，不切换到列表外的其他座位 | 一个或多个座位号，例如 [226] |

模式 **4** 和 **5** 都只尝试配置中列出的座位。目标座位不可用时，程序不会自动改选列表之外的座位。

## 常用命令

### 查询座位信息

管理工具读取配置中的日期和教室，并将获取到的座位数据保存为 JSON 文件：

~~~bash
python src/get_seat_info_ForAdmin.py -c configs/local.yml
~~~

### 批量执行多个账号

先在 **configs/** 下建立一个本地用户清单，例如 **configs/my-users.yml**。每个 **config** 路径相对于该清单所在目录解析：

~~~yaml
users:
  - config: local-a.yml
    name: account-a
  - config: local-b.yml
    name: account-b
~~~

将 **configs/my-users.yml**、**configs/local-a.yml** 和 **configs/local-b.yml** 加入 **.git/info/exclude** 或适当的本地忽略规则，并为每个账号创建独立配置。然后执行：

~~~bash
# 多账号预约
python scripts/run_all.py seat -u configs/my-users.yml --max-workers 2

# 多账号签到
python scripts/run_all.py checkin -u configs/my-users.yml --max-workers 2

# 多账号签退
python scripts/run_all.py signout -u configs/my-users.yml --max-workers 2
~~~

**--max-workers** 用于设置最大并发线程数；**--notify-mode** 可设为 **each**（各账号独立通知）或 **aggregated**（聚合通知）。请根据图书馆系统规则和账号实际授权合理设置并发。

## 自动化与 Agent Skill

仓库还包含面向服务器调度和 AI Agent 工作流的辅助文件：

- **automation/scripts/**：预约、签到、签退和通知相关的 Shell/Python 脚本。
- **automation/skills/productivity/library-seat-booking/SKILL.md**：图书馆预约 Skill，记录预约流程、取消预约、状态核验与常见问题处理。
- **automation/cron/jobs.json**：调度任务定义及运行状态快照，具体格式取决于生成它的调度器。
- **deploy/systemd/**：Linux systemd 服务配置。
- **docs/ORGANIZATION.md**：仓库目录及归档说明。

**注意：** **automation/scripts/** 中部分脚本针对维护者的 Linux 服务器目录、虚拟环境和账号配置编写。运行前请检查并修改其中的路径、账号清单、目标教室和座位号；不要将服务器专用脚本直接当作通用安装脚本执行。

## 项目结构

~~~text
QFNULibraryBook/
├── src/                 # 预约、签到、签退、认证、请求、加密与通知模块
├── configs/             # 配置模板与用户清单
├── scripts/             # 多账号执行及辅助脚本
├── data/seat_info/      # 教室座位信息快照
├── tests/               # 单元测试
├── automation/
│   ├── scripts/         # 服务器自动化脚本
│   ├── skills/          # Agent Skill 与参考文档
│   └── cron/            # 调度任务快照
├── deploy/systemd/      # systemd 服务配置
├── docs/                # 仓库说明与评审记录
├── archive/             # 历史文件归档
├── requirements.txt
└── README.md
~~~

## 测试

安装测试依赖并从项目根目录运行：

~~~bash
python -m pip install pytest
python -m pytest -q
~~~

## 使用须知

- 本项目仅用于学习和个人效率辅助。使用前请确认图书馆规章及预约系统的使用要求。
- 请勿恶意占座、空占座位或通过过度请求影响其他读者正常使用。
- 系统接口、认证流程、座位映射与开放时间均可能变化；遇到异常时先核对官方页面和日志，再调整配置或代码。
- 请自行保护账号密码、Token、钉钉密钥等凭据。对外发布前检查配置文件、日志、截图和自动化脚本，确认没有真实个人信息或密钥。

## 致谢与许可

本项目基于 [sakurasep/qfnuLibraryBook](https://github.com/sakurasep/qfnuLibraryBook) 二次开发，并保留原作者及既有贡献者的相关致谢。

项目许可见 [LICENSE](LICENSE)：**CC BY-NC 4.0**。
