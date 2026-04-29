# AgentFlow Plugins

AgentFlow 插件目录，每个插件通过 `manifest.yaml` 声明命令（commands）和钩子（hooks）。

---

## 1. agent-orchestration

轻量级子 Agent 记录管理，用于在项目中跟踪 sub-agent 的创建、运行和终止。

| 命令 | 说明 |
|------|------|
| `agent list` | 列出所有子 Agent 记录 |
| `agent spawn --role <role> --task <desc> [--name <name>]` | 创建子 Agent，role 可选 executor/verifier/researcher/tech-leader |
| `agent terminate <name> [--result <text>]` | 终止指定子 Agent 并记录结果 |
| `agent sync [--agent-name <name>]` | 同步 Agent 记忆（默认 all） |

数据存储在 `.agent-flow/state/agents.json`。

---

## 2. hermes-skillops

Hermes 原生工具 + Skill 技能管理。

### hermes 组

| 命令 | 说明 |
|------|------|
| `hermes status` | 显示 Hermes 状态 |
| `hermes snapshot [--name <name>]` | 创建记忆快照，存储在 `.agent-flow/memory/snapshots/` |
| `hermes search <query>` | 在 `.agent-flow/` 下搜索包含关键词的 Markdown 文件 |
| `hermes hooks` | 列出 Hermes 支持的 hooks 事件 |

### skill 组

| 命令 | 说明 |
|------|------|
| `skill create --name <n> --procedure <p> [--trigger] [--rules] [--scope project\|global]` | 创建新 Skill 文件 |
| `skill edit --name <n> [--procedure] [--rules] [--scope project\|global]` | 追加更新 Skill 内容 |
| `skill patch --name <n> --field <key=value> [--scope project\|global]` | 在文件头部插入字段 |
| `skill delete --name <n> [--scope project\|global]` | 删除 Skill |
| `skill list [--scope project\|global]` | 列出所有 Skill |
| `skill show --name <n> [--scope project\|global]` | 显示 Skill 完整内容 |

Skill 存储路径：项目级 `.agent-flow/skills/` 或全局 `~/.agent-flow/skills/`。

---

## 3. mcp-factory

MCP Tool Factory 提案与审批工作流，含两个自动守护钩子。

### 命令

| 命令 | 说明 |
|------|------|
| `mcp-factory request [--task] [--scope project\|global] [--summary] [--proposal-file]` | 发起 MCP Server 创建请求，生成提案模板和 marker |
| `mcp-factory approve [--task] [--confirmed-by] [--summary]` | 批准待处理请求 |
| `mcp-factory reject [--task] [--confirmed-by] [--summary]` | 拒绝待处理请求 |

### Hooks

| Hook | 事件 | 说明 |
|------|------|------|
| `implementation-clarification-guard` | PreToolUse (Write/Edit/Bash...) | 当 `.implementation-question-raised` 标记存在时，阻止代码修改操作，直到用户解决澄清项 |
| `mcp-tool-factory-guard` | PreToolUse (Write/Edit/Bash) | 当 `.mcp-tool-factory-requested` 标记状态为 pending 时，阻止代码修改操作，要求先完成审批 |

状态文件存储在 `.agent-flow/state/`。

---

## 4. memory-recall

记忆管理与跨会话回顾。

### memory 组

| 命令 | 说明 |
|------|------|
| `memory compress [--text <content>]` | 压缩并保存一条记忆条目 |
| `memory index` | 刷新记忆索引 |
| `memory search --query <keyword>` | 搜索记忆条目 |
| `memory get <id>` | 获取指定 ID 的记忆条目 |
| `memory stats` | 显示记忆条目统计 |

数据存储在 `.agent-flow/memory/entries.jsonl`。

### recall 命令

| 命令 | 说明 |
|------|------|
| `recall [--query <keyword>]` | 按关键词搜索历史会话摘要 |
| `recall --recent <n>` | 显示最近 N 条会话摘要 |
| `recall --backtrack <id>` | 回溯指定 ID 的完整会话摘要 |

搜索路径：`.agent-flow/wiki/recall/` 和 `~/.agent-flow/wiki/recall/`。

---

## 5. ops-doctor

诊断当前项目的 AgentFlow 配置和资产完整性。

| 命令 | 说明 |
|------|------|
| `doctor [--json]` | 运行诊断检查，输出报告。`--json` 输出 JSON 格式 |

---

## 6. organization-evolution

资产管理、知识晋升与整理。

### asset 组

| 命令 | 说明 |
|------|------|
| `asset resolve` | 解析所有层级资源 |
| `asset list [--kind <kind>] [--layer <layer>] [--team-id <id>]` | 列出资产。kind 可选 skills/wiki/references/tools/hooks/souls/all，layer 可选 global/team/project/all |
| `asset show --kind <kind> --name <name> [--team-id <id>]` | 显示资产详情 |
| `asset create --kind <kind> --name <name> --layer <layer> [--team-id <id>] [--force]` | 创建资产文件，`--force` 覆盖已有文件 |
| `asset lint [--team-id <id>] [--json]` | 检查资产完整性（缺失 souls、shadow chain 等） |

### promote 组

