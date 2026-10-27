# SPEC: 图书馆抢座系统仓库重组

## 修订记录

| 轮次 | 日期 | 结论 | 主要修正 |
|---|---|---|---|
| 初稿 | 2026-10-11 | — | 7 节 + 附录 A/B |
| 第 1 轮修订 | 2026-10-11 | CHANGES REQUESTED（20 条） | 代码基准改为开发版；`.bak` 入库；去重改磁盘全量；pytest 先装依赖 |
| 第 2 轮修订 | 2026-10-11 | CHANGES REQUESTED（15 条） | `.gitignore` 反选补全 5 处；去重判据与验证码交叉重复闭环；字节判据改为「blob == 磁盘」（实测成立）；AC-13/28 命令重写；`.sh` 显式 chmod +x；新增前置快照 |

### 第 1 轮处置台账（20 条，全部已修正）

| 级别 | 发现 | 修正 |
|---|---|---|
| Blocking | B-1 FR-3.2 的 `.bak` 落位与 FR-1.1/1.2/1.4 冲突 | 统一为「已指定落位者就地保留，其余进 `archive/legacy/`」 |
| Blocking | B-2 `.gitignore` 的 `*.bak` 通配让历史版本永不入库 | 新增 FR-4.8 反选规则（**第 2 轮补全至 5 处**） |
| Blocking | B-3 「1KB 以上重复组 = 0」不可达成且扫描范围未定义 | 判据改为磁盘全量 SHA256 去重；扫描范围明确 |
| High | H-1 生产版无 mode 5，`configs/user3.yml` 写 `MODE: '5'` → 覆盖后断裂 | **代码基准改为开发版**，mode 5 完整保留 |
| High | H-2 覆盖丢弃 4 项未提交改动 | 随开发版基准全部保留，登记为 A6 |
| High | H-3 `hermes/misc/` 实为 10 个文件 | FR-1.4 补全为 10 个，两个 `.db` 归 `archive/legacy/` |
| High | H-4 pytest 基线 60 项 + 8 collection error | 新增 NFR-0.4，先装 `pycryptodome` |
| High | H-5 多处计数与磁盘不符 | 按实测订正 |
| Medium ×10 | 源路径嵌套、AC 计数、字节统计命令、提交结构矛盾、`core.autocrlf`、幂等性、SSH 依赖、grep 命令、archives 子目录、脚本计数 | 逐条修正 |
| Low ×4 | pre-commit 误列、文档重复、漏 `listening-protocol`、AC-16 覆盖面 | 逐条修正 |

### 第 2 轮处置台账（15 条，全部已修正）

评审在临时目录中模拟 `git check-ignore` 与 PowerShell 扫描，结论 CHANGES REQUESTED：3 Blocking + 6 High + 6 Medium/Low。我对其数字主张逐项实测复核，其中 **3 条为评审误判**（见下方「评审误判」），其余 12 条已修正。

| 级别 | 发现 | 复核结论 | 本轮修正 |
|---|---|---|---|
| Blocking | F-1 `.gitignore` 反选只覆盖 2 处，skills 的 2 个 `.bak` 与 `jobs.json.bak` 仍不入库 | **成立**（评审实测可信） | FR-4.8 扩为 5 条反选；AC-23 扩为 4 项检查 |
| Blocking | F-2 `archive/captcha/` 与 `src/debug_captcha/` 有 2 个交叉重复，AC-10 与 AC-12 不可能同时成立 | **成立**，实测交叉重复 `bg_1789125485.png`=`bg_1789997438.png`(313751B)、`slider_1789125485.png`=`slider_1789997438.png`(10925B) | 用户裁决：删 `archive/captcha` 中这 2 张 → 该目录 30；`src/debug_captcha` 计数订正为 1150 |
| Blocking | F-3 AC-13 命令在 PS 5.1 下会误纳 `.git` 非 objects 文件、边界语义不清、异常静默 | **成立** | AC-13 命令重写：显式排除整个 `.git`、阈值写实为 `> 1024`、通过条件为「无输出行」 |
| High | F-4 `core.autocrlf=true` 使入库 blob 字节 > 磁盘字节，AC-2 的 16634 必然失败 | **误判**。实测 6 个未修改文件 blob 字节 **等于** 磁盘字节（README.md 6531=6531、LICENSE 1243=1243、`src/auth/login.py` 15950=15950、`src/crypto/aes.py` 2147=2147、`src/api/constants.py` 1164=1164、`src/get_info.py` 3328=3328）。`autocrlf=true` 只做 CRLF→LF 规范化，LF 文件入库不变 | AC-2 保留字节判据并补记实测证据；主判据改为内容断言（与行尾无关）；R-3 补记该结论 |
| High | F-5 4 处数字不符：日志 318139、`.pyc` 61、`__init__.py` 5、A6 重试口径 | **成立**，全部实测确认 | 全部按实测值订正；A6 改为「外层 `select_seat` 重试上限 300→100（L153/L312）」，删除与 HEAD 重复的「内层 10→3」 |
| High | F-6 AC-28 的 `git grep` 模式串在 PowerShell 下被拆词，零匹配 | **成立**。实测 `git grep -c 'mode == "5"'` 退出 1，`git grep -cE 'mode == .5.'` 返回 1 | AC-28 改用 `git grep -cE "elif config\.mode == .5."`；§5.1 补记该陷阱 |
| High | F-6 附带：`AC-22` 的 `scripts/loop_seat.sh` 尚不存在，`git check-attr` 返回 `unspecified` | **成立** | AC-22 补前置顺序；检查对象改为实测的 6 个 `.sh` 清单 |
| Medium | F-7 `.bak` 清单「27 个」vs 表格 21 行 | **数字成立、表格不成立**。实测全库 `.bak*` **27 个**（book 8 + opt 7 + hermes 6 + extras 6） | FR-1.11 重写为「27 个来源 → 去重后 `archive/legacy/` 保留 9 个 + 2 个 `.db` = 11 个」，附实测字节与哈希 |
| Medium | F-8 FR-3.2 表第 5 组「assets 全套等」无保留判据 | **成立** | 改为「`opt/` 侧一律不落位，仓库内只存在 book 侧一份」 |
| Medium | F-9 `extras/opt_*` 的 6 个 `.bak` 与 `opt/` 内同名文件同内容，重复收编 | **成立**（实测哈希两两相同） | FR-1.11 明确 `extras/opt_*` 的 6 个不收编，随原目录保留 |
| Medium | F-10 AC-20「与安装后立即采集的基线一致」恒真 | **成立** | AC-20 改为「退出码 0 且无 error 行」，收集项数作为证据写入验收报告 |
| Medium | F-11 AC-5「可执行位」在 Windows 不可验证；NFR-5.4「8 个 `.sh`」无来源 | **成立**。实测仓库 92 个已跟踪文件全为 `100644`；`extracted/` 下 `.sh` 共 6 个 | 用户裁决：显式 `git update-index --chmod=+x`；AC-5 改为验 `git ls-files -s` 的 mode；NFR-5.4 改为实测 6 个并列出清单 |
| Medium | F-14 缺「不可逆操作前置快照」 | **成立** | 新增 FR-3.6：动手前导出 `pre-reorg-manifest.csv`（仓库外）；NFR-8.2 补「`archive/` 源自 `extracted/` 原目录，回滚后重新复制即可」 |
| Low | F-12 R-12 引用错误字节数且「各不相同」未验证 | **成立** | 改为 318139，附 8 个日志实测哈希前 8 位（两两不同） |
| Low | F-13 A1/A2/A4/A5/A7 标为假设但已是事实或裁决 | **成立** | 移入「已验证事实」与「用户裁决」小节 |
| Low | F-15 §5.3 漏 `assets/` | **成立** | 补入，14 文件 3086209 字节 |

**评审误判（3 条，已实测排除）**：F-4（blob 字节）、F-7 中的「磁盘仅 15 个 `.bak`」、F-1 中「`.git` 内 29 个文件参与 AC-13」。

### 第 3 轮处置台账（10 条，全部已修正）

第 3 轮为三轮硬上限的终审，结论 CHANGES REQUESTED（5 Blocking + 5 Medium/Low）。该轮**独立复现并确认**了 `.gitignore` 5 条反选对 17 个目标路径 17/17 入库、`pycryptodome 3.24.0` 安装后 `pytest --collect-only -q` 退出码 0 且 **148 tests collected 0 error**、AC-19/AC-29 通过、`git update-index --chmod=+x` 在 Windows 实测成功、NFR-2.1 十项计数（除 `debug_captcha` 外）全对。我对其 5 条阻塞项逐项实测后全部确认成立，已全部修正：

