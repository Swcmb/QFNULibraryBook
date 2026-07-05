# OpenClaw 已同步资源完整测试计划

> 目标：验证 OpenClaw（云服务器 47.104.159.142）能正确使用所有已同步的规则文件、技能文件、记忆数据和 MCP 工具。

---

## 测试环境快照

| 项目 | 值 |
|:---|:---|
| 服务器 IP | 47.104.159.142 |
| Workspace | `/root/.openclaw/workspace`（517 个文件） |
| 默认模型 | sensenova/sensenova-6.7-flash-lite（256K ctx） |
| 备用模型 | sensenova/deepseek-v4-flash（128K ctx） |
| MCP 服务器 | celiums-memory ✓ |
| 插件 | 49/49 启用 |
| 技能 | 16/54 就绪 |
| 频道 | openclaw-weixin（已配置） |
| Gateway | local:18789，密码 admin123 |

---

## 测试用例

### TC-01：验证规则文件可被正确注入 Agent 上下文

**前提**：workspace 中存在 9 条规则文件（与本地 `~/.claude/rules/` 完全同步）

**测试方法**：
1. 向 agent 发送指令："请列举 workspace 中所有 rules 文件的内容摘要"
2. 验证 agent 能准确识别每一条规则文件
3. 针对每一条规则，提出一个依赖该规则才能回答的问题，验证 agent 使用了正确的规则

**通过标准**：
- Agent 至少能列出 9 条规则中的 8 条
- Agent 能根据规则内容正确回答问题（如：根据 `package-manager.md`，问"安装 torch 用什么" → 应回答 conda）

| 规则文件 | 验证问题 | 预期回答 |
|:---|:---|:---|
| `celiums-memory.md` | "celiums 有哪些 MCP 工具？" | 列出 7 个 tool |
| `code-quality.md` | "代码注释用什么语言？" | 简洁中文注释 |
| `compilation-chain.md` | "MinGW 编译参数有哪些？" | `-std=c++23 -static-libgcc -static-libstdc++ -O2` |
| `documentation-organization.md` | "规格文档放哪里？" | `./claude-context/` |
| `github-kb.md` | "本地 GitHub 仓库根目录在哪？" | `D:\github-kb` |
| `netease-music-player.md` | "音质等级有哪些？" | 标准/高品质/无损/Hi-Res |
| `open-websearch.md` | "默认搜索引擎是什么？" | bing |
| `package-manager.md` | "安装 torch 用什么包管理器？" | conda（绝对不能用 pip/uv） |
| `special-responses.md` | "用户说创建 skill 应该做什么？" | 调用 skill-creator，放到 D:\ProgramFiles\Skill |

---

### TC-02：验证 Celiums MCP 工具可在 Agent 交互中正常使用

**前提**：MCP 服务器 celiums-memory 已连接（已验证 JSON-RPC 返回 7 个 tools）

**测试方法**：
1. 循环测试各 Celiums MCP 工具

| 子测试 | 工具 | 测试指令 | 预期行为 |
|:---|:---|:---|:---|
| TC-02a | `remember` | "记住：今天是 2026年7月6日，我正在测试 OpenClaw" | 工具调用成功，记忆存储 |
| TC-02b | `emotion` | "你现在感觉如何？" | 返回 PAD 三元组 + 情感标签 |
| TC-02c | `search` | "搜索关于 OpenClaw 测试的记忆" | 返回匹配记忆的 ID 和摘要（含刚存储的） |
| TC-02d | `recall` | "详细回忆 OpenClaw 测试相关的内容" | 返回完整记忆记录 |
| TC-02e | `timeline` | "最近 24 小时发生了什么？" | 按时间线列出记忆 |
| TC-02f | `forget` | "删除刚才测试用的记忆" | 删除成功，再次 search 不再返回 |

**通过标准**：
- 每个工具调用成功，无 JSON-RPC 错误
- Agent 能根据工具返回的数据自然组织语言回复
- 工具返回的数据格式与本地 Claude Code 一致

---

### TC-03：验证技能文件可被 Agent 正确加载和使用

**前提**：workspace 中包含大量 `skills-reference/` 目录下的 SKILL.md 文件

**测试方法**：
1. 选取 5 个代表性的技能，分别触发其使用场景

| 子测试 | 技能文件 | 触发指令 | 预期行为 |
|:---|:---|:---|:---|
| TC-03a | `diagram-maker` | "画一个系统架构图" | 生成 SVG/HTML/Excalidraw 图表 |
| TC-03b | `browser-automation` | "打开浏览器访问 example.com" | 调用 browser 工具 |
| TC-03c | `clawhub` | "搜索一个能做数据分析的技能" | 调用 ClawHub 搜索 |
| TC-03d | `canvas` | "创建一个 HTML 画布" | 生成 HTML 内容并展示 |
| TC-03e | `caveman-help` | "用 caveman 模式解释什么是 MCP" | 使用 ultra 压缩格式输出 |

