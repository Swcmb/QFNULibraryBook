# PLAN: 图书馆抢座系统仓库重组

## 前置条件

- **SPEC.md 已就位**，含第 1–3 轮评审的完整处置台账（累计 45 条发现，其中 3 条经实测判定为评审误判）。
- **评审循环状态**：三轮硬上限已用尽，第 3 轮修订完成后**用户于 2026-10-11 显式授权进入 Step 5**（消息记录：授权「第 4 轮修正后进入 Step 5」）。当前规格的开放发现数为 **0**，无需登记「已接受但未修复」的发现 id。
- **仓库根**：`E:\Files\Documents\deepseek-harness\default-workspace\qfnulibrary-download\extracted\MyQFNULibraryBook\MyQFNULibraryBook`
- **执行环境**：Windows + PowerShell 5.1，Python 3.13.9，pytest 8.4.2，git 2.51.0.windows.1，`core.autocrlf=true`，当前分支 `main`，HEAD `ad613ea`。
- **零推送约束**：本轮全部 git 操作限于本地，`git push` 一次都不可执行。

## 里程碑

| 里程碑 | 状态定义 | 涉及任务 |
|---|---|---|
| **M1 环境与回滚基线就绪** | 依赖装齐、pytest 可收集、不可逆操作前的完整快照已落盘、6 个未提交改动已固化为提交 | T-1、T-2、T-3 |
| **M2 分层落位完成** | `automation/`、`deploy/`、`archive/` 四个子目录全部按 FR-1.1~1.8、FR-1.11 就位，文件数与字节数符合 NFR-2.1 | T-4、T-5、T-6、T-7 |
| **M3 清理与去重完成** | `__pycache__` 清零、`src/` 下 8 个 `.bak` 删除、验证码去重至 1150、`> 1024` 字节文件零重复 | T-9、T-10、T-11、T-12 |
| **M4 版本控制与文档闭环** | `.gitignore` 反选与 `.gitattributes` 生效、三份文档写就、可执行位设置、`<合并提交>` 落地、35 条 AC 全量验收通过 | T-8、T-13、T-14、T-15、T-16、T-17 |

---

## 任务

### T-1 安装缺失依赖并采集 pytest 基线

- **交付物**：本机 Python 环境装齐 `pycryptodome`；`pytest --collect-only -q` 可零错误完成收集。依赖安装本身不属于交付物，其目的是让 AC-20 可验证。
- **依赖**：无
- **映射**：NFR-0.4、NFR-3.4、AC-20
- **步骤**：
  1. `pip install pycryptodome`
  2. 在仓库根执行 `pytest --collect-only -q`
- **验证**：
  ```powershell
  pytest --collect-only -q | Select-String 'error'
  # 通过条件：无任何 error 行；且 $LASTEXITCODE -eq 0
  ```
  实测参考值：装 `pycryptodome 3.24.0` 后收集 **148 tests collected 0 error**。收集项数作为证据写入验收报告（NFR-3.4），不作为硬判据。

### T-2 导出重组前置快照

- **交付物**：`qfnulibrary-download/pre-reorg-manifest.csv`（仓库外，不入库），含 `extracted/` 下五组目录全部文件的相对路径、字节数、SHA256。
- **依赖**：无
- **映射**：FR-3.6、NFR-8.4、R-13、AC-32
- **验证**：
  ```powershell
  Test-Path qfnulibrary-download\pre-reorg-manifest.csv
  ```
  通过条件：True；且 CSV 行数（不含表头）等于扫描到的文件总数。
  ```powershell
  Import-Csv qfnulibrary-download\pre-reorg-manifest.csv | Measure-Object
  ```
  参考量级：五组目录合计约 1700 行（`MyQFNULibraryBook` 1397 + `opt_qfnulibrary` 100 + `hermes` 145 + `systemd` 1 + `extras` 47，去重目录）。

### T-3 提交工作区改动形成回退点