| 级别 | 发现 | 复核 | 本轮修正 |
|---|---|---|---|
| Blocking | F-1 `src/` 下 8 个 `.bak` 若原位保留，会与 `archive/legacy/` 中 4 个同 SHA256 副本构成 4 组重复，AC-13 输出假失败 | **成立**（4 组：`4B11C151` 11453B、`E90ECB0C` 13916B、`D7658744` 12596B、`FD0A4A7B` 11368B） | FR-3.2 去重规则新增第 4 条「`src/` 下 8 个 `.bak` 原位副本一律删除」；FR-1.11 新增「第七组」处置表；重复组表由 6 组扩为 8 组 |
| Blocking | F-3 `src/debug_captcha` 唯一文件数算错 | **成立，但三轮均未算对**。第 1 轮我写 1152、第 2 轮评审写 1150、第 3 轮我写 1118。**Step 6 实测定案**：1184 文件 → **32 组重复 / 34 个冗余副本 / 1150 唯一**（组规模分布实测：32 组各含 2 份，无 3 份组）。34 = 1184 − 1150 | 全篇 1118 → 1150、66 → 34、1423 → 1455；FR-3.3、R-10、AC-12、NFR-2.1、附录同步订正 |
| Blocking | F-5 `git grep -cE 'retries < 100'` 期望值写 2 | **成立**。实测返回 **1**（仅 L153 `while not flag and retries < 100:`；L312 为 `retries >= 100`） | NFR-1.3 与 AC-2 期望值改为 1，并补记行号依据 |
| Blocking | F-10 落位后 0 字节文件写「9 个」 | **成立**。实测 **10** 个（`src/` 下 5 个 `__init__.py`、`tests/__init__.py`、`tests/fixtures/config_empty.yaml`、`automation/memory/memories/` 下 2 个 `.lock`、`archive/runtime-logs/loop_stdout.log`） | FR-3.2 规则 1、A8 枚举同步改为 10 个并列出完整路径 |
| Blocking | F-2 落位后总文件数口径未闭环 | **成立** | FR-3.2 新增文件总数口径表：落位后删除前 **309** → 执行删除后（不含 `debug_captcha`）**305** → 含 `debug_captcha` 1150 共 **1455**；已验证事实表同步订正 |
| Medium/Low | F-4 §5.1 `git check-attr` 未说明退出码恒为 0 | 成立 | 错误行为列改为「退出码恒为 0，判定必须解析输出文本」 |
| Medium/Low | F-6 AC-28 模式串过宽 | 成立 | 收紧为 `git grep -cE 'elif config\.mode == "5"'`（单引号包裹） |
| Medium/Low | F-7 §5.1 `git commit` 误列 pre-commit 钩子行为 | 成立 | 改为「本仓库无自定义钩子（`.git/hooks/` 仅含 `*.sample`）」 |
| Medium/Low | F-8 文档内部重复陈述 | 成立 | 去重 |
| Medium/Low | F-9 `.gitattributes` `* text=auto eol=lf` 的 CRLF 影响面 | **部分误判**。实测 220 个受检文本文件中仅 1 个含 CRLF —— `.pytest_cache/README.md`，属 gitignored 的运行时产物 | FR-4.7 补记「对现有文件零影响」的实测结论；R-14 保留为已知权衡 |

**3 轮累计**：第 1 轮 20 条、第 2 轮 15 条（3 条经实测排除）、第 3 轮 10 条，共 45 条发现，其中 3 条为评审误判。经用户授权（2026-10-11），第 3 轮修订完成后直接进入 Step 5 编写 PLAN.md，不再送第 4 轮。

### 已验证事实（2026-10-11 实测，非假设）

| 事实 | 实测值 | 验证命令 |
|---|---|---|
| `.bak*` 全库总数 | 27（book 8 + opt 7 + hermes 6 + extras 6） | `Get-ChildItem extracted -Recurse -Filter '*.bak*'` |
| `autocrlf` 规范化 | blob 字节 == 磁盘字节（LF 文件不变） | `git cat-file -s (git rev-parse HEAD:<f>)` |
| `src/debug_captcha` 重复 | 1184 文件 → 32 组重复 → **1150** 唯一 | `Group-Object {Get-FileHash $_ -Algorithm SHA256}` |
| 验证码交叉重复 | 2 组（`archive/captcha` ↔ `src/debug_captcha`） | 同上，跨目录比对 |
| 落位后总文件数 | 309（去重前）→ 305（删除后，不含 `debug_captcha`）→ 1455（含 1150 张验证码） | 见 FR-3.2 |
| `retries < 100` 匹配数 | 1（仅 L153） | `git grep -cE 'retries < 100' -- src/get_seat.py` |
| 落位后 0 字节文件 | 10 个，构成一组 SHA256 相同重复 | `Get-ChildItem -Recurse -File | Where-Object Length -eq 0` |
| 文本文件行尾 | 220 个受检文件中仅 `.pytest_cache/README.md` 含 CRLF（gitignored 运行时产物） | 逐文件扫描 `\r\n` |
| 仓库可执行位 | 已跟踪文件 92 个全为 `100644`，无 `100755` | `git ls-files -s \| Select-String 100755` |
| pytest 环境 | Python 3.13.9、pytest 8.4.2，仅缺 `pycryptodome` | `pip list` |

### 用户裁决（2026-10-11）

| 议题 | 裁决 |
|---|---|
| mode 5 去留 | 开发版为代码基准，mode 5 完整保留 |
| 4 项未提交改动 | 全部保留 |
| `.bak` 是否入库 | 入库，`.gitignore` 末尾追加反选 |
| pytest 基线 | 先装依赖再定基线 |
| hermes 侧 5 个未定义文件 | 两个 `.db` 进 `archive/legacy/`；2 个 `.lock` 与 `jobs.json.bak` 随 `automation/memory/` 原样保留 |
| `archives/` 子目录 | 三个子目录与顶层 tar.gz 一并保留原位，不入库 |
| `extracted/` 原始目录 | 复制式归并，五组原始目录全部保留不删除 |
| 生产版运行日志 | 收进 `archive/runtime-logs/` 并入库 |
| 验证码样本去重 | 一并去重（1184 → 1150） |
| 验证码交叉重复 | **删 `archive/captcha/` 中 2 张，该目录变 30** |
| `.sh` 可执行位 | **显式 `git update-index --chmod=+x` 入库为 100755** |

---

## 1. 背景

曲阜师范大学图书馆座位自动预约系统的代码散落在服务器 47.104.159.142 的两处，并配套一整套 Hermes 智能体侧自动化资产。2026-10-11 已将全部内容下载到本机 `qfnulibrary-download/`，解包后得到 `extracted/` 下五组并列目录。

两份代码的关系经实测确认为**开发版是生产版的严格超集**：

| 维度 | 生产版 `/opt/qfnulibrary` | 开发版 `MyQFNULibraryBook` |
|---|---|---|
| `get_seat.py` 模式分支 | mode 1/2/3/4（L133/146/156/164） | mode 1/2/3/4/5（L185/198/208/216/268） |
| `get_seat.py` 函数集合 | 6 个 | 7 个（多 `get_all_seats()`） |
| `config.py` 暂停开关 | 无 | `suspend: bool`（L36）+ `SUSPEND` 解析（L81） |
| `get_seat.py` mode 4/5 限制 | L166 `if build_id != 22` 硬约束 | 已解禁 |
| `classrooms.py` 教室数 | 22 | 23（新增 ID 49 五楼自习区） |
| 限流识别 | 无 | 识别「访问频繁」与 `msg=null` |
| `logs/` 运行日志 | 8 个文件 318139 字节 | 无此目录 |
| 工作区状态 | — | 5 个已修改未提交 + 1 未跟踪 |

开发版的额外能力来自两次经 15 轮端到端验证的提交：`44811ed fix: 修复抢座时序偏差、限流误判与通知失效` 与 `5238227 feat: 设置指定座位优先模式`。用户于 2026-10-11 决定**以开发版为代码基准**。

当前待解决的问题：

