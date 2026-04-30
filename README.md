# AgentFlow Next

AgentFlow Next 是一个"核心最小化 + 插件扩展"的多层工作流 CLI。

- 核心只负责：初始化、插件系统、动态命令加载
- 业务能力由插件提供：pipeline、agent、memory、team、promote、runtime 等
- 三层作用域：`global / team / project`
- 资源类型：skill、wiki、reference、tool、hook、soul

---

## 从 0 到 1 快速上手

### 1. 安装

```bash
cd /Users/sunyi/ai/agent-flow-team
pip install -e .
agent-flow --help
```

### 2. 初始化 Global（机器级）

```bash
agent-flow init --global
```

这会初始化全局层，并自动安装内置插件到 global scope。

### 3. 初始化 Team（团队级）

```bash
# 在你的团队根目录执行
agent-flow init --team --team-id acme
```

默认 team 路径：
- `${AGENT_FLOW_TEAM_ROOT:-当前目录}/acme/.agent-flow/`

如果希望固定团队根目录：

```bash
export AGENT_FLOW_TEAM_ROOT=/path/to/team-root
agent-flow init --team --team-id acme
```

Team 初始化支持 hooks profile：
- `minimal`（默认）：仅安装必要的 guard hooks
- `full`：安装全部 hooks（guards + enforcers + reminders + trackers）

```bash
agent-flow init --team --team-id acme --hooks-profile full
```

### 4. 初始化 Project（项目级）

```bash
cd /path/to/your-project
agent-flow init
```

这会创建项目 `.agent-flow/` 并自动安装 project scope 内置插件。

### 5. 绑定项目到团队（可选但推荐）

```bash
cd /path/to/your-project
agent-flow bind-team acme
```

绑定后资源解析优先级：`project > team > global`。

---

## 初始化后如何检查

```bash
# 查看生效插件（effective view）
agent-flow plugin list

# 查看所有命令（会包含动态插件命令）
agent-flow --help

# 健康检查
agent-flow doctor
```

---

## 插件系统使用

## 作用域

- `project`：当前项目生效
- `team`：指定团队生效（需 `--team-id`）
- `global`：当前机器生效

## 安装插件

### 1) 安装内置插件

```bash
# project scope
agent-flow plugin install workflow-pipeline --scope project --source builtin:workflow-pipeline

# team scope
agent-flow plugin install workflow-pipeline --scope team --team-id acme --source builtin:workflow-pipeline

# global scope
agent-flow plugin install workflow-pipeline --scope global --source builtin:workflow-pipeline
```

### 2) 安装本地插件

```bash
agent-flow plugin install my-plugin --scope project --source local:./plugins/my-plugin
```

## 启用/禁用插件

```bash
agent-flow plugin disable workflow-pipeline --scope project
agent-flow plugin enable workflow-pipeline --scope project
```

> 禁用后：命令不可见、插件 hooks 从项目 `.claude/settings.json` 移除。

## 卸载插件

```bash
agent-flow plugin uninstall workflow-pipeline --scope project
```

## 更新插件

支持独立 `plugin update` 子命令，会重装插件并同步 hooks 到项目 `.claude/settings.local.json`。

例如（沿用当前安装记录的 source）：

```bash
agent-flow plugin update workflow-pipeline --scope project
```

也可以显式覆盖 source：

```bash
agent-flow plugin update workflow-pipeline --scope project --source builtin:workflow-pipeline
```

批量升级当前 scope 下全部已安装插件：

```bash
agent-flow plugin update --scope project --all
```

只升级版本发生变化（outdated）的插件：

```bash
agent-flow plugin update --scope project --all --only-outdated
```

## 查看插件列表

```bash
# 生效视图（project > team > global）
agent-flow plugin list

# 仅看已启用
agent-flow plugin list --enabled-only
```

---

## 常用 CLI 命令

> 下面命令由插件动态提供；若提示不存在，先执行 `agent-flow init` 和 `agent-flow plugin list` 检查安装状态。

## 初始化与插件

```bash
agent-flow init [--global|--team --team-id <id>]
agent-flow plugin --help
```

## 团队与协作

```bash
agent-flow team list
agent-flow team info
agent-flow bind-team <team-id>
agent-flow init-team-flow --team-id <team-id> --name "Team Name"
```

## 资源管理与治理

```bash
agent-flow asset resolve
agent-flow asset list --kind all --layer all
agent-flow asset create --kind wiki --name concepts/new-doc --layer project

agent-flow promote submit --kind skill --name demo --from-layer project --to-layer team --team-id acme --source-path <path>
agent-flow promote review <proposal_id> --reviewer alice --role maintainer --decision approved --summary "ok"
agent-flow promote finalize <proposal_id>

agent-flow organize
agent-flow organize --dry-run
```

## Pipeline 工作流

```bash
agent-flow plan-review --spec spec.md
agent-flow plan-eng-review --spec spec.md
agent-flow add-feature payment-flow
agent-flow run --tasks 1,2
agent-flow review
agent-flow qa
agent-flow ship

agent-flow pipeline status
agent-flow pipeline run --to-stage qa
agent-flow pipeline resume --from-stage run
```

## Agent / Memory / User / Hermes