- **交付物**：`<保存提交>`，父提交为 `ad613ea`，恰好含 6 个对象变更：`configs/user1.yml`、`configs/user2.yml`、`configs/user3.yml`、`src/classrooms.py`、`src/config/config.py`、`src/get_seat.py`。提交信息中文，遵循仓库既有风格（参照 `ad613ea`）。
- **依赖**：T-1
- **映射**：FR-2.3、FR-2.4、NFR-1.1、NFR-1.2、NFR-1.3、NFR-1.4、AC-1、AC-2、AC-3、AC-28、AC-29、R-1
- **验证**：
  ```powershell
  git show HEAD --stat | Select-String 'changed'
  ```
  通过条件：`changed` 计数为 6；且下列内容断言全部成立：
  ```powershell
  git grep -cE 'def get_all_seats' HEAD -- src/get_seat.py          # 1
  git grep -cE 'retries < 100' HEAD -- src/get_seat.py            # 1
  git grep -cE 'config\.mode == .5.' -- src/get_seat.py           # 1
  git grep -c suspend -- src/config/config.py                      # >= 2
  ```
  辅证（字节判据）：`git cat-file -s (git rev-parse HEAD:src/get_seat.py)` = **16634**。已实测 `core.autocrlf=true` 对 LF 文件不做改写，blob 字节等于磁盘字节。

### T-4 落位 `automation/` 四个子目录

- **交付物**：
  - `automation/skills/` ← `extracted/hermes/skills/skills/` 全量，**14** 文件 / 80114 字节，三级层级（`behavioral/`、`productivity/`、`task-execution-decision/`）原样保留
  - `automation/scripts/` ← `extracted/hermes/scripts/scripts/` 下 8 个文件，原文件名不变（`book-seat.sh`、3 个 `.bak_*`、`book-seat-userC.sh`、`book-seat-zonghe.py`、`book-seat-zonghe.sh`、`seat-notify.py`）
  - `automation/cron/` ← `extracted/hermes/cron/cron/jobs.json` 与 `output/<id>/`，**111** 文件 / 320819 字节
  - `automation/memory/` ← `extracted/hermes/misc/` 下 8 个文件（`memories/` 5 个 + `backups/seatfix-20260913/` 3 个），**32941** 字节
- **依赖**：T-3
- **映射**：FR-1.1、FR-1.2、FR-1.3、FR-1.4、NFR-2.1、NFR-5.5、AC-4、AC-6、AC-7
- **注意**：源路径存在一层额外嵌套（`hermes/skills/skills/`、`hermes/scripts/scripts/`、`hermes/cron/cron/`），复制时须指向内层。
- **验证**：
  ```powershell
  Get-ChildItem automation\skills -Recurse -File | Measure-Object -Property Length -Sum
  # Count=14, Sum=80114
  Get-ChildItem automation\cron -Recurse -File | Measure-Object -Property Length -Sum
  # Count=111, Sum=320819
  Get-ChildItem automation\memory -Recurse -File | Measure-Object | Select-Object -ExpandProperty Count
  # 8
  Get-ChildItem automation\scripts -File | Measure-Object | Select-Object -ExpandProperty Count
  # 8
  ```
  四项全部相符方为通过。`automation/memory/` 与 `automation/scripts/` 的 `.bak` 此时仍被 `.gitignore` 通配忽略，入库状态留给 T-13 与 T-16 验证。

### T-5 落位 `deploy/systemd/`

- **交付物**：`deploy/systemd/qfnu-library.service`，**364** 字节，内容为生产版单元原样（`WorkingDirectory=/opt/qfnulibrary`、`ExecStart=/opt/qfnulibrary/scripts/loop_seat.sh`、`Restart=always`）。
- **依赖**：T-3
- **映射**：FR-1.5、NFR-2.1、AC-8
- **验证**：
  ```powershell
  Test-Path deploy\systemd\qfnu-library.service
  (Get-Item deploy\systemd\qfnu-library.service).Length   # 364
  ```

### T-6 落位 `archive/` 四个子目录