1. 五组目录并列存放，文件用途与生命周期不透明
2. 全库存在 100 组以上重复文件
3. 61 个 `.pyc`（分布在 7 个 `__pycache__/`）、27 个 `.bak*`、3 个 tar.gz 归档（199MB）、1184 张验证码截图混杂在有效内容中
4. 无组织说明文档

受益者：该系统维护者本人，以及未来接手的开发者。

## 2. 目标

### 2.1 目标（可验证）

- **G-1**：五组来源内容以**复制式归并**为单一自包含 Git 仓库。原始 `extracted/` 下五组目录全部保留不删除，可回溯来源
- **G-2**：目录按角色分层，读者可依据所在层级判断文件用途与生命周期
- **G-3**：仓库根下长度 > 1024 字节的文件按 SHA256 分组后重复组数为 0（`.git` 与 `archives/` 除外）
- **G-4**：工作区原有 5 个未提交改动与 1 个未跟踪文件在重组后完整保留
- **G-5**：`docs/ORGANIZATION.md` 说明每一层的职责、来源与取舍规则
- **G-6**：`git status --porcelain` 为空，且本轮零推送
- **G-7**：`archive/legacy/` 与 `automation/` 下的历史版本真正纳入版本控制

### 2.2 非目标（明确排除）

- 推送 GitHub、创建 PR、创建新 GitHub 仓库
- 修改服务器 47.104.159.142 上的任何文件或服务状态
- 代码功能变更、依赖升级、测试重写、格式化
- 改写任何现有文件的内容（仅做位置归并、去重删除、新增文档与 `.gitattributes`、mode 位设置）
- 将 `src/debug_captcha/` 纳入版本控制（保留在磁盘）
- 脱敏 `configs/user*.yml` 明文凭据、`data/seat_info/` 座位数据、`automation/memory/MEMORY.md` 中的真实姓名学号
- 引入 CI/CD、lint 配置、pre-commit 钩子
- 修复 `tests/test_classrooms.py` 当前已存在的 2 项失败（见 R-9）

## 3. 功能需求

### 3.1 FR-1 目录分层重组

仓库根为 `qfnulibrary-download/extracted/MyQFNULibraryBook/MyQFNULibraryBook`（沿用现有 `.git`，不重新 `git init`）。

```
├── src/ tests/ web/ configs/ data/ assets/ scripts/   ← 程序本体（开发版）
├── automation/          ← 自动化调度
│   ├── skills/ scripts/ cron/ memory/
├── deploy/systemd/      ← 部署配置
├── archive/             ← 历史存档
│   ├── legacy/ runtime-logs/ tmp-scripts/ captcha/
└── docs/                ← 组织说明
```

**FR-1.1** `automation/skills/` 收编 `extracted/hermes/skills/skills/`，三个技能目录（`behavioral/`、`productivity/`、`task-execution-decision/`）层级一律原样保留。文件数须为 **14**。

**FR-1.2** `automation/scripts/` 收编 `extracted/hermes/scripts/scripts/` 下 8 个文件，保持原文件名：`book-seat.sh`(3817)、`book-seat.sh.bak_20260914_192712`(4293)、`book-seat.sh.bak_notify`(2151)、`book-seat.sh.bak_notifyfix_20260914_193052`(5452)、`book-seat-userC.sh`(2610)、`book-seat-zonghe.py`、`book-seat-zonghe.sh`(451)、`seat-notify.py`。文件数须为 **8**。其中 3 个 `.sh` 须以 mode `100755` 入库（FR-3.7）。

**FR-1.3** `automation/cron/` 收编 `extracted/hermes/cron/cron/jobs.json` 与 `output/` 下 4 个图书馆任务的历史输出目录，保持 `automation/cron/jobs.json` 与 `automation/cron/output/<id>/` 层级。文件数须为 **111**，总字节 **320819**。

**FR-1.4** `automation/memory/` 收编 `extracted/hermes/misc/` 下 8 个文件：

| 文件 | 字节 | 落位 |
|---|---:|---|
| `memories/MEMORY.md` | 3523 | `automation/memory/` |
| `memories/USER.md` | 1005 | 同上 |
| `memories/user_profile.md` | 3566 | 同上 |
| `memories/MEMORY.md.lock` | 0 | 同上 |
| `memories/USER.md.lock` | 0 | 同上 |
| `backups/seatfix-20260913/get_seat.py` | 11453 | `automation/memory/backups/seatfix-20260913/` |
| `backups/seatfix-20260913/book-seat.sh` | 1546 | 同上 |
| `backups/seatfix-20260913/jobs.json.bak` | 11848 | 同上 |

`hermes/misc/` 下另 2 个文件 `kanban.db`(118784) 与 `verification_evidence.db`(32768) 按 FR-1.11 归 `archive/legacy/`。

**FR-1.5** `deploy/systemd/` 收编 `extracted/systemd/qfnu-library.service`（364 字节），文件名不变。文件数须为 **1**。

**FR-1.6** `archive/tmp-scripts/` 收编 `extracted/extras/tmp/` 下 9 个文件：`book-seat-new.sh`(2022)、`check_seat.py`(1082)、`get_seat.pre_mode5.py`(15875)、`patch_seat.py`(3473)、`probe_seats.py`(1063)、`seat-<学号A>.log`(28342)、`seat-<学号B>.log`(28341)、`seat-<学号C>.log`(117842)、`seats2.py`(793)。文件数须为 **9**。

> **脱敏说明（2026-10-11 追加）**：三个 `seat-*.log` 的原始文件名含真实学号，本文已替换为占位符。原始文件名与本机完整副本见 `qfnulibrary-download/extracted/extras/tmp/`（仓库外）。

**FR-1.7** `archive/captcha/` 收编 `extracted/extras/opt_debug_captcha/debug_captcha/` 下 32 个文件（16 bg + 16 slider），并**删除其中与 `src/debug_captcha/` 交叉重复的 2 个**：`bg_1789125485.png`（与 `bg_1789997438.png` 同为 313751 字节、SHA256 相同）、`slider_1789125485.png`（与 `slider_1789997438.png` 同为 10925 字节）。文件数须为 **30**。

**FR-1.8** `archive/runtime-logs/` 收编生产版 `extracted/opt_qfnulibrary/opt/qfnulibrary/logs/` 下 8 个运行日志：`checkin.log`(12183)、`library_seat.err.log`(4462)、`library_seat.log`(38)、`loop.log`(5117)、`loop_stdout.log`(0)、`manual_seat_20260911_190034.log`(97563)、`seat.log`(194762)、`signout.log`(4014)。文件数须为 **8**，总字节 **318139**。8 个文件 SHA256 两两不同。

**FR-1.9** `docs/ORGANIZATION.md` 新建，内容覆盖：五层职责定义、每层内容来自哪个下载分组、去重与代码基准的取舍规则、哪些内容被 gitignore 及原因、重新获取原始数据的方法。

**FR-1.10** 归并为**复制式**：`extracted/` 下五组原始目录全部保留不删除。`qfnulibrary-download/archives/` 下顶层 3 个 tar.gz 与三个子目录（`extras/` 4 文件 4.14MB、`hermes/` 4 文件 0.07MB、`history/` 1 文件 4.55MB）一并保留原位，不进入仓库。

**FR-1.11** `archive/legacy/` 收编两类内容。

**第一类：`.bak*` 文件。** 全库 27 个 `.bak*` 的去向如下。

| 来源 | 文件 | 字节 | SHA256 前 8 | 去向 |
|---|---|---:|---|---|
| `opt/scripts/` | `run_all.py.bak_20260911_081029` | 9521 | `A4D11F23` | 删除（与活文件 `scripts/run_all.py` 同内容） |
| `opt/src/` | `check_in.py.bak_20260911_081029` | 2543 | `2A27C0D8` | 删除（与活文件 `src/check_in.py` 同内容） |
| `book/src/auth/` | `token.py.bak_20260914_193704` | 3011 | `EB064AE1` | 删除（与活文件 `src/auth/token.py` 同内容） |
| `book/src/` | `get_seat.py.bak_mode5` | 15875 | `9879BE8C` | 删除（与 `archive/tmp-scripts/get_seat.pre_mode5.py` 同内容） |
| `book/src/` | `get_seat.py.bak_fallbackfix` | 11453 | `D4BC9DD2` | 删除（与 `automation/memory/backups/seatfix-20260913/get_seat.py` 同内容） |
| `book/src/` | `get_seat.py.bak_sleep_20260912_195350` | 11453 | `D4BC9DD2` | 删除（同上） |
| `extras/opt_scripts/` | 3 个 | — | — | **不收编**，随原目录保留（与 `opt/` 内同名文件同内容） |
| `extras/opt_src/` | 3 个 | — | — | **不收编**，同上 |
| `hermes/skills/` | `SKILL.md.bak_20260913`、`SKILL.md.bak_m5` | 8464 / 10220 | — | `automation/skills/`（FR-1.1） |
| `hermes/scripts/` | `book-seat.sh.bak_20260914_192712`、`.bak_notify`、`.bak_notifyfix_20260914_193052` | 4293 / 2151 / 5452 | — | `automation/scripts/`（FR-1.2） |
| `hermes/misc/` | `jobs.json.bak` | 11848 | `41FE97AD` | `automation/memory/backups/`（FR-1.4） |

