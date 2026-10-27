# 敏感数据排除说明

生成日期：2026-10-11　　适用提交：`ab372d6` 之后

## 为什么要排除

系统在曲阜师范大学图书馆的实际运行数据中含三名学生的**真实姓名、真实学号与明文密码**。这些数据仅保存在开发者本机的完整副本里，不进入 Git 版本控制，因此不会随仓库分发。

## 判断口径

单个文件只要命中下面任一模式，整个文件即排除：

- 真实中文姓名 —— 三名学生各一个，本文一律写作 `<姓名A>` / `<姓名B>` / `<姓名C>`
- 学号 —— `20234` 开头的 9 位数字
- 明文密码 —— 三处账号密码，本文一律写作 `<密码A>` / `<密码B>` / `<密码C>`

判定命令（在仓库根执行）：

```powershell
git grep -lIE '<姓名A>|<姓名B>|<姓名C>|20234[0-9]{5}|<密码A>|<密码B>|<密码C>'
```

把上面命令里的占位符替换成实际字符串后使用。判定对象取「Git 已跟踪文件全集」，不用目录遍历，保证判定结果与实际分发内容一致。

## 排除方式

在 `.gitignore` 的「敏感数据」段落写入文件级或目录级规则，再用 `git rm --cached` 把已跟踪对象移出版本控制。文件在磁盘上保留。

复核边界用这条命令，它列出「已跟踪且命中忽略规则」的对象：

```powershell
git ls-files -ci --exclude-standard
```

## 排除规则一览

| `.gitignore` 规则 | 说明 |
|---|---|
| `configs/user1.yml` `user2.yml` `user3.yml` | 三个账号配置，各含一处明文密码 |
| `configs/users.yml` | 账号汇总表，`name` 字段内嵌学号 |
| `archive/legacy/user1.yml.bak_*` | 旧账号配置备份，含明文密码 |
| `archive/runtime-logs/` | 8 个生产运行日志，正文含学号与姓名 |
| `archive/tmp-scripts/` | 9 个 `/tmp` 临时脚本与抢座日志，含学号文件名与脚本注释 |
| `automation/scripts/` | 8 个 Hermes 抢座脚本，注释内嵌姓名学号 |
| `automation/cron/` | `jobs.json` 与 99 个任务历史输出 |
| `automation/memory/memories/` `automation/memory/backups/` | 记忆体与抢座修复前的备份 |
| `automation/skills/behavioral/listening-protocol/` | 技能文档举例使用真实学号 |
| `automation/skills/productivity/library-seat-booking/` | 技能主体与 7 份 references，含姓名学号与一处明文密码 |
| `automation/skills/task-execution-decision/references/` | 参考文档含真实学号 |

规则顺序说明：`.gitignore` 后写的规则覆盖先写的。`.bak` 反选规则（`!archive/legacy/**` 等）写在前面，敏感数据规则写在后面，因此 `archive/legacy/user1.yml.bak_*` 最终按敏感规则排除。

## 排除规模

| 类别 | 文件数 |
|---|---:|
| `archive` | 18 |
| `automation` | 140 |
| `configs` | 4 |
| **合计** | **162** |

按敏感串逐文件命中的是 **145** 个；目录级规则连带排除另外 **17** 个不含敏感串、但处在敏感目录内的文件。重组后仓库原有 300 个已跟踪文件，扣除排除项后推送 **138** 个。

## 连带排除清单

以下 17 个文件自身不含敏感串，因所在目录被整目录排除而一并排除：

| 文件 | 连带原因 |
|---|---|
| `archive/runtime-logs/library_seat.log` | 同目录 7 个日志含姓名学号 |
| `archive/runtime-logs/loop_stdout.log` | 同上 |
| `archive/tmp-scripts/check_seat.py` | 同目录日志文件名含学号 |
| `archive/tmp-scripts/get_seat.pre_mode5.py` | 同上 |
| `archive/tmp-scripts/patch_seat.py` | 同上 |
| `archive/tmp-scripts/probe_seats.py` | 同上 |
| `archive/tmp-scripts/seats2.py` | 同上 |
| `automation/cron/output/47148cef999d/2026-10-09_19-18-31.md` | 同目录 5 个输出含姓名学号 |
| `automation/cron/output/47148cef999d/2026-10-10_19-18-30.md` | 同上 |
| `automation/memory/backups/seatfix-20260913/get_seat.py` | 同目录 `book-seat.sh` 含姓名学号 |
| `automation/memory/backups/seatfix-20260913/jobs.json.bak` | 同上 |
| `automation/memory/memories/MEMORY.md.lock` | 同目录 `MEMORY.md` 含姓名学号 |
| `automation/memory/memories/USER.md.lock` | 同上 |
| `automation/memory/memories/user_profile.md` | 同上 |
| `automation/skills/productivity/library-seat-booking/references/cancel-api.md` | 同目录 references 含姓名学号与明文密码 |
| `automation/skills/productivity/library-seat-booking/references/cancel-reservation.md` | 同上 |
| `automation/skills/task-execution-decision/references/project-scripts-before-wrapper.md` | 同目录含真实学号 |

`web/static/logo.png` 虽然命中 `.gitignore` 里既有的 `web/static/logo.png` 规则，但它在 2026-09-14 的历史推送中已进入版本控制，属于已跟踪对象，内容不含敏感信息，保持入库。

## 项目文档的脱敏

`SPEC.md` 与 `docs/ORGANIZATION.md` 作为项目文档保留入库，其中的真实姓名学号已替换为占位符：

| 文件 | 位置 | 原内容 | 替换后 |
|---|---|---|---|
| `SPEC.md` | FR-1.6 | 三个含真实学号的 `seat-*.log` 文件名 | `seat-<学号A>.log` 等占位符，并加注说明原始文件名见本机副本 |
| `SPEC.md` | 附录 B | 第三个 cron 任务名含真实姓名 | `图书馆抢座-用户三` |
| `docs/ORGANIZATION.md` | `cron/` 说明行 | 第四个 cron 任务含真实姓名 | `抢座-用户三 20 19 * * *` |

脱敏后复核文档，预期 0 命中：

```powershell
git grep -nIE '<姓名A>|<姓名B>|<姓名C>|20234[0-9]{5}|<密码A>|<密码B>|<密码C>' -- '*.md'
```

`PLAN.md` 与 `docs/REVIEW_LOG.md` 原本就不含敏感串，无需脱敏。

## 原始数据的存放位置

全部排除项的原始文件保存在开发者本机，不随仓库分发：

- 本机完整下载：`qfnulibrary-download/extracted/`
- 重组前清单：`qfnulibrary-download/pre-reorg-manifest.csv`（1691 行，含全部文件的 SHA256）

本仓库 `docs/ORGANIZATION.md` 的「重新获取原始数据」一节按来源分组列出了具体路径。

## 远端历史中的既有问题

远端 `origin/main` 在 2026-09-14 的历史推送中已包含 `configs/user1.yml` 与 `configs/user2.yml` 的明文密码。本次推送采用快进方式，只在历史顶部追加提交，无法移除旧提交里的这两处密码。彻底清理需要重写已推送的 Git 历史并强制推送，属于不可逆操作，需单独决策。