- **交付物**：
  - `archive/tmp-scripts/` ← `extracted/extras/tmp/` 下 9 个文件，**198833** 字节
  - `archive/captcha/` ← `extracted/extras/opt_debug_captcha/debug_captcha/` 下 32 个文件（16 bg + 16 slider），**删除其中与 `src/debug_captcha/` 交叉重复的 2 个**：`bg_1789125485.png`、`slider_1789125485.png`，落位后 **30** 个文件
  - `archive/runtime-logs/` ← `extracted/opt_qfnulibrary/opt/qfnulibrary/logs/` 下 8 个运行日志，**318139** 字节
  - `archive/legacy/` ← 9 个 `.bak*`（4 个来自 `book/src/`：`_20260912_195204`、`_20260914_192712`、`_bak_directpost`、`_bak_nosleep_20260912_195441`；5 个来自 `opt/`：`user1.yml.bak_20260911_191239`、`loop_seat.sh.bak_20260911_192300`、`run_all.py.bak_20260911_190528`、`get_seat.py.bak_20260911_190528`、`sign_out.py.bak_20260911_190528`）+ 2 个 `.db`（`kanban.db` 118784、`verification_evidence.db` 32768），合计 **11** 个文件 / 227239 字节
- **依赖**：T-3
- **映射**：FR-1.6、FR-1.7、FR-1.8、FR-1.11、NFR-2.1、AC-9、AC-10、AC-11
- **注意**：`extracted/opt_qfnulibrary/`、`extracted/extras/` 本身保留不删（FR-1.10 复制式归并），本任务的删除只作用于仓库内 `archive/captcha/` 那 2 张交叉重复。
- **验证**：
  ```powershell
  Get-ChildItem archive\tmp-scripts -File | Measure-Object -Property Length -Sum     # 9 / 198833
  Get-ChildItem archive\captcha -File | Measure-Object | Select-Object -ExpandProperty Count   # 30
  Get-ChildItem archive\runtime-logs -File | Measure-Object -Property Length -Sum # 8 / 318139
  Get-ChildItem archive\legacy -File | Measure-Object -Property Length -Sum        # 11 / 227239
  Test-Path archive\captcha\bg_1789125485.png                                      # False
  Test-Path archive\captcha\slider_1789125485.png                                   # False
  ```
  另需确认 8 个运行日志 SHA256 两两不同（已实测：5639AD38、354E5852、020CA7DB、05808AB5、E3B0C442、A0FDBBB8、032D7749、4B85E048）。

### T-7 收编生产版独有的 `scripts/loop_seat.sh`

- **交付物**：`scripts/loop_seat.sh`（993 字节）落入仓库。这是 systemd 单元的 `ExecStart` 目标，当前仓库缺失。
- **依赖**：T-3
- **映射**：FR-2.2、AC-22（前置）
- **验证**：
  ```powershell
  Test-Path scripts\loop_seat.sh
  (Get-Item scripts\loop_seat.sh).Length   # 993
  ```
  补充：`Get-Content scripts\loop_seat.sh | Select-String "`r`n"` 应零匹配（保持 LF）。

### T-8 写入 `.gitignore` 反选规则与 `.gitattributes`

- **交付物**：
  - `.gitignore` 末尾追加 5 条反选规则（须位于既有 `*.bak` / `*.bak_*` / `*.bak.*` 之后）+ 2 行记录不入库意图的注释：
    ```
    !archive/legacy/**
    !archive/legacy/*.bak*
    !automation/scripts/*.bak_*
    !automation/skills/**/*.bak_*
    !automation/memory/**/*.bak*
    ```
  - 新建 `.gitattributes`：`* text=auto eol=lf` + `*.png binary` + `*.jpg binary` + `*.gz binary`
- **依赖**：T-4、T-6、T-7（规则覆盖的目标路径须已存在）
- **映射**：FR-4.7、FR-4.8、NFR-5.1、NFR-5.2、AC-22、AC-23、AC-34、G-7、R-11
- **注意**：`git check-attr` **退出码恒为 0**，属性未定义时输出 `unspecified`，判定必须解析输出文本而非退出码。
- **验证**：
  ```powershell
  Get-Content .gitattributes          # 含 * text=auto eol=lf 与 3 条 binary
  git check-attr text eol -- scripts/loop_seat.sh    # 输出含 eol: lf
  git check-ignore -v archive/legacy/get_seat.py.bak_directpost   # 应无输出且退出码 1
  git check-ignore -v automation/scripts/book-seat.sh.bak_notify  # 应无输出且退出码 1
  ```
  后两条证明反选规则压过了通配忽略。