**第七组（`src/` 原位副本删除）**：`src/` 下 8 个 `.bak*` **不在原位保留**，全部删除。其中 4 个的 SHA256 与 `archive/legacy/` 中的副本相同，属纯重复副本：

| 文件 | 字节 | SHA256 前 8 | 去向 |
|---|---|---|---|
| `book/src/get_seat.py.bak_20260912_195204` | 11453 | `4B11C151` | 删除（`archive/legacy/` 已有同内容副本） |
| `book/src/get_seat.py.bak_20260914_192712` | 13916 | `E90ECB0C` | 删除（同上） |
| `book/src/get_seat.py.bak_directpost` | 12596 | `D7658744` | 删除（同上） |
| `book/src/get_seat.py.bak_nosleep_20260912_195441` | 11368 | `FD0A4A7B` | 删除（同上） |

其余 4 个（`bak_mode5`、`bak_fallbackfix`、`bak_sleep_20260912_195350`、`token.py.bak_20260914_193704`）已在上表第 1–6 条中记录删除原因。

**保留在 `archive/legacy/` 的 9 个 `.bak*`：**

| 文件 | 字节 |
|---|---:|
| `book/src/get_seat.py.bak_20260912_195204` | 11453 |
| `book/src/get_seat.py.bak_20260914_192712` | 13916 |
| `book/src/get_seat.py.bak_directpost` | 12596 |
| `book/src/get_seat.py.bak_nosleep_20260912_195441` | 11368 |
| `opt/configs/user1.yml.bak_20260911_191239` | 1043 |
| `opt/scripts/loop_seat.sh.bak_20260911_192300` | 993 |
| `opt/scripts/run_all.py.bak_20260911_190528` | 9753 |
| `opt/src/get_seat.py.bak_20260911_190528` | 11368 |
| `opt/src/sign_out.py.bak_20260911_190528` | 3197 |

**第二类：Hermes 数据库。** `kanban.db`(118784)、`verification_evidence.db`(32768)。

`archive/legacy/` 最终文件数 = 9 + 2 = **11**。

### 3.2 FR-2 代码基准（开发版）

**FR-2.1** 仓库中 `src/`、`tests/`、`configs/`、`scripts/`、`assets/`、`data/`、`web/`、`AGENTS.md`、`LICENSE`、`README.md`、`pytest.ini`、`requirements.txt`、`.gitignore` 全部保持开发版现状，不做内容变更。

**FR-2.2** 收编生产版独有的 `scripts/loop_seat.sh`（993 字节，mode `100755`）。该文件是 systemd 单元 `qfnu-library.service` 的 `ExecStart` 目标。

**FR-2.3** 保留开发版当前工作区的 5 个已修改文件与 1 个未跟踪文件，不回退：

| 文件 | 未提交改动内容 | 工作区实测位置 |
|---|---|---|
| `src/config/config.py` | 新增 `suspend: bool = False` 字段与 `SUSPEND` 解析 | L36、L81 |
| `configs/user1.yml` | 新增 `SUSPEND: false`；`DATE` 为 `"tomorrow"` | — |
| `configs/user2.yml` | 新增 `SUSPEND: false` | — |
| `src/get_seat.py` | 解禁 mode 4/5 的 `build_id != 22` 检查；新增 `get_all_seats()`；新增 mode 5 分支；**外层 `select_seat` 重试上限 300→100** | L153、L268、L312 |
| `src/classrooms.py` | 新增 `"东校区图书馆-五楼自习区（南）（东区房间静音）": 49` | — |

内层 `post_with_retry` 的 `max_retries=3`（L115）已在 HEAD 中，属 `44811ed` 提交内容，非工作区改动。

**FR-2.4** 工作区改动在重组前先提交一次，形成可回退点。

**FR-2.5** 生产版与其独有内容（`logs/`、`.bak*`）仅作为参考与存档来源，不参与代码基准。

### 3.3 FR-3 去重与清理

**FR-3.1** 删除全部 `__pycache__/` 目录及其 `.pyc` 文件（**61 个 `.pyc`，分布在 7 个 `__pycache__/` 目录**）。

**FR-3.2** 去重判据：最终落位后，**仓库根下长度 > 1024 字节的文件**（排除 `.git/`）按 SHA256 分组，每组保留一份，其余删除。判据口径三条：

1. `> 1024` 字节，排除 0 字节文件。实测落位后有 **10** 个 0 字节文件（`src/` 下 5 个 `__init__.py`、`tests/__init__.py`、`tests/fixtures/config_empty.yaml`、`automation/memory/memories/` 下 2 个 `.lock`、`archive/runtime-logs/loop_stdout.log`）构成一组 SHA256 相同的重复，其中多个是功能性文件（`__init__.py` 缺失会破坏包导入），一律保留
2. 与活文件或 `automation/memory/backups/` 下备份同内容的 `.bak` 副本一律删除，保留活文件/备份（见 FR-1.11 处置表）
3. `opt/` 侧与 `book/` 侧同内容的文件**一律不落位**：`extracted/opt_qfnulibrary/` 原目录保留，仓库内只存在 `book/` 侧一份，无需去重
4. `src/` 下的 8 个 `.bak*` **原位副本一律删除**（其中 4 个的 SHA256 与 `archive/legacy/` 中的副本相同，见 FR-1.11 处置表第 7 组），`archive/legacy/` 保留一份即可

**去重后仓库文件总数口径**：`src/debug_captcha/` 不计入该数（gitignored，且 FR-3.3 单独验收）。

| 阶段 | 文件数 |
|---|---:|
| 落位完成、删除动作执行前 | 309（`book` 侧基线 99 + automation 130 + archive 60 + loop_seat.sh 1 + 两个 `.db` 2 + 9 个 `.bak` 9 + 新增文档 5 + 待删的 4 个 `src/` 原位 `.bak` 另计） |
| 执行 FR-3.2 的删除后（不含 `src/debug_captcha/`） | **305** |
| 含 `src/debug_captcha/` 1150 个 | 1455 |

落位后模拟实测共 8 组重复，全部由上述规则覆盖：

| 组 | 内容相同者 | 处置 |
|---|---|---|
| 1 | `scripts/run_all.py`(9521) = `run_all.py.bak_20260911_081029` | 保留活文件 |
| 2 | `src/check_in.py`(2543) = `check_in.py.bak_20260911_081029` | 保留活文件 |
| 3 | `src/auth/token.py`(3011) = `token.py.bak_20260914_193704` | 保留活文件 |
| 4 | `automation/memory/backups/seatfix-20260913/get_seat.py` = `get_seat.py.bak_fallbackfix` = `get_seat.py.bak_sleep_20260912_195350`（均 11453，SHA256 `D4BC9DD2`） | 保留 memory 下那份，删除两个 `.bak` |
| 5 | `archive/tmp-scripts/get_seat.pre_mode5.py` = `get_seat.py.bak_mode5`（均 15875，SHA256 `9879BE8C`） | 保留 tmp-scripts 下那份，删除 `.bak` |
| 6 | `archive/legacy/get_seat.py.bak_20260912_195204` = `src/get_seat.py.bak_20260912_195204`（11453，SHA256 `4B11C151`） | 保留 archive/legacy 那份，删除 `src/` 原位副本 |
| 7 | `archive/legacy/get_seat.py.bak_20260914_192712` = `src/` 原位副本（13916，SHA256 `E90ECB0C`） | 同上 |
| 8 | `archive/legacy/get_seat.py.bak_directpost` = `src/` 原位副本（12596，SHA256 `D7658744`） | 同上 |
| — | `archive/legacy/get_seat.py.bak_nosleep_20260912_195441` = `src/` 原位副本（11368，SHA256 `FD0A4A7B`） | 同上（并入第 6–8 组处置） |

