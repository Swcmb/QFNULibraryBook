# 仓库组织说明

本仓库把原先散落在服务器两处（生产版 `/opt/qfnulibrary`、开发版 `~/MyQFNULibraryBook`）以及 Hermes 智能体侧的图书馆抢座系统相关内容，合并为一个自包含的 Git 仓库，按用途分层存放。

重组日期：2026-10-11。原始内容全部保留在 `extracted/` 下未被删除，本仓库的每一份文件都能追溯到那里。

---

## 五层结构

| 目录 | 职责 | 是否参与运行 | 来源分组 |
|---|---|---|---|
| `src/` `tests/` `web/` `configs/` `data/` `assets/` `scripts/` | 程序本体 | 是 | 开发版 `MyQFNULibraryBook`（代码基准） |
| `automation/` | 定时调度与技能包 | 是（由 Hermes 调用） | `hermes/` |
| `deploy/` | 部署配置 | 是 | `systemd/` |
| `archive/` | 历史存档 | 否 | `opt_qfnulibrary/logs`、`extras/`、`hermes/misc`、`book` 与 `opt` 的 `.bak` |
| `docs/` | 组织说明与评审记录 | 否 | 本轮新建 |

### 程序本体

- `src/` 19 个 `.py`：`auth/`（登录与令牌）、`api/`（接口常量）、`crypto/`（AES 动态加密）、`config/`（配置解析）、`notify/`（通知）、以及根部的 `get_seat.py`、`check_in.py`、`sign_out.py`、`get_info.py`、`seat_selector.py`、`classrooms.py`
- `tests/` 14 个 `test_*.py` + `conftest.py` + `__init__.py`，加 `fixtures/` 下 7 个 YAML
- `web/` 独立的 Flask 面板，有自己的 `requirements.txt`（Flask + flask-session），与根 `requirements.txt` 分离
- `configs/` 7 个 YAML，其中 `user1/2/3.yml` 含学号与密码明文
- `data/seat_info/` 15 个中文名 JSON，含真实座位信息
- `assets/` 14 张文档截图
- `scripts/loop_seat.sh` 是 systemd 单元的 `ExecStart` 目标，**唯一来自生产版**的程序文件

### automation

- `skills/` 14 个文件，三个技能包：`behavioral/listening-protocol`、`productivity/library-seat-booking`（含 7 个 references 与 2 个 `SKILL.md.bak*`）、`task-execution-decision`（含 2 个 references）
- `scripts/` 8 个文件：3 个抢座脚本（`book-seat.sh`、`book-seat-userC.sh`、`book-seat-zonghe.sh`）、3 个 `.bak_*` 历史版本、`book-seat-zonghe.py`、`seat-notify.py`
- `cron/` 111 个文件：`jobs.json` 与 4 个图书馆任务的历史输出目录（签到 `1 8 * * *`、签退 `30 21 * * *`、抢座 `17 19 * * *`、抢座-用户三 `20 19 * * *`）
- `memory/` 8 个文件：`memories/` 下 3 个 md 与 2 个 0 字节 `.lock`，`backups/seatfix-20260913/` 下 3 个修复前的备份

### deploy

`deploy/systemd/qfnu-library.service`：生产环境的 systemd 单元（364 字节），`WorkingDirectory=/opt/qfnulibrary`、`ExecStart=/opt/qfnulibrary/scripts/loop_seat.sh`、`Restart=always`。

### archive

四个子目录，均不参与运行：

- `legacy/`（11 个文件）—— 9 个 `.bak` 历史版本 + 2 个 Hermes `.db`。删除记录详见 [`archive/legacy/README.md`](../archive/legacy/README.md)
- `runtime-logs/`（8 个文件 / 318139 字节）—— 生产环境的完整运行日志快照，8 个 SHA256 两两不同
- `tmp-scripts/`（9 个文件）—— `/tmp` 下的排查脚本与 3 份座位日志
- `captcha/`（30 张）—— 生产环境调试用的验证码样本

### docs

`ORGANIZATION.md`（本文件）、`REVIEW_LOG.md`（三轮评审记录）、根目录的 `SPEC.md` 与 `PLAN.md`。

---

## 代码基准：为什么取开发版

2026-10-11 逐文件比对确认，**开发版是生产版的严格超集**：