### T-9 删除 `__pycache__` 目录与 `.pyc`

- **交付物**：仓库内 7 个 `__pycache__/` 目录及 **61** 个 `.pyc` 全部清除。
- **依赖**：T-3
- **映射**：FR-3.1、AC-14
- **验证**：
  ```powershell
  (Get-ChildItem -Recurse -Directory -Filter __pycache__ | Measure-Object).Count   # 0
  (Get-ChildItem -Recurse -File -Filter *.pyc | Measure-Object).Count            # 0
  ```

### T-10 删除 `src/` 下 8 个 `.bak*` 原位副本

- **交付物**：`src/` 目录下 8 个 `.bak*` 全部删除。其中 4 个在 `archive/legacy/` 已有同 SHA256 副本；另 4 个（`get_seat.py.bak_mode5`、`bak_fallbackfix`、`bak_sleep_20260912_195350`、`src/auth/token.py.bak_20260914_193704`）与活文件或 `automation/memory/backups/` 下的备份同内容。
- **依赖**：T-4（`automation/memory/backups/` 须先就位）、T-6（`archive/legacy/` 与 `archive/tmp-scripts/` 须先就位）
- **映射**：FR-1.11 第七组、FR-3.2 规则 2 与规则 4、R-6
- **注意**：这是**删除**而非不收编 —— 这些文件位于仓库内。`extracted/` 侧的 6 个 `opt/`、`extras/` `.bak` 按 FR-1.10 保留原位不删，本任务不涉及。
- **验证**：
  ```powershell
  (Get-ChildItem src -Recurse -File -Filter '*.bak*' | Measure-Object).Count   # 0
  ```
  附证：`archive/legacy/` 下 `get_seat.py.bak_directpost` 的 SHA256 仍为 `D7658744`、`get_seat.py.bak_20260912_195204` 仍为 `4B11C151`（存档副本未被误删）。

### T-11 `src/debug_captcha/` 全局去重

- **交付物**：`src/debug_captcha/` 由 1184 个文件去重至 **1150** 个，删除 **34** 个冗余副本（32 组重复，32 组各含 2 份）。目录保留在磁盘上，不纳入版本控制。
- **依赖**：T-6（`archive/captcha/` 的 2 张交叉重复须已由本任务的前置 T-6 删除）
- **映射**：FR-3.3、FR-3.5、NFR-4.1、R-10、AC-12、AC-21
- **验证**：
  ```powershell
  (Get-ChildItem src\debug_captcha -File | Measure-Object).Count   # 1150
  (git ls-files src/debug_captcha/ | Measure-Object).Count        # 0
  ```
  另需复算：去重后该目录内全部文件 SHA256 唯一（重复组数 = 0）。

### T-12 `> 1024` 字节文件全局零重复验收

- **交付物**：仓库根下（排除 `.git/`）长度 > 1024 字节的文件按 SHA256 分组后重复组数为 **0**。
- **依赖**：T-9、T-10、T-11
- **映射**：FR-3.2、G-3、AC-13
- **验证**（AC-13 可复现命令，通过条件为无任何输出）：
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
- **注意**：10 个 0 字节文件（`src/` 下 5 个 `__init__.py`、`tests/__init__.py`、`tests/fixtures/config_empty.yaml`、`automation/memory/memories/` 下 2 个 `.lock`、`archive/runtime-logs/loop_stdout.log`）被阈值排除，属功能性文件，一律保留。
- **文件总数口径参考**：删除动作执行后（不含 `debug_captcha`）为 **305** 个；含 `debug_captcha` 1150 个为 1455 个。

### T-13 编写 `docs/ORGANIZATION.md`