**通过标准**：
- Agent 能找到并加载对应的 skill
- 输出符合该 skill 定义的行为规范
- 对于 "needs setup" 的技能，agent 应主动提示配置步骤

---

### TC-04：验证记忆数据跨机器可访问

**前提**：workspace 中包含来自多台机器的记忆数据（`memory/` 目录）

**测试方法**：
1. 搜索来自不同机器的记忆："搜索和编程相关的记忆"
2. 搜索跨机器的内容："搜索关于 open-websearch 的记忆"

**通过标准**：
- Agent 能查找到记忆（只要相关信息已被同步到该机器）
- 如果某条记忆存在但搜索不到，属于同步不完整问题，需标记

---

### TC-05：验证 Agent 能正确使用 Workspace 中的文件路径

**前提**：`openclaw.json` 中 `agents.defaults.workspace` 指向 `/root/.openclaw/workspace`

**测试方法**：
1. "读取 SOUL.md 的内容" → 验证 agent 能读取 workspace 根文件
2. "读取 rules/code-quality.md" → 验证 agent 能读取子目录文件
3. "统计 workspace 中有多少 skill 文件" → 验证 agent 能遍历目录

**通过标准**：
- Agent 能直接读取 workspace 中的文件（无需 `cat` 等 shell 命令）
- Agent 能正确报告文件数量（应在 517 左右）

---

### TC-06：验证模型能够处理长上下文（256K）

**前提**：默认模型 `sensenova-6.7-flash-lite` 支持 256K token

**测试方法**：
1. 让 agent 处理一个包含大量信息的指令："请在读取所有 rules 文件后，综合这些规则编写一份 AI 行为手册"
2. 观察 context window 使用情况

**通过标准**：
- Agent 能加载至少 5 个规则文件并综合它们的内容
- 输出不截断，推理完整
- 无需回退到备用模型

---

### TC-07：验证 49 个插件全部正常加载

**前提**：`openclaw plugins list --enabled --verbose` 显示 49/49 已启用

**测试方法**：
1. 遍历调用各插件的核心功能，抽样测试 5 个：
   - anthropic-provider：模型调用是否正常
   - browser-plugin：浏览器控制
   - alibaba-provider：阿里云 API
   - azure-speech：语音服务
   - openclaw-weixin：微信渠道

**通过标准**：
- 抽样测试的插件至少 4/5 正常响应
- 插件间无冲突导致整体加载失败

---

### TC-08：验证 Gateway HTTP 服务可用

**前提**：Gateway `local:18789`，密码 `admin123`

**测试方法**：
```bash
curl -X POST http://127.0.0.1:18789/api/chat \
  -H "Content-Type: application/json" \
  -d '{"password":"admin123","message":"ping"}'
```

**通过标准**：
- 返回 HTTP 200
- 返回格式正确的 JSON 响应
- 请求经过认证

---

### TC-09：验证技能引用完整性（补漏）

**前提**：workspace 中 517 个文件，技能参考有大量 SKILL.md

**测试方法**：
1. 统计 `skills-reference/` 下的技能目录数量
2. 与 OpenClaw 的 `skills list` 输出对比
3. 检查是否有技能 SKILL.md 存在但未被加载，或已加载但找不到对应文件

**通过标准**：
- 已知的 16/54 就绪技能在所有 SKILL.md 中都能找到对应文件
- 不需要的 "needs setup" 技能至少能识别其路径

---

## 执行顺序

```
Phase 1: 基础连通性验证
  └─ TC-05 (文件访问) → TC-06 (模型响应) → TC-08 (Gateway API)

Phase 2: 资源完整性验证
  └─ TC-01 (规则注入) → TC-09 (技能引用完整性)

Phase 3: 功能深度验证
  └─ TC-02 (Celiums MCP) → TC-03 (技能调用) → TC-07 (插件)

Phase 4: 跨机器能力验证
  └─ TC-04 (跨机器记忆)
```

---

## 风险与已知问题

1. **Agent 交互命令未返回输出**：`openclaw agent --message` 在调查中未产生可见输出（可能被 `tail -20` 截断或超时），TC-03/TC-05 需使用交互式或 websocket 方式验证
2. **仅一个 MCP 服务器**：如果测试需要其他 MCP 工具，需先通过 OpenClaw `mcp add` 注册
3. **sensenova API 可用性**：测试依赖第三方 API 服务 `token.sensenova.cn`，如果服务不可用请回退到备用模型
4. **weixin 频道**：已配置但未验证配置完整性，TC-07 的微信测试需有实际微信账号配对