**FR-3.3** 去重后 `src/debug_captcha/` 文件数须为 **1150**（1184 文件中 32 组重复、冗余副本 34 个；32 组各含 2 份）。

**FR-3.4** `archive/legacy/README.md` 须逐条列出每一份被删除副本的原路径、字节数、与哪份文件内容相同，涵盖 FR-1.11 处置表的全部删除记录（表格前 6 条 + 第七组 4 个 `src/` 原位副本，共 10 条）与 `extras/opt_*` 的 6 个不收编文件。

**FR-3.5** `src/debug_captcha/` 保留在磁盘上但不纳入版本控制。

**FR-3.6 重组前置快照**：Step 6 动手前，把 `extracted/` 下五组目录的完整文件清单与 SHA256 导出为 `qfnulibrary-download/pre-reorg-manifest.csv`（仓库外，不入库），作为一切删除操作的唯一回滚依据。

**FR-3.7 可执行位**：`scripts/loop_seat.sh` 与 `automation/scripts/` 下 3 个 `.sh` 共 4 个文件，入库时 mode 须为 `100755`，通过 `git update-index --chmod=+x` 设置。

### 3.4 FR-4 版本控制

**FR-4.1** 保留现有 `.git` 目录与 3 条提交历史，不重新初始化，不重写历史。

**FR-4.2** 保留 `origin` 远端配置（`https://github.com/Swcmb/MyQFNULibraryBook.git`）。

**FR-4.3** 全部提交落在 `main` 分支，不创建分支，不 rebase，不 force push。

**FR-4.4** 最终 `git status --porcelain` 输出为空。

**FR-4.5** 不执行任何 `git push`。

**FR-4.6** 提交结构：

| 提交 | 内容 |
|---|---|
| `<保存提交>` | 仅含 FR-2.3 的 5 个已修改文件与 `configs/user3.yml` |
| `<合并提交>` | 其余全部重组内容 + `SPEC.md` + `PLAN.md` + `docs/REVIEW_LOG.md` + `.gitattributes` + `docs/ORGANIZATION.md` + `archive/legacy/README.md` + `.gitignore` 追加 |

父提交关系：`ad613ea → <保存提交> → <合并提交>`。

**FR-4.7** 新增 `.gitattributes`：

```
* text=auto eol=lf
*.png binary
*.jpg binary
*.gz binary
```

用于在 `core.autocrlf=true` 的 Windows 环境下固化 LF 行尾，并排除二进制文件。

**已实测（本条对当前仓库为无操作）**：220 个受检文本文件中仅 1 个含 CRLF —— `.pytest_cache/README.md`，属 gitignored 的运行时产物；`src/`、`tests/`、`configs/`、`web/`、`*.sh`、`*.md`、`*.yml`、`*.json` 全部已是 LF。因此 `* text=auto eol=lf` 对现有文件零影响，仅对未来新增文件与跨平台协作生效。

**FR-4.8** 在 `.gitignore` 末尾追加反选规则（必须位于既有通配规则之后）：

```
# archive/legacy/ 与 automation/ 中的历史版本需要入库（覆盖上方的 *.bak 通配）
!archive/legacy/**
!archive/legacy/*.bak*
!automation/scripts/*.bak_*
!automation/skills/**/*.bak_*
!automation/memory/**/*.bak*
```

**FR-4.9** 生产版 8 个运行日志（`archive/runtime-logs/`）纳入版本控制。

### 3.5 FR-5 不入库内容

**FR-5.1** `extracted/hermes/history/library_messages.jsonl`（19MB，20384 条消息）与 `library_sessions.json`（730 字节）保留原位，不进入仓库。

**FR-5.2** `qfnulibrary-download/archives/` 下全部内容保留原位，不入库。

**FR-5.3** `DOWNLOAD_MANIFEST.md` 与 `pre-reorg-manifest.csv` 保留在 `qfnulibrary-download/` 根，不入库。

## 4. 非功能需求

### 4.1 NFR-0 运行环境

- **NFR-0.1** 操作系统 Windows，Shell PowerShell 5.1
- **NFR-0.2** Python 3.13.9，pytest 8.4.2
- **NFR-0.3** 已装依赖：`requests`、`opencv-python-headless`、`pyyaml`、`numpy`、`tenacity`、`flask`
- **NFR-0.4** 缺依赖：`pycryptodome`。Step 6 须先执行 `pip install pycryptodome`。依赖安装属于验证步骤，不属于本轮交付物

### 4.2 NFR-1 可回退性

- **NFR-1.1** 父提交关系为 `ad613ea → <保存提交> → <合并提交>`，`<保存提交>` 只含 FR-2.3 的 6 个对象
- **NFR-1.2** 从 `<保存提交>` 可取回 `src/get_seat.py`（磁盘 16634 字节）、`configs/user1.yml`（1138 字节）、`src/classrooms.py`（2480 字节）。实测 `core.autocrlf=true` 对 LF 文件不做改写，入库 blob 字节等于磁盘字节（对照：`README.md` 6531=6531、`src/auth/login.py` 15950=15950）
- **NFR-1.3** 主验证用内容断言（与行尾无关）：`git grep -cE "retries < 100" <保存提交> -- src/get_seat.py` 返回 **1**（实测仅 L153 `while not flag and retries < 100:` 匹配；L312 为 `retries >= 100`），`git grep -cE "def get_all_seats" <保存提交> -- src/get_seat.py` 返回 1
- **NFR-1.4** `git show <保存提交> --stat` 恰好显示 6 个文件变更

### 4.3 NFR-2 完整性

**NFR-2.1** 落位后文件计数（2026-10-11 实测基线）：

| 目录 | 期望计数 | 期望字节 |
|---|---:|---:|
| `automation/skills/` | 14 | 80114 |
| `automation/scripts/` | 8 | 27365 |
| `automation/cron/` | 111 | 320819 |
| `automation/memory/` | 8 | — |
| `deploy/systemd/` | 1 | 364 |
| `archive/legacy/` | 11 | — |
| `archive/tmp-scripts/` | 9 | 198833 |
| `archive/captcha/` | 30 | — |
| `archive/runtime-logs/` | 8 | 318139 |
| `src/debug_captcha/` | 1150（去重后，原 1184） | — |
| `assets/` | 14 | 3086209 |

**NFR-2.2** 未被移动的仓库内容 SHA256 与重组前一致：`web/` 5 个文件、`AGENTS.md`、`configs/user3.yml`、`scripts/performance_results.json`、`pytest.ini`、`requirements.txt`、`LICENSE`、`README.md`、`.gitignore`（除追加规则外的部分）。

**NFR-2.3** `src/` 下 19 个 `.py`（含 5 个 `__init__.py`）、`tests/` 下 14 个 `test_*.py` + `conftest.py` + `__init__.py`（共 16，与 `AGENTS.md` 一致）、`tests/fixtures/` 7 个 YAML 配置文件全部保留。

### 4.4 NFR-3 代码可运行性

- **NFR-3.1** `pytest.ini` 内容不变（`testpaths = tests`，`pythonpath = src`）
- **NFR-3.2** 不存在任何 `import src.*` 或 `import web.*` 形式的跨目录导入（重组前已验证零匹配）
- **NFR-3.3** `web/requirements.txt` 与根 `requirements.txt` 均保持原样
- **NFR-3.4** 装齐 `pycryptodome` 后，`pytest --collect-only -q` 退出码为 0 且无 error 行；收集项数作为证据写入验收报告
- **NFR-3.5** `automation/` 引入后不污染 pytest 收集范围（由 `testpaths = tests` 保证）

### 4.5 NFR-4 性能

- **NFR-4.1** `src/debug_captcha/` 的 1150 个文件被 gitignore 排除，不纳入版本控制
- **NFR-4.2** 仓库磁盘占用不超过 220MB
- **NFR-4.3** 单次 `git add -A` 处理的文件数不超过 500

### 4.6 NFR-5 兼容性