```bash
agent-flow agent list
agent-flow agent spawn --role executor --task "Implement T1"
agent-flow agent sync

agent-flow memory index
agent-flow memory search --query "feature flag"
agent-flow recall --query "payments"

agent-flow user show
agent-flow user set-autonomy 4

agent-flow skill list
agent-flow skill create --name payments-pattern --trigger payments --procedure "..."
agent-flow hermes status
```

## Runtime 适配

```bash
agent-flow adapt --platform claude-code
agent-flow hooks setup-claude
agent-flow hooks inject-context --target claude-hook
```

## MCP 工厂

```bash
agent-flow mcp-factory --help
```

## 诊断

```bash
agent-flow doctor
agent-flow doctor --json
```

---

## 当前内置插件

| 插件 | 命名空间 | 命令 | Hooks | 说明 |
|------|---------|------|-------|------|
| workflow-pipeline | pipeline | pipeline, plan-review, plan-eng-review, add-feature, run, review, qa, ship | — | Pipeline 工作流阶段 |
| workflow-guards | workflow-guards | — | 18 个 (guards, enforcers, reminders, trackers) | 运行时执行器（含 requirement-entry、UI/多Agent门控、反思总结门控） |
| agent-orchestration | agent-orchestration | agent | — | 多 Agent 调度与结构化状态 |
| memory-recall | memory-recall | memory, recall | — | 记忆索引、压缩、召回、生命周期 |
| user-profile | user-profile | user | — | 用户模型与自主权设置 |
| hermes-skillops | hermes-skillops | hermes, skill | — | 技能管理与演进 |
| runtime-adapters | runtime-adapters | hooks, adapt | — | 平台运行时适配 |
| team-collaboration | team-collaboration | team, bind-team, init-team-flow | — | 团队绑定与同步 |
| organization-evolution | organization-evolution | asset, promote, organize | — | 资产晋升、衰减、反思 |
| mcp-factory | mcp-factory | mcp-factory | 2 个 guards | MCP 工具工厂 |
| ops-doctor | ops-doctor | doctor | — | 健康诊断 |
| builtin-demo | builtin-demo | demo | 1 个 hook | 启动与注册链路 smoke-test 插件 |

---

## 排障建议

### 命令不存在

1. 执行 `agent-flow init`
2. 执行 `agent-flow plugin list`
3. 确认目标插件为 `enabled`

### team scope 报错需要 team_id

- 使用 `--team-id <id>`
- 或先在项目中 `agent-flow bind-team <id>`

### Hook 没生效

- 检查项目 `.claude/settings.json`
- 重新 `agent-flow plugin disable/enable <plugin> --scope project`

---

## Requirement-Entry 与反思总结（新增）

当 Claude Code 输入“阅读需求文档并执行任务”类提示词时，`workflow-guards` 会自动触发 requirement-entry 流程：

1. 解析提示词并生成 `.agent-flow/state/request-context.json`
2. 自动准备流程骨架：
   - `.agent-flow/state/requirements-initial.md`
   - `.agent-flow/state/task-list.md`
   - `.agent-flow/wiki/project-structure.md`
   - `.agent-flow/state/phase-review.md`
   - `.agent-flow/state/agent-team-config.yaml`

### UI 门控策略

- 仅当 `request-context.json` 中 `ui_constraints_required=true` 时，才启用 UI 强门控
- 非 UI 任务不会因为目录路径等误判触发 UI 阻断

### 多 Agent 路由策略

- `task-list.md` 需要包含 `任务类型` 与 `执行Agent`
- 若存在多个任务类型但都分配给同一个 agent，`workflow-enforce` 会阻断并给出建议分配

### 任务完成后的反思总结

- 中高复杂度任务（`medium/complex`）在 Implement 后会触发反思提醒
- 自动生成反思草稿并按类型沉淀：
  - 通用业务经验 -> `.agent-flow/wiki/retrospectives/*.md`
  - 可复用流程/工具模式 -> `.agent-flow/skills/retrospectives/*/SKILL.md`
- 在 `git push` / `glab mr` 前，若缺 `.agent-flow/state/.task-reflection-done`，会被硬阻断

### 搜索门控优化（简单替换白名单 + 连续会话共享）

- 对简单字符串替换（如 CDN URL host 替换）支持白名单放行，不再强制每次都先搜索 skills/wiki
- 对长会话支持“同类型连续操作”共享一次搜索标记（默认：`medium` 2h、`complex` 1.5h）
- 同一共享会话仅允许同类型操作复用（如 `code_edit` 可连续复用，切到 `bash_exec` 需重新搜索）

可在 `.agent-flow/config.yaml` 配置：

```yaml
workflow_guards:
  simple_replace_whitelist:
    enabled: true
    max_chars: 300
    max_lines: 2
    file_globs:
      - "**/*"
    keywords:
      - "cdn"
      - "static"
      - "asset"
  shared_search_session:
    enabled: true
    ttl_seconds:
      medium: 7200
      complex: 5400
```

---

## 设计原则

- 核心稳定，能力插件化
- scope 隔离，按优先级覆盖
- 配置可审计，状态可回放
- 兼容迁移，逐步替换旧 CLI 能力
- Team hooks 支持 minimal/full profile，按需安装