- **交付物**：`docs/ORGANIZATION.md`，覆盖五层职责定义（程序本体 / `automation` 调度 / `deploy` 部署 / `archive` 存档 / `docs` 说明）、每层内容来自哪个下载分组、去重与代码基准的取舍规则（含「开发版是生产版严格超集」这一结论的依据）、哪些内容被 gitignore 及原因、从 `pre-reorg-manifest.csv` 与 `archives/` 重新获取原始数据的方法。
- **依赖**：T-4、T-5、T-6、T-7
- **映射**：FR-1.9、G-5、NFR-7.1、AC-15
- **验证**：
  ```powershell
  $c = Get-Content docs\ORGANIZATION.md -Raw
  '职责','来源','去重','代码基准','gitignore' | ForEach-Object { if ($c -notmatch $_) { "MISSING: $_" } }
  ```
  通过条件：无 `MISSING:` 输出。

### T-14 编写 `archive/legacy/README.md`

- **交付物**：`archive/legacy/README.md`，逐条列出每一份被删除副本的原路径、字节数、与哪份文件内容相同，涵盖 FR-1.11 的全部删除记录（表格前 6 条 + 第七组 4 个 `src/` 原位副本，共 10 条）与 `extras/opt_*` 的 6 个不收编文件。
- **依赖**：T-6、T-10、T-11
- **映射**：FR-3.4、NFR-7.2、AC-33、R-6、R-10
- **验证**：人工逐条比对（该 AC 在 SPEC 中即标注为人工检查项）。至少须能查到 `src/get_seat.py.bak_mode5`、`src/get_seat.py.bak_fallbackfix`、`src/auth/token.py.bak_20260914_193704`、`src/get_seat.py.bak_20260912_195204` 与 `extras/opt_scripts/run_all.py.bak_20260911_081029` 五条记录。

### T-15 编写 `docs/REVIEW_LOG.md`

- **交付物**：`docs/REVIEW_LOG.md`，含三轮评审日志：每轮编号、发现清单、对应修正、下一轮结论；记录 `use_agent document-reviewer` 失败的原因（agent 文件 `C:\Users\Swcmb\.dsh\agents\document-reviewer.md` L146-153 含 `{{short-kebab-case-slug}}` 模板占位符，运行时 `malformed prompt variable reference`）与改用 `subagent` 承载同一评审方法的事实；记录 3 条评审误判的实测排除证据；记录用户授权第 4 轮修订后直接进入 Step 5 的决定。
- **依赖**：无
- **映射**：NFR-7（可维护性）、Step 4 流程留痕
- **验证**：`Test-Path docs\REVIEW_LOG.md` 为 True，且 `Get-Content docs\REVIEW_LOG.md -Raw` 含「第 1 轮」「第 2 轮」「第 3 轮」「误判」四个关键词。

### T-16 暂存、设置可执行位、提交 `<合并提交>`

- **交付物**：`<合并提交>`，父提交为 `<保存提交>`，含全部重组内容 + 5 份文档 + `.gitattributes` + `.gitignore` 追加。4 个 `.sh`（`scripts/loop_seat.sh`、`automation/scripts/` 下 `book-seat.sh`、`book-seat-userC.sh`、`book-seat-zonghe.sh`）mode 为 `100755`。
- **依赖**：T-3、T-4、T-5、T-6、T-7、T-8、T-9、T-10、T-11、T-13、T-14、T-15
- **映射**：FR-3.7、FR-4.1~FR-4.6、NFR-1.1、NFR-5.4、NFR-5.6、AC-1、AC-5、AC-23、AC-24
- **步骤**：
  1. `git add -A`
  2. `git update-index --chmod=+x scripts/loop_seat.sh automation/scripts/book-seat.sh automation/scripts/book-seat-userC.sh automation/scripts/book-seat-zonghe.sh`
  3. `git commit`（中文提交信息）
