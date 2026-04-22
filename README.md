# agent-flow-next

Three-layer AgentFlow implementation with unified assets, governance promotions, and migration tooling.

## 已实现功能

- 三层资源模型（`global / team / project`）初始化与路径解析
- 团队绑定：项目绑定到指定 `team_id`
- 团队型初始化：自动生成团队目录（`<team_id>/`）、`readme.md`、`wiki/Index.md`、`skills/Index.md` 与 `skills/wiki` 锚点文档
- 资源解析（overlay）：`project > team > global`，并支持治理 Hook 保护策略
- 资源管理（通用）：`asset resolve/list/show/create/lint`
- 团队信息（通用）：`team list/info`
- 晋升治理流程：`promote submit/review/ai-review/status/finalize`
- 健康检查：`doctor`（支持 `--json`）
- 旧资产迁移：`migrate-legacy`

## 安装与运行

### 本地开发安装

```bash
pip install -e .
```

### 查看命令

```bash
agent-flow --help
agent-flow asset --help
agent-flow promote --help
```

## 使用说明

### 1. 初始化

```bash
# 初始化全局层（默认在 agent_flow/resources/global）
agent-flow init --global

# 初始化项目层（当前目录下 .agent-flow）
agent-flow init --project

# 初始化团队层
agent-flow init --team --team-id acme

# 初始化团队型 Agent-flow（包含 team 索引/锚点/readme）
agent-flow init-team-flow --team-id acme --name "Acme Team"
```

### 2. 绑定团队

```bash
agent-flow bind-team acme
```

会把当前项目写入 `team_id` 绑定信息，用于资源解析时加载团队层。

团队层默认生成路径：`{当前目录}/{team_id}/`（可通过 `AGENT_FLOW_TEAM_ROOT` 覆盖）。

初始化时会默认创建以下结构（目录默认空，文档为引导与锚点）：

```text
{team_id}/
├── hooks/
│   ├── governance/
│   └── runtime/
├── references/
├── skills/
│   ├── ANCHOR.md
│   └── Index.md
├── souls/
├── tools/
├── wiki/
│   ├── ANCHOR.md
│   └── Index.md
├── readme.md
└── team.yaml
```

### 3. 资源管理（asset）

```bash
# 查看各类资源解析数量
agent-flow asset resolve

# 列出资源（支持 kind/layer 过滤）
agent-flow asset list --kind all --layer all
agent-flow asset list --kind skills --layer project

# 查看单个资源
agent-flow asset show --kind wiki --name concepts/agent-roles

# 创建资源
agent-flow asset create --kind wiki --name concepts/new-doc --layer project
agent-flow asset create --kind skills --name workflow/new-skill --layer team --team-id acme

# 资源检查
agent-flow asset lint
agent-flow asset lint --json
```

`asset create` 支持的 `kind`：`skills/wiki/references/tools/hooks/souls`。

### 4. 团队信息（team）

```bash
# 列出本机所有团队目录
agent-flow team list

# 查看团队信息
agent-flow team info --team-id acme
```

### 5. 晋升治理（promote）

```bash
# 提交晋升提案
agent-flow promote submit \
  --kind skill \
  --name workflow/new-skill \
  --from-layer project \
  --to-layer team \
  --team-id acme \
  --source-path .agent-flow/skills/workflow/new-skill/SKILL.md

# 人工审核
agent-flow promote review <proposal_id> \
  --reviewer alice \
  --role maintainer \
  --decision approve \
  --summary "looks good"

# AI 审核
agent-flow promote ai-review <proposal_id> \
  --profile reusable \
  --decision approve \
  --summary "generic enough"

# 查看状态与最终落地
agent-flow promote status <proposal_id>
agent-flow promote finalize <proposal_id>
```

### 6. 健康检查与迁移

```bash
# 健康检查
agent-flow doctor
agent-flow doctor --json

# 迁移旧仓库资产
agent-flow migrate-legacy \
  --legacy-project /path/to/legacy-project \
  --global-source /path/to/legacy-global \
  --team-id acme \
  --include-project-knowledge
```

## 当前范围说明

当前仓库聚焦“通用能力”：三层资源、团队基础、资产管理、治理晋升、迁移与检查。

以下旧版能力未纳入当前通用范围：`pipeline/run/review/qa/ship`、`agent`、`user`、`memory/recall`、`hermes`、`adapt` 等运行时或平台耦合功能。