- **NFR-5.1** 既有 `.gitignore` 规则保留，追加反选规则置于其后（FR-4.8）
- **NFR-5.2** `automation/`、`archive/`、`deploy/`、`docs/` 不使用 `.gitignore` 覆盖
- **NFR-5.3** `data/seat_info/` 下 15 个中文名 JSON 保持 UTF-8 编码不变
- **NFR-5.4** 仓库内 6 个 `.sh` 保持 LF 行尾，由 `.gitattributes` 固化：`scripts/loop_seat.sh`、`automation/scripts/book-seat.sh`、`book-seat-userC.sh`、`book-seat-zonghe.sh`、`automation/memory/backups/seatfix-20260913/book-seat.sh`、`archive/tmp-scripts/book-seat-new.sh`
- **NFR-5.5** `automation/scripts/` 的 3 个 `.bak_*` 与 `automation/skills/` 的 2 个 `SKILL.md.bak*`、`automation/memory/` 的 `jobs.json.bak` 由 FR-4.8 反选规则纳入版本控制
- **NFR-5.6** `automation/scripts/` 的 3 个 `.sh` 与 `scripts/loop_seat.sh` 以 mode `100755` 入库（FR-3.7）

### 4.7 NFR-6 数据敏感性

- **NFR-6.1** `configs/user1.yml`、`user2.yml`、`user3.yml`、`user1.yml.bak_20260911_191239` 含学号与密码明文，保留原样，仓库保持 PRIVATE
- **NFR-6.2** `data/seat_info/` 15 个 JSON 含真实座位信息，保留原样
- **NFR-6.3** `automation/memory/MEMORY.md` 含三名学生真实姓名、学号、目标座位号，保留原样
- **NFR-6.4** `archive/tmp-scripts/seat-2023413*.log` 与 `archive/runtime-logs/*.log` 含学号与运行细节，保留原样
- **NFR-6.5** `archive/runtime-logs/manual_seat_20260911_190034.log` 与 `seat.log` 含请求响应体，保留原样
- **NFR-6.6** 上述内容全部不脱敏；本轮不改变仓库可见性

### 4.8 NFR-7 可维护性

- **NFR-7.1** `docs/ORGANIZATION.md` 中每一层须写明「职责」「来源分组」「是否参与运行」「典型操作」
- **NFR-7.2** `archive/legacy/README.md` 须逐条列出被去重副本的原始路径
- **NFR-7.3** 提交信息采用中文，遵循现有仓库风格（参见 `ad613ea`、`44811ed`、`5238227`）

### 4.9 NFR-8 可重入与失败恢复

- **NFR-8.1** 每一步的幂等判据：目标目录存在且文件数符合 NFR-2.1 即跳过
- **NFR-8.2** 整轮回滚命令序列：
  1. `git reset --hard ad613ea`
  2. `Remove-Item -Recurse -Force automation, archive, deploy, docs, .gitattributes`
  3. `git clean -nd` 预演确认无其他残留
  
  `archive/` 内容源自 `extracted/` 原目录（FR-1.10 复制式），回滚后按 FR-1.x 重新复制即可，无数据丢失
- **NFR-8.3** 重组过程中断后重跑，不得产生重复副本或遗漏文件
- **NFR-8.4** 一切删除操作以 `pre-reorg-manifest.csv`（FR-3.6）为回滚依据

## 5. 接口与数据

### 5.1 本轮涉及的命令接口

| 命令 | 输入 | 输出 | 错误行为 |
|---|---|---|---|
| `git commit` | 已暂存的变更 | 提交 SHA | 本仓库无自定义钩子（`.git/hooks/` 仅含 `*.sample` 模板） |
| `git cat-file -s <blob>` | blob SHA | 字节数 | 对象不存在时报 `fatal: Not a valid object name` |
| `git show <sha>:<path>` | 提交与路径 | 文件内容 | 路径不存在时报 `fatal: path '...' exists on disk, but not in '<sha>'` |
| `git rev-parse <sha>:<path>` | 提交与路径 | blob SHA | 同上 |
| `git check-ignore -v <path>` | 文件路径 | 命中的 ignore 规则 | 未被忽略时退出码 1 且无输出 |
| `git check-attr text eol -- <path>` | 文件路径 | 属性值 | **退出码恒为 0**，即使属性未定义或文件不存在；此时输出第三列为 `unspecified`。判定必须解析输出文本，仅看退出码不成立 |
| `git grep -cE '<pattern>' -- <path>` | 正则 | 匹配行数 | 无匹配时退出码 1 且无输出。**PowerShell 陷阱**：模式串含双引号时会被拆词导致零匹配，须用 `-E` 加 `.` 通配或 `-F` |
| `git update-index --chmod=+x <path>` | 文件路径 | 无输出 | 文件未跟踪时报 `fatal: ... does not exist in index` |
| `git ls-files -s <dir>` | 目录 | `<mode> <sha> <stage>\t<path>` | — |
| `pytest --collect-only -q` | 仓库根 | 测试项列表 | 导入失败时报 collection error 并以非零码退出 |

### 5.2 `.gitignore` 新增规则

追加于文件末尾（在既有 `*.bak` / `*.bak_*` / `*.bak.*` 规则之后）：

```
# archive/legacy/ 与 automation/ 中的历史版本需要入库（覆盖上方的 *.bak 通配）
!archive/legacy/**
!archive/legacy/*.bak*
!automation/scripts/*.bak_*
!automation/skills/**/*.bak_*
!automation/memory/**/*.bak*
```

另记录意图但本轮不产生忽略效果的注释：

```
# 图书馆聊天记录（19MB，含真实姓名学号，保留在仓库外不入库）
# extracted/hermes/history/library_messages.jsonl
# extracted/hermes/history/library_sessions.json
```

### 5.3 数据模型

本轮不新增任何数据结构。被移动内容的实体清单：

| 实体 | 载体 | 数量 | 约束 |
|---|---|---:|---|
| 程序源文件 | `src/**.py` | 19 | 开发版现状，含 5 个 `__init__.py` |
| 文档截图 | `assets/**` | 14 | 3086209 字节，内容不变 |
| 测试 | `tests/test_*.py` | 14 | 加 `conftest.py` + `__init__.py` 共 16 |
| 测试 fixture | `tests/fixtures/*.yaml` | 7 | 含 1 个 0 字节 `config_empty.yaml` |
| 配置 | `configs/*.yml` | 7 | 含 `user3.yml`，含明文凭据 |
| 座位数据 | `data/seat_info/*.json` | 15 | 内容不变，UTF-8，中文文件名 |
| 技能包 | `automation/skills/**` | 14 | 三级层级原样保留 |
| 调度脚本 | `automation/scripts/*` | 8 | 含 3 个 `.bak_*`、3 个 `.sh`（100755） |
| 定时任务 | `automation/cron/jobs.json` + 4 个 output 目录 | 111 | 320819 字节 |
| 记忆 | `automation/memory/**` | 8 | 含 2 个 0 字节 `.lock`，含敏感信息 |
| Hermes 数据库 | `archive/legacy/*.db` | 2 | kanban.db + verification_evidence.db |
| 服务单元 | `deploy/systemd/qfnu-library.service` | 1 | 364 字节 |
| 历史备份 | `archive/legacy/**` | 11 | 9 个 `.bak*` + 2 个 `.db`，需记录去重来源 |
| 生产运行日志 | `archive/runtime-logs/*` | 8 | 318139 字节，SHA256 两两不同 |
| 临时脚本 | `archive/tmp-scripts/*` | 9 | 含 3 个日志 |
| 生产版验证码 | `archive/captcha/*` | 30 | 原 32，删 2 个交叉重复 |
| 开发版验证码 | `src/debug_captcha/` | 1150（去重后，原 1184） | gitignore，不入库 |
| 说明文档 | `docs/*.md` | 3 | ORGANIZATION + REVIEW_LOG + 本 SPEC/PLAN |

### 5.4 生命周期

重组为一次性操作，无运行时状态机。产物为两条提交（`<保存提交>` + `<合并提交>`）+ 五份文档（`SPEC.md`、`PLAN.md`、`docs/REVIEW_LOG.md`、`docs/ORGANIZATION.md`、`archive/legacy/README.md`）+ 一个 `.gitattributes` + `.gitignore` 追加规则 + 一个仓库外清单 `pre-reorg-manifest.csv`。

## 6. 验收标准

**执行环境声明**：全部验收在仓库根 `E:\Files\Documents\deepseek-harness\default-workspace\qfnulibrary-download\extracted\MyQFNULibraryBook\MyQFNULibraryBook` 下以 PowerShell 5.1 执行。搜索类检查统一用 `git grep`（不用 `grep -r`），模式串避免双引号。