- **验证**：
  ```powershell
  git ls-files -s automation/scripts/ | Select-String '100755'   # 3 行
  git ls-files -s scripts/loop_seat.sh                          # mode 100755
  git log --oneline -3      # 顶部 <合并提交>，其次 <保存提交>，再次 ad613ea
  ```
  注：仓库 92 个既有已跟踪文件全为 `100644`，本次仅上述 4 个变为 `100755`。Windows 上 `git update-index --chmod=+x` 已实测可用。

### T-17 全量验收

- **交付物**：验收报告，逐条记录 AC-1~AC-35 的实测结果与通过/失败判定。
- **依赖**：T-16
- **映射**：AC-1~AC-35 全部
- **验证**：按下列分组逐项执行，任一失败即回到对应任务修复后重跑：

  | 组 | 覆盖 AC | 关键命令 |
  |---|---|---|
  | 提交结构 | AC-1、AC-2、AC-3 | `git log --oneline -3`、`git show <保存提交> --stat` |
  | 目录计数 | AC-4、AC-6~AC-12 | `Get-ChildItem <dir> -Recurse -File \| Measure-Object` |
  | 去重 | AC-13 | T-12 的可复现脚本，输出须为空 |
  | 清理 | AC-14 | `Get-ChildItem -Recurse -Directory -Filter __pycache__ \| Measure-Object` = 0 |
  | 内容不变 | AC-16~AC-19 | 对 8 个对象逐一 `Get-FileHash -Algorithm SHA256` 与重组前记录比对；`git grep -nE '^\s*import (src\|web)\.'` 须零匹配（退出码 1） |
  | 代码基准 | AC-28、AC-29 | `git grep -cE 'config\.mode == .5.' -- src/get_seat.py` = 1；`git grep -c suspend -- src/config/config.py` ≥ 2 |
  | 版本控制 | AC-21、AC-23、AC-24、AC-34 | `git ls-files <dir> \| Measure-Object`；`git status --porcelain` 为空 |
  | 兼容性 | AC-22 | `git check-attr text eol -- scripts/loop_seat.sh` 输出含 `eol: lf`；6 个 `.sh` 磁盘行尾无 CRLF |
  | 测试 | AC-20 | `pytest --collect-only -q`，退出码 0 且无 error 行 |
  | 边界 | AC-25、AC-26、AC-27、AC-32 | `Test-Path` 确认 `extracted/` 五组原始目录、`archives/` 内容、两个 history 文件、前置快照均在原位 |
  | 隐私与零推送 | AC-30、AC-31 | `gh repo view Swcmb/MyQFNULibraryBook --json visibility` 仍为 PRIVATE；本轮 git 命令历史中无 `git push` |
  | 非阻塞 | AC-35 | 有 SSH 凭据时执行远端文件数对比；无凭据时在报告中显式记为「未执行」 |

- **已知不纳入本轮修复的项**：`tests/test_classrooms.py` 的 2 项失败（L12 断言 22 个教室、L17 断言 18 个唯一 ID，实际为 23/19，因新增教室 ID 49）。采用开发版基准后该失败保留，属 SPEC R-9 已接受项。修复属代码变更，超出本轮非目标范围。

---

## 需求覆盖矩阵

### 功能需求 FR 覆盖