| 维度 | 生产版 | 开发版 |
|---|---|---|
| `get_seat.py` 模式分支 | mode 1/2/3/4 | mode 1/2/3/4/**5** |
| `get_seat.py` 函数集合 | 6 个 | 7 个（多 `get_all_seats()`） |
| `config.py` 暂停开关 | 无 | `suspend: bool` 字段 + `SUSPEND` 解析 |
| `get_seat.py` mode 4/5 限制 | `if build_id != 22` 硬约束 | 已解禁 |
| `classrooms.py` 教室数 | 22 | 23（新增 ID 49 五楼自习区） |
| 限流识别 | 无 | 识别「访问频繁」与 `msg=null` |

开发版没有一行生产版有而它缺的代码。选择开发版意味着保留 `44811ed fix: 修复抢座时序偏差、限流误判与通知失效` 与 `5238227 feat: 设置指定座位优先模式` 两次经 15 轮端到端验证的改进。

生产版的独有内容只有 `logs/`（8 个运行日志）与 `.bak*`，两者都进了 `archive/`，没有丢失。

---

## 去重规则

重组时删除了仓库内所有长度 > 1024 字节且 SHA256 完全相同的重复文件，删除判据与逐条记录见 [`archive/legacy/README.md`](../archive/legacy/README.md)。

保留了两类例外：

- **0 字节文件（10 个）**：5 个 `src/**/__init__.py`、`tests/__init__.py`、`tests/fixtures/config_empty.yaml`、2 个 `.lock`、`archive/runtime-logs/loop_stdout.log`。它们 SHA256 相同但都是功能性文件，缺失会破坏导入或丢失「曾经为空」这一事实。
- **`src/debug_captcha/` 的 1150 张截图**：1184 张中 32 组内容相同，保留每组一份。目录保留在磁盘上但不纳入版本控制。

---

## 被 gitignore 排除的内容

| 路径 | 原因 |
|---|---|
| `src/debug_captcha/`（1150 张，约 170MB） | 验证码调试样本，体积大且可随时重新生成 |
| `web/static/logo.png` | 既有规则，与本次重组无关 |
| `web/flask_session/` | 运行期生成的会话目录 |
| `.pytest_cache/` | 运行期产物 |
| `extracted/hermes/history/library_messages.jsonl`（19MB / 20384 条） | Hermes 聊天记录，含真实姓名学号，保留在 `extracted/` 外层不入库 |
| `extracted/hermes/history/library_sessions.json`（730 字节） | 同上 |

仓库历史版本由 3 份 `.bak` 通配规则忽略（`*.bak`、`*.bak_*`、`*.bak.*`）。`.gitignore` 末尾追加了 5 条反选规则，让 `archive/legacy/` 与 `automation/` 下的历史版本真正入库：

```
!archive/legacy/**
!archive/legacy/*.bak*
!automation/scripts/*.bak_*
!automation/skills/**/*.bak_*
!automation/memory/**/*.bak*
```

反选规则必须放在通配规则之后才能生效，位置不可调换。

`.gitattributes` 固定了 `* text=auto eol=lf` 与三类 binary 规则。本机 `core.autocrlf=true`，实测现有文本文件全部已是 LF，因此该文件对当前内容零影响，只对未来新增文件与跨平台协作生效。4 个 `.sh` 以 `git update-index --chmod=+x` 显式设为 `100755`，仓库其余文件保持 `100644`。

---

## 敏感数据

以下内容**未脱敏**，按用户要求保留原样：

- `configs/user1.yml`、`user2.yml`、`user3.yml`、`archive/legacy/user1.yml.bak_20260911_191239` —— 学号与密码明文
- `data/seat_info/` 15 个 JSON —— 真实座位信息
- `automation/memory/MEMORY.md` —— 三名学生的真实姓名、学号、目标座位号
- `archive/tmp-scripts/seat-2023413*.log`、`archive/runtime-logs/*.log` —— 学号与请求响应体

仓库在 GitHub 上保持 **PRIVATE**（`Swcmb/MyQFNULibraryBook`）。本轮重组**零推送**，所有提交只存在于本地。

---

## 重新获取原始数据

| 需要什么 | 去哪里取 |
|---|---|
| 全部原始文件清单与 SHA256 | `qfnulibrary-download/pre-reorg-manifest.csv`（1691 行，仓库外） |
| 打包归档 | `qfnulibrary-download/archives/` 下 3 个 tar.gz 与 `extras/`、`hermes/`、`history/` 三个子目录 |
| 解包后的五组原始目录 | `qfnulibrary-download/extracted/{opt_qfnulibrary,MyQFNULibraryBook,hermes,systemd,extras}` |
| 下载记录 | `qfnulibrary-download/DOWNLOAD_MANIFEST.md` |
| 服务器原件 | `ssh root@47.104.159.142`，生产版在 `/opt/qfnulibrary`，开发版在 `/home/admin/MyQFNULibraryBook`，Hermes 资产在 `/home/admin/.hermes/` |

由于归并采用**复制式**，`extracted/` 下的五组目录与 `archives/` 的全部内容都保持原样未动，任何一份文件都能从这里重新取回。

---

## 整轮回滚

```powershell
git reset --hard ad613ea
Remove-Item -Recurse -Force automation, archive, deploy, docs, .gitattributes
git clean -nd   # 预演确认无其他残留
```

`<保存提交>`（`04a3a2e`）是工作区改动的固化点，`<合并提交>` 是重组内容。回滚到 `ad613ea` 后按本文件的分层表重新复制即可，无数据丢失。