| 编号 | 关联 | 验证方式 | 通过条件 |
|---|---|---|---|
| AC-1 | NFR-1.1 | `git log --oneline -3` | 顶部 `<合并提交>`，其次 `<保存提交>`，再次 `ad613ea` |
| AC-2 | NFR-1.2 | `git grep -cE "def get_all_seats" <保存提交> -- src/get_seat.py` 与 `git grep -cE "retries < 100" <保存提交> -- src/get_seat.py` | 分别返回 1 与 **1**（辅证：`git cat-file -s (git rev-parse <保存提交>:src/get_seat.py)` = 16634） |
| AC-3 | NFR-1.4 | `git show <保存提交> --stat` | 恰好 6 个文件变更 |
| AC-4 | NFR-2.1 ① | `Get-ChildItem automation/skills -Recurse -File \| Measure-Object` | 计数 = 14，字节和 = 80114 |
| AC-5 | NFR-5.6 | `git ls-files -s automation/scripts/` | 计数 = 8；其中 3 个 `.sh` 的 mode 为 `100755` |
| AC-6 | NFR-2.1 ③ | 同上，`automation/cron` | 计数 = 111，总字节 = 320819 |
| AC-7 | NFR-2.1 ④ | 同上，`automation/memory` | 计数 = 8 |
| AC-8 | NFR-2.1 ⑤ | `Test-Path deploy/systemd/qfnu-library.service` | True，字节 = 364 |
| AC-9 | NFR-2.1 ⑥ | `Get-ChildItem archive/tmp-scripts -File \| Measure-Object` | 计数 = 9，总字节 = 198833 |
| AC-10 | FR-1.7 | 同上，`archive/captcha` | 计数 = 30 |
| AC-11 | FR-1.8 | 同上，`archive/runtime-logs` | 计数 = 8，总字节 = 318139 |
| AC-12 | FR-3.3 | 同上，`src/debug_captcha` | 计数 = 1150 |
| AC-13 | FR-3.2 | 见下方可复现命令 | 无任何输出行 |
| AC-14 | FR-3.1 | `Get-ChildItem -Recurse -Directory -Filter __pycache__` | 计数 = 0 |
| AC-15 | FR-1.9 | `Get-Content docs/ORGANIZATION.md` | 含五层职责、来源映射、去重规则、代码基准说明、gitignore 说明 |
| AC-16 | NFR-2.2 | 对 8 个对象逐一 `Get-FileHash -Algorithm SHA256`：`web/app.py`、`web/README.md`、`web/requirements.txt`、`web/static/logo.png`、`web/templates/index.html`、`AGENTS.md`、`configs/user3.yml`、`scripts/performance_results.json` | 8/8 与重组前记录一致 |
| AC-17 | NFR-2.3 | `Get-ChildItem src -Recurse -File -Filter *.py`、`Get-ChildItem tests -Recurse -File -Filter 'test_*.py'` | 19 / 14 |
| AC-18 | NFR-3.1 | `Get-Content pytest.ini` | 内容为 `testpaths = tests` + `pythonpath = src` |
| AC-19 | NFR-3.2 | `git grep -nE '^\s*import (src\|web)\.'` | 零匹配（退出码 1） |
| AC-20 | NFR-3.4 | `pip install pycryptodome` 后 `pytest --collect-only -q` | 退出码 0，输出无 error 行；收集项数写入验收报告 |
| AC-21 | NFR-4.1 | `git ls-files src/debug_captcha/ \| Measure-Object` | 计数 = 0 |
| AC-22 | NFR-5.4/FR-4.7 | 前置：FR-2.2 收编 `loop_seat.sh` 且 FR-4.7 写入 `.gitattributes` **之后**执行。`git check-attr text eol -- scripts/loop_seat.sh` 输出含 `eol: lf`；再对 NFR-5.4 列出的 6 个 `.sh` 检查磁盘行尾 | 两者均通过 |
| AC-23 | FR-4.8/G-7 | 四项并列检查 | ① `git ls-files archive/legacy/` 计数 = 11；② `git ls-files automation/scripts/` 计数 = 8（含 3 个 `.bak_*`）；③ `git ls-files automation/skills/` 计数 = 14 且其中含 2 个 `SKILL.md.bak*`；④ `git ls-files automation/memory/` 计数 = 8 且含 `jobs.json.bak` |
| AC-24 | FR-4.4 | `git status --porcelain` | 输出为空 |
| AC-25 | FR-5.1 | `Test-Path` 两个文件 | `...\extracted\hermes\history\library_messages.jsonl` 与 `library_sessions.json` 均为 True |
| AC-26 | FR-5.2 | `Get-ChildItem qfnulibrary-download\archives` | 3 个 tar.gz + 3 个子目录仍在原位 |
| AC-27 | FR-1.10 | `Test-Path` 五组原始目录 | `opt_qfnulibrary`、`MyQFNULibraryBook`、`hermes`、`systemd`、`extras` 均为 True |
| AC-28 | FR-2.1 | `git grep -cE 'config\.mode == .5.' -- src/get_seat.py`（PowerShell 下用单引号包裹模式串；`.` 代替字面双引号，`-E` 下 `.` 匹配任意字符，此处匹配 `"`） | 返回 1 |
| AC-29 | FR-2.3 | `git grep -c suspend -- src/config/config.py` | 返回 ≥ 2 |
| AC-30 | NFR-6.6 | `gh repo view Swcmb/MyQFNULibraryBook --json visibility` | 仍为 `PRIVATE` |
| AC-31 | FR-4.5 | 检查本轮 git 命令历史 | 无任何 `git push` |
| AC-32 | FR-3.6 | `Test-Path qfnulibrary-download\pre-reorg-manifest.csv` | True，行数与重组前文件总数一致 |
| AC-33 | FR-1.9 / NFR-6 | 人工检查 `archive/legacy/README.md` | 逐条列出 FR-1.11 的 6 条删除记录与 6 个不收编文件 |
| AC-34 | FR-4.7 | `Get-Content .gitattributes` | 含 `* text=auto eol=lf` 与 3 条 binary 规则 |
| AC-35 | — | **非阻塞手动项**：有 SSH 凭据时执行 `ssh root@47.104.159.142 'find /opt/qfnulibrary -type f \| wc -l'` 与 `DOWNLOAD_MANIFEST.md` 对比 | 记录实测值；无凭据时在验收报告中显式记为「未执行」 |

**AC-13 可复现命令**（在仓库根执行，通过条件为无任何输出）：

```powershell
$root = (Get-Location).Path.TrimEnd('\')
$dup = Get-ChildItem $root -Recurse -File -Force |
  Where-Object { $_.FullName -notlike "$root\.git\*" -and $_.Length -gt 1024 } |
  ForEach-Object {
    [pscustomobject]@{
      H = (Get-FileHash $_.FullName -Algorithm SHA256).Hash
      P = $_.FullName.Substring($root.Length + 1)
    }
  } |
  Group-Object H | Where-Object Count -gt 1
$dup | ForEach-Object { $_.Name + ' => ' + ($_.Group.P -join ', ') }
```

**AC-20 前置命令**（Step 6 须先执行）：

```powershell
pip install pycryptodome
pytest --collect-only -q
```

## 7. 风险与开放问题

### 7.1 风险