| FR | 覆盖任务 |
|---|---|
| FR-1.1 `automation/skills/` | T-4 |
| FR-1.2 `automation/scripts/` | T-4 |
| FR-1.3 `automation/cron/` | T-4 |
| FR-1.4 `automation/memory/` | T-4 |
| FR-1.5 `deploy/systemd/` | T-5 |
| FR-1.6 `archive/tmp-scripts/` | T-6 |
| FR-1.7 `archive/captcha/` | T-6 |
| FR-1.8 `archive/runtime-logs/` | T-6 |
| FR-1.9 `docs/ORGANIZATION.md` | T-13 |
| FR-1.10 复制式归并、原始目录保留 | T-6（约束）、T-17（AC-26、AC-27 验证） |
| FR-1.11 `archive/legacy/` 收编与处置表 | T-6、T-10、T-14 |
| FR-2.1 保持开发版现状 | T-3、T-17（AC-28、AC-29） |
| FR-2.2 收编 `loop_seat.sh` | T-7 |
| FR-2.3 保留 5 个已修改 + 1 个未跟踪 | T-3 |
| FR-2.5 生产版仅作参考 | T-6 |
| FR-3.1 删除 `__pycache__` | T-9 |
| FR-3.2 全局去重判据 | T-10、T-12 |
| FR-3.3 `debug_captcha` 去重至 1150 | T-11 |
| FR-3.4 `archive/legacy/README.md` | T-14 |
| FR-3.5 验证码不入库 | T-11 |
| FR-3.6 前置快照 | T-2 |
| FR-3.7 可执行位 | T-16 |
| FR-4.1~FR-4.3 保留历史与远端配置 | T-16 |
| FR-4.4 `git status` 干净 | T-16、T-17 |
| FR-4.5 不 push | T-16、T-17 |
| FR-4.6 提交结构 | T-3、T-16 |
| FR-4.7 `.gitattributes` | T-8 |
| FR-4.8 `.gitignore` 反选 | T-8 |
| FR-4.9 运行日志入库 | T-6、T-16 |
| FR-5.1 history 不入库 | T-17（AC-25） |
| FR-5.2 `archives/` 不入库 | T-17（AC-26） |
| FR-5.3 清单文件不入库 | T-2、T-17（AC-32） |

### 验收标准 AC 覆盖

| AC | 验证任务 |
|---|---|
| AC-1、AC-2、AC-3 | T-3（保存提交结构）、T-17（最终结构） |
| AC-4、AC-6、AC-7 | T-4 |
| AC-5 | T-16 |
| AC-8 | T-5 |
| AC-9、AC-10、AC-11 | T-6 |
| AC-12 | T-11 |
| AC-13 | T-12 |
| AC-14 | T-9 |
| AC-15 | T-13 |
| AC-16、AC-17、AC-18、AC-19 | T-17 |
| AC-20 | T-1 |
| AC-21 | T-11、T-17 |
| AC-22 | T-8（前置由 T-7 满足）、T-17 |
| AC-23 | T-8、T-16、T-17 |
| AC-24 | T-16、T-17 |
| AC-25、AC-26、AC-27 | T-17 |
| AC-28、AC-29 | T-3、T-17 |
| AC-30、AC-31 | T-17 |
| AC-32 | T-2、T-17 |
| AC-33 | T-14 |
| AC-34 | T-8 |
| AC-35 | T-17（非阻塞） |

---

## 明确不做的事

| 项 | 原因 |
|---|---|
| `git push`、创建 PR、创建新 GitHub 仓库 | SPEC 非目标；用户明确「零推送」。AC-31 专门验证这一点 |
| 修改服务器 47.104.159.142 上的任何文件或服务 | SPEC 非目标；SSH 仅用于 AC-35 的只读对比（无凭据时跳过并记为「未执行」） |
| 任何代码功能变更、依赖升级、测试重写、格式化 | SPEC 非目标。本轮只做位置归并、去重删除、新增文档与 `.gitattributes`、mode 位设置 |
| 修复 `tests/test_classrooms.py` 的 2 项失败 | 属代码变更，SPEC R-9 已接受；在验收报告中显式记录状态 |
| 脱敏 `configs/user*.yml`、`data/seat_info/`、`automation/memory/MEMORY.md` | SPEC NFR-6 与非目标明确要求保留原样 |
| 将 `src/debug_captcha/` 纳入版本控制 | FR-3.5；AC-21 专门验证其为 0 |
| 删除 `extracted/` 五组原始目录或 `archives/` 内容 | FR-1.10 复制式归并；NFR-8.2 回滚依赖它们 |
| 引入 CI/CD、lint 配置、pre-commit 钩子 | SPEC 非目标；仓库 `.git/hooks/` 保持仅含 `*.sample` |

## 进度日志