| 命令 | 说明 |
|------|------|
| `promote submit --kind <k> --name <n> --from-layer <l> --to-layer <l> --team-id <id> --source-path <p>` | 提交晋升提案 |
| `promote review <proposal_id> --reviewer <r> --role <r> --decision <d> [--summary]` | 人工审核晋升提案 |
| `promote ai-review <proposal_id> --profile <p> --decision <d> --summary <s>` | AI 审核晋升提案 |
| `promote status <proposal_id>` | 查看提案状态 |
| `promote finalize <proposal_id>` | 终审通过并执行晋升 |

### organize 命令

| 命令 | 说明 |
|------|------|
| `organize [--dry-run] [--scope memory\|wiki\|recall\|all]` | 整理知识资产。`--dry-run` 仅预览，报告输出到 `.agent-flow/state/organize-report.md` |

---

## 7. runtime-adapters

将 AgentFlow 规则适配到不同 AI 编码平台，并管理 Claude Code hooks。

### adapt 命令

| 命令 | 说明 |
|------|------|
| `adapt --platform <platform>` | 生成对应平台的规则文件。platform 可选 claude-code/codex/copilot/generic |

生成目标：
- `claude-code` → `~/.claude/rules/agent-flow-runtime.md`
- `codex` → `.codex/instructions.md`
- `copilot` → `.github/copilot/instructions.md`
- `generic` → `.agent-flow/prompts/system-prompt.md`

### hooks 组

| 命令 | 说明 |
|------|------|
| `hooks setup-claude` | 将 workflow-guards 等钩子注册到项目 `.claude/settings.json` |

---

## 8. team-collaboration

团队协作与项目绑定。

### team 组

| 命令 | 说明 |
|------|------|
| `team list` | 列出所有可用团队 |
| `team info [--team-id <id>]` | 显示团队详情（成员、资产统计等），默认使用项目绑定 |

### 独立命令

| 命令 | 说明 |
|------|------|
| `bind-team <team_id>` | 将当前项目绑定到指定团队 |
| `init-team-flow --team-id <id> [--name <name>]` | 初始化团队工作流目录结构 |

---

## 9. user-profile

用户偏好与自主级别管理。

| 命令 | 说明 |
|------|------|
| `user show` | 显示当前用户配置 |
| `user set-autonomy <level>` | 设置自主级别（1-5）：1=manual, 2=low, 3=balanced, 4=high, 5=auto |
| `user add-avoidance <tool_or_framework>` | 添加到规避列表（Agent 永不推荐） |
| `user observe` | 观察近期会话并更新配置 |

数据存储在 `.agent-flow/state/user-profile.json`。

---

## 10. workflow-guards

工作流守护钩子集，无命令，通过 12 个 hooks 自动执行质量门控。

### UserPromptSubmit Hooks

| Hook | 说明 |
|------|------|
| `preflight-guard` | 预飞检查：确保任务开始前完成必要准备 |
| `self-questioning-enforce` | 强制自问：要求 Agent 在执行前自检疑点 |
| `user-acceptance-guard` | 用户确认守卫：关键操作前需用户确认 |
| `parallel-enforce` | 并行执行强制：识别可并行的子任务 |

### PreToolUse Hooks

| Hook | 匹配工具 | 说明 |
|------|---------|------|
| `preflight-enforce` | Write/Edit/Bash | 执行写操作前强制完成预飞检查 |
| `workflow-enforce` | Write/Edit/Bash | 强制遵守开发工作流规范 |
| `project-structure-enforce` | Grep | 搜索时强制遵守项目结构规范 |
| `thinking-chain-enforce` | Write/Edit/Bash | 强制思考链：写操作前必须完成推理记录 |
| `subtask-guard-enforce` | Write/Edit/Bash | 子任务守卫：确保在正确子任务上下文内操作 |

### PostToolUse Hooks

| Hook | 说明 |
|------|------|
| `search-tracker` | 追踪搜索行为，防止重复搜索 |
| `error-search-remind` | 出错时提醒搜索解决方案 |
| `phase-reminder` | 阶段提醒：根据当前阶段提示下一步操作 |

---

## 11. workflow-pipeline

开发流水线工作流，管理从计划到发布的完整流程。

### pipeline 组

| 命令 | 说明 |
|------|------|
| `pipeline status` | 查看各阶段状态 |
| `pipeline run [--to-stage <stage>]` | 执行到指定阶段 |
| `pipeline resume [--from-stage <stage>]` | 从指定阶段恢复执行 |

### 流水线阶段（按顺序）

| 命令 | 阶段名 | 说明 |
|------|--------|------|
| `plan-review [--spec <path>] [--mode expansion\|selective\|hold\|reduction]` | plan-review | 计划评审 |
| `plan-eng-review [--spec <path>] [--scope frontend\|full]` | plan-eng-review | 工程评审 |
| `add-feature <name>` | add-feature | 创建特性分支（`feat/<name>`） |
| `run [--tasks <ids>] [--dry-run]` | run | 执行任务 |
| `review` | review | 代码审查 |
| `qa [--suite <name>]` | qa | 质量保证 |
| `ship [--base-branch <branch>] [--dry-run]` | ship | 发布上线 |

流水线状态存储在 `.agent-flow/state/pipeline-state.yaml`。