| 编号 | 风险 | 可能性 | 影响 | 缓解措施 |
|---|---|---|---|---|
| R-1 | 提交 `<保存提交>` 时若遗漏某个文件，`<合并提交>` 无法回退该改动 | 中 | 高 | FR-2.4 强制先提交；AC-3 验证恰好 6 个文件 |
| R-2 | `.sh` 脚本在 Windows 上无 mode 概念，入库默认 `100644`，Linux 上不可直接执行 | **确定** | 中 | FR-3.7 显式 `git update-index --chmod=+x`；AC-5 验证 mode |
| R-3 | Windows checkout 将 `.sh` 转成 CRLF，导致 Linux 上脚本报错 | 中 | 高 | FR-4.7 `.gitattributes`（`* text=auto eol=lf`）；AC-22 验证。**已实测**：`core.autocrlf=true` 对 LF 文件不做改写，blob 字节 == 磁盘字节，`.py`/`.yml`/`.json` 无 CRLF 规范化风险 |
| R-4 | 中文文件名在移动过程中编码损坏 | 低 | 中 | NFR-5.3；`data/seat_info/` 下 15 个中文名 JSON 逐一验证 SHA256 |
| R-5 | `automation/` 引入后污染 pytest 收集范围 | 低 | 低 | `testpaths = tests` 已限定；AC-20 验证 |
| R-6 | 去重时误删内容不同但文件名相似的文件 | 低 | 高 | 仅按 SHA256 完全一致才去重；`archive/legacy/README.md` 逐条记录 |
| R-7 | `.git` 历史中已含明文凭据 | 确定 | 高 | NFR-6.1 接受现状；仓库 PRIVATE；本轮不推送 |
| R-8 | `git add -A` 意外纳入 1150 张验证码截图 | 中 | 中 | NFR-4.1；AC-21 验证 |
| R-9 | `tests/test_classrooms.py` 存在 2 项失败（L12 断言 22 个教室、L17 断言 18 个唯一 ID，因新增教室 ID 49 而实际为 23/19）。采用开发版基准后该失败保留 | 确定 | 中 | 已知并接受。修复属代码变更，超出本轮非目标范围；本轮在验收报告中显式记录该状态。AC-20 只跑 `--collect-only`，不执行断言，与本项无冲突 |
| R-10 | 删除 34 个验证码冗余样本后失去时间序列完整性 | 低 | 低 | 用户已决定一并去重；`archive/legacy/README.md` 记录被删路径 |
| R-11 | `.gitignore` 反选规则位置或覆盖不全导致 `.bak` 仍不入库 | 中 | 高 | FR-4.8 反选置于通配之后且覆盖 5 处路径；AC-23 四项并列验证 |
| R-12 | 8 个运行日志若存在同内容副本，去重会删掉一个并使 AC-11 失败 | 低 | 中 | **已实测排除**：8 个日志 SHA256 两两不同（5639AD38、354E5852、020CA7DB、05808AB5、E3B0C442、A0FDBBB8、032D7749、4B85E048） |
| R-13 | 一次性重组 30+ 步中途失败，且删除操作不可逆 | 中 | 高 | FR-3.6 前置快照 `pre-reorg-manifest.csv`；NFR-8.2 回滚序列；NFR-8.1 幂等判据 |
| R-14 | `.gitattributes` 的 `* text=auto eol=lf` 使 Windows 端 checkout 后工作区全部为 LF，与编辑器默认 CRLF 预期不同 | 中 | 低 | 影响面限于工作区行尾显示，不改变 blob 内容；如后续出现问题可改为按扩展名逐条声明 |

### 7.2 开放问题

无。第 1、2 轮评审提出的问题已全部实测核实并处置。

### 7.3 已标记的假设

- **A1**：`archive/tmp-scripts/get_seat.pre_mode5.py` 与 `archive/legacy/get_seat.py.bak_mode5` 内容相同（15875 字节、SHA256 `9879BE8C`）。按 FR-3.2 保留 `archive/tmp-scripts/` 那份，删除 `.bak`
- **A2**：`automation/cron/` 下 111 个文件（320819 字节）含 4 个任务的历史输出，全部纳入版本控制
- **A3**：`archive/legacy/` 最终 11 个文件 = 9 个 `.bak*` + 2 个 `.db`（详见 FR-1.11 两张表）
- **A4**：`web/` 作为独立 Flask 应用保留在 `web/` 顶层，有独立的 `requirements.txt`
- **A5**：工作区改动登记 —— `config.py` 的 `suspend` 字段与 `SUSPEND` 解析、`user1.yml`/`user2.yml` 的 `SUSPEND: false`、`get_seat.py` 解禁 `build_id != 22` 与外层重试 300→100、`classrooms.py` 新增教室 ID 49，共 5 项，全部保留
- **A6**：`archive/captcha/` 30 与 `src/debug_captcha/` 1150 之间无交叉重复（FR-1.7 已删 2 个）
- **A7**：`extras/opt_scripts/` 与 `extras/opt_src/` 的 6 个 `.bak*` 不收编，随原目录保留
- **A8**：10 个 0 字节文件（`src/` 下 5 个 `__init__.py`、`tests/__init__.py`、`tests/fixtures/config_empty.yaml`、`automation/memory/memories/` 下 2 个 `.lock`、`archive/runtime-logs/loop_stdout.log`）构成 SHA256 相同的重复组，全部保留，不计入 AC-13

## 附录 A：下载分组到重组后目录的映射

| 下载分组（`extracted/` 下） | 实测计数 | 实测字节 | 重组后落位 |
|---|---:|---:|---|
| `MyQFNULibraryBook/MyQFNULibraryBook`（不含 `.git`） | 1352 | 169.0 MB | 仓库根（代码基准），`__pycache__` 删除，`debug_captcha` 去重 |
| `opt_qfnulibrary/opt/qfnulibrary` | 100 | 5072001 | `scripts/loop_seat.sh` 进 `scripts/`（100755）；`logs/` 8 文件进 `archive/runtime-logs/`；7 个 `.bak*` 中 5 个进 `archive/legacy/`；其余与开发版重复，不落位 |
| `opt_qfnulibrary/.../src/debug_captcha` | 32 | 4676911 | `archive/captcha/`（删 2 个交叉重复后 30） |
| `extras/opt_debug_captcha/debug_captcha` | 32 | 4676911 | 同上（与上一行同源，保留一份） |
| `hermes/skills/skills/` | 14 | 80114 | `automation/skills/` |
| `hermes/scripts/scripts/` | 8 | 27365 | `automation/scripts/` |
| `hermes/cron/cron/` | 111 | 320819 | `automation/cron/` |
| `hermes/misc/memories/` | 5 | 8094 | `automation/memory/memories/` |
| `hermes/misc/backups/seatfix-20260913/` | 3 | 24847 | `automation/memory/backups/seatfix-20260913/` |
| `hermes/misc/*.db` | 2 | 151552 | `archive/legacy/` |
| `hermes/history/` | 2 | 19 MB | 仓库外原位保留 |
| `systemd/` | 1 | 364 | `deploy/systemd/` |
| `extras/tmp/` | 9 | 198833 | `archive/tmp-scripts/` |
| `extras/opt_scripts/` + `extras/opt_src/` | 6 | — | 不收编，随原目录保留（A7） |

## 附录 B：4 个图书馆 cron 任务

| ID | 名称 | 表达式 | 调度 | output 体积 |
|---|---|---|---|---:|
| `9fff2a93f04b` | 图书馆签到 | `1 8 * * *` | 每日 08:01 | 192 KB |
| `cd2e73182afa` | 图书馆签退 | `30 21 * * *` | 每日 21:30 | 196 KB |
| `47148cef999d` | 图书馆抢座 | `17 19 * * *` | 每日 19:17 | 40 KB |
| `444005495128` | 图书馆抢座-用户三 | `20 19 * * *` | 每日 19:20 | 28 KB |

## 附录 C：开发版 vs 生产版 差异文件明细

| 文件 | 开发版字节 | 生产版字节 | 差异实质 | 决策 |
|---|---:|---:|---|---|
| `src/get_seat.py` | 16634 | 11699 | mode 5、`get_all_seats()`、限流识别、外层重试上限、`build_id != 22` 解禁 | 取开发版 |
| `src/config/config.py` | 2993 | 2895 | `suspend` 字段 + `SUSPEND` 解析 | 取开发版 |
| `configs/user1.yml` | 1138 | 1043 | `SUSPEND: false`、`DATE: "tomorrow"` | 取开发版 |
| `configs/user2.yml` | 1143 | 1047 | `SUSPEND: false` | 取开发版 |
| `src/classrooms.py` | 2480 | 2401 | 教室 ID 49 | 取开发版（导致 R-9 测试失败，保留） |
| `src/check_in.py` | 2543 | 2660 | 生产版多 117 字节，函数集合相同 | 取开发版 |
| `src/sign_out.py` | 3302 | 3353 | 生产版多 51 字节，函数集合相同 | 取开发版 |
| `scripts/run_all.py` | 9521 | 9788 | 生产版多 267 字节，函数集合相同 | 取开发版 |
| `scripts/loop_seat.sh` | — | 993 | 仅生产版有 | 收编（FR-2.2，mode 100755） |
| `logs/` 8 文件 | — | 318139 | 仅生产版有 | 收进 `archive/runtime-logs/` |