| 任务 | 完成时间 | 结果 | 验证摘要 |
|---|---|---|---|
| T-1 | 2026-10-11 | 通过 | `pip install pycryptodome` → 3.24.0；`pytest --collect-only -q` → **148 tests collected**，退出码 0，无 error 行（AC-20 达标） |
| T-2 | 2026-10-11 | 通过 | `pre-reorg-manifest.csv` 落盘 **1691 行**（opt 100 / book 1398 / hermes 145 / systemd 1 / extras 47），283301 字节，含 114 组重复哈希。仓库外不入库（AC-32 达标） |
| T-3 | 2026-10-11 | 通过 | `<保存提交>` = **`04a3a2e`**（父 `ad613ea`），6 files changed。内容断言全中：`get_all_seats`=1、`retries < 100`=1、`config.mode == .5.`=1、`suspend`=2、blob 字节 **16634**（AC-2/AC-3/AC-28/AC-29 达标）。首次提交因 `Out-File -Encoding utf8` 写入 BOM 导致标题前出现 `﻿`，已用 `UTF8Encoding($false)` 重写并 `--amend` 修正 |
| T-4 | 2026-10-11 | 通过 | `automation/skills` 14/80114、`automation/scripts` 8/27365、`automation/cron` 111/320819、`automation/memory` 8/32941，四项全中 NFR-2.1。首次 `Copy-Item ... -Recurse` 把 `scripts` 目录整体复制成一个同名文件（count=1），已改为逐文件复制修正（AC-4/AC-6/AC-7 达标） |
| T-5 | 2026-10-11 | 通过 | `deploy/systemd/qfnu-library.service` = 364 字节（AC-8 达标） |
| T-6 | 2026-10-11 | 通过 | `archive/tmp-scripts` 9/198833、`archive/captcha` 32→**30**（删 `bg_1789125485.png`、`slider_1789125485.png`）/4352235、`archive/runtime-logs` 8/318139 且 8 个 SHA256 两两不同、`archive/legacy` 11/227239（AC-9/AC-10/AC-11 达标） |
| T-7 | 2026-10-11 | 通过 | `scripts/loop_seat.sh` = 993 字节，CRLF 匹配 0 |
| T-8 | 2026-10-11 | 通过 | `.gitignore` 追加 5 条反选 + 2 行意图注释；`.gitattributes` 写入。`git check-ignore -v` 对 4 个反选目标命中反选规则（`!archive/legacy/*.bak*`、`!automation/scripts/*.bak_*`、`!automation/memory/**/*.bak*`），对 `src/get_seat.py.bak_mode5` 仍命中 `*.bak_*` 通配 —— 符合预期，该文件由 T-10 删除。`git check-attr text eol -- scripts/loop_seat.sh` → `text: auto` / `eol: lf`（AC-34、AC-22 前置达标） |
| T-9 | 2026-10-11 | 通过 | `__pycache__` 7 个目录 + 61 个 `.pyc` 全部清除，复查均为 0（AC-14 达标） |
| T-10 | 2026-10-11 | 通过 | `src/` 下 8 个 `.bak*` 全部删除，复查为 0；`archive/legacy/` 11 个存档副本齐全 |
| T-11 | 2026-10-11 | 通过 | `src/debug_captcha` 1184 → **1150**，删除 34 个冗余副本。**Step 6 实测发现规格数字有误**：三轮评审给出的唯一文件数（1152 / 1150 / 1118）均不正确；实测组规模分布为 32 组各含 2 份、无 3 份组，冗余数 = 1184 − 1150 = 34。已全篇订正 SPEC.md 与 PLAN.md（1152→1150、66→34、1423→1455）。复查该目录 1150 文件 SHA256 全部唯一（AC-12 达标） |
| T-12 | 2026-10-11 | 通过 | AC-13 可复现脚本输出 `AC13_DUP_GROUPS=0`，无任何重复组行（AC-13 达标）。实测落位后共 **1452** 个文件（含 `src/debug_captcha` 1150 个与 gitignored 的 `.pytest_cache` 5 个）；不含 `debug_captcha` 为 302，其中 `.pytest_cache` 占 5，有效落位数 297。0 字节文件实测 **10** 个，与 A8 枚举逐条吻合 |
