# 评审日志 —— 图书馆抢座系统仓库重组

规格文档 `../SPEC.md` 的三轮评审记录。每轮记录轮次、发现清单、逐条处置与下一轮结论。评审方法由 `document-reviewer` 的六步评审流程承载。

三轮上限为硬约束。第 3 轮为终审，经用户授权（2026-10-11）在修正后直接进入 Step 5 编写 `../PLAN.md`，不再送第 4 轮。

**累计**：第 1 轮 20 条、第 2 轮 15 条（其中 3 条经实测排除）、第 3 轮 10 条，共 45 条发现，其中 3 条为评审误判。

---

## 第 1 轮

| 项 | 内容 |
|---|---|
| 日期 | 2026-10-11 |
| 结论 | CHANGES REQUESTED（Fail） |
| 构成 | 3 Blocking + 5 High + 10 Medium + 4 Low |

评审重点是规格自身的可执行性，以及规格与磁盘实况的一致性。

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

本轮有 4 项需用户裁决，裁决结果见 `../SPEC.md` 的「用户裁决」小节：代码基准取开发版、`.bak` 入库、去重范围取磁盘全量、pytest 先装依赖再定基线。

---

## 第 2 轮

| 项 | 内容 |
|---|---|
| 日期 | 2026-10-11 |
| 结论 | CHANGES REQUESTED |
| 构成 | 3 Blocking + 6 High + 6 Medium/Low |

评审在临时目录中模拟 `git check-ignore` 与 PowerShell 扫描。我对其数字主张逐项实测复核，其中 **3 条为评审误判**，其余 12 条已修正。

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

---

## 第 3 轮（终审）

| 项 | 内容 |
|---|---|
| 日期 | 2026-10-11 |
| 结论 | CHANGES REQUESTED |
| 构成 | 5 Blocking + 5 Medium/Low |

三轮硬上限下的终审。该轮**独立复现并确认**了：

- `.gitignore` 5 条反选对 17 个目标路径 17/17 入库
- 装 `pycryptodome 3.24.0` 后 `pytest --collect-only -q` 退出码 0 且 **148 tests collected 0 error**
- AC-19 / AC-29 通过
- `git update-index --chmod=+x` 在 Windows 实测成功
- NFR-2.1 十项计数（除 `debug_captcha` 外）全对

我对其 5 条阻塞项逐项实测后全部确认成立，已全部修正：

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

---

## 遗留与已知权衡

三条轮上限内的终审未修复项，均已在规格中登记为已知权衡而非缺陷：

| 编号 | 内容 | 处置 |
|---|---|---|
| R-14 | `.gitattributes` 的 `* text=auto eol=lf` 在本机 `core.autocrlf=true` 下对现有文件零影响，仅对未来文件生效 | 接受。跨平台协作的收益高于当前零影响的事实 |
| 保留项 | `configs/user{1,2,3}.yml`、`data/seat_info/`、`automation/memory/MEMORY.md`、运行日志中的真实姓名学号与密码 | **未脱敏**，按用户要求保留原样；仓库在 GitHub 上保持 PRIVATE，本轮零推送 |
| 3 条误判 | F-4、F-7 部分、F-1 的 `.git` 部分 | 已实测排除并记录证据。保留记录是为了避免后续实施阶段重蹈同一误判 |