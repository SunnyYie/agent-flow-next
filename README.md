# AgentFlow Next

AgentFlow Next 是一个“核心最小化 + 插件扩展”的多层工作流 CLI。

- 核心只负责：初始化、插件系统、动态命令加载
- 业务能力由插件提供：pipeline、agent、memory、team、promote、runtime 等
- 三层作用域：`global / team / project`

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

## 更新插件（当前版本）

当前 CLI 还没有独立 `plugin update` 子命令。推荐更新流程：

1. `plugin uninstall`
2. `plugin install`（重新安装目标版本/来源）

例如：

```bash
agent-flow plugin uninstall workflow-pipeline --scope project
agent-flow plugin install workflow-pipeline --scope project --source builtin:workflow-pipeline
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

## 诊断

```bash
agent-flow doctor
agent-flow doctor --json
```

---

## 当前内置插件

- `workflow-pipeline`
- `workflow-guards`
- `agent-orchestration`
- `memory-recall`
- `user-profile`
- `hermes-skillops`
- `runtime-adapters`
- `team-collaboration`
- `organization-evolution`
- `mcp-factory`
- `ops-doctor`

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

## 设计原则

- 核心稳定，能力插件化
- scope 隔离，按优先级覆盖
- 配置可审计，状态可回放
- 兼容迁移，逐步替换旧 CLI 能力
