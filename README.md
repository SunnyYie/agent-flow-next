# agent-flow-next

Three-layer AgentFlow implementation with unified assets, governance promotions, and migration tooling.

## 已实现功能

- 三层资源模型（`global / team / project`）初始化与路径解析
- 团队绑定：项目绑定到指定 `team_id`
- 团队型初始化：自动生成团队目录（`<team_id>/`）、`readme.md`、`wiki/Index.md`、`skills/Index.md` 与 `skills/wiki` 锚点文档
- 资源解析（overlay）：`project > team > global`，并支持治理 Hook 保护策略
- 资源管理（通用）：`asset resolve/list/show/create/lint`
- 团队信息（通用）：`team list/info`
- 晋升治理流程（V1）：`promote submit/review/ai-review/status/finalize`
  - 支持类型：`skill/wiki/hook`
  - 支持路径：`project -> team -> global`（禁止跳级）
  - 提案与审计存储：团队级目录（跨项目可见）
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
agent-flow hooks --help
```

## 使用说明

### 1. 初始化

```bash
# 初始化全局层（默认在 agent_flow/resources/global）
agent-flow init --global

# 初始化项目层（当前目录下 .agent-flow，默认行为）
agent-flow init

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
│   ├── runtime/
│   └── governance/
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

项目初始化后 hooks 结构如下：

```text
.agent-flow/
└── hooks/
    ├── runtime/
    └── governance/
```

Hook 模版来源（按场景）：
- 团队初始化：`agent_flow/templates/team/hooks/*` -> `{team_id}/hooks/*`
- 项目初始化：`agent_flow/templates/project/hooks/*` -> `.agent-flow/hooks/*`

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

V1 规则：
- 仅支持 `skill/wiki/hook`
- 仅允许两条路径：`project -> team`、`team -> global`
- `promote finalize` 会执行目标层复制并写团队审计日志
- 目标层同名冲突时会 reject（不会覆盖）
- `platform` 只是团队名称（例如 `--team-id platform`），不是独立 layer

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
  --decision approved \
  --summary "looks good"

# AI 审核
agent-flow promote ai-review <proposal_id> \
  --profile reusable \
  --decision approved \
  --summary "generic enough"

# 查看状态与最终落地
agent-flow promote status <proposal_id>
agent-flow promote finalize <proposal_id>

# 可选：在 review/ai-review/status/finalize 指定 team 覆盖当前项目绑定
agent-flow promote status <proposal_id> --team-id acme
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

### 7. Claude Code 项目级 Hooks 配置

```bash
# 一键将 AgentFlow 项目 hooks 写入当前项目 .claude/settings.json
agent-flow hooks setup-claude
```

默认写入命令：
- `python3 .agent-flow/hooks/governance/promotion-guard.py`
- `python3 .agent-flow/hooks/runtime/pre-compress-guard.py`
- `python3 .agent-flow/hooks/runtime/context-guard.py`

该命令只会修改当前项目目录下的 `.claude/settings.json`，不会改动全局 `~/.claude/settings.json`，因此不会影响其他项目。

## 当前范围说明

当前仓库聚焦“通用能力”：三层资源、团队基础、资产管理、治理晋升、迁移与检查。

以下旧版能力未纳入当前通用范围：`pipeline/run/review/qa/ship`、`agent`、`user`、`memory/recall`、`hermes`、`adapt` 等运行时或平台耦合功能。
