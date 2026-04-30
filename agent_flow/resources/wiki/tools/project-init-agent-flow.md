---
name: project-init-agent-flow
type: tool
module: init
status: active
confidence: 0.99
created: 2026-04-28
last_validated: 2026-04-28
tags: [agent-flow, init, project, settings.local.json, plugin-hooks]
---

# 项目内初始化 AgentFlow（含插件 Hook 注册）

## 目标

在当前项目完成以下动作：

1. 使用agent-flow CLI初始化.agent-flow（project scope）
2. 安装需要的插件（可选，但推荐至少安装 workflow-guards、workflow-pipeline、mcp-factory 等核心插件）
3. 将插件 hooks 同步到 `.claude/settings.local.json`
4. 注册 Agent-flow skills 到 Claude/Codex 运行时目录
5. 验证 hooks 与 effective plugins 一致

## 标准步骤

```bash
# 1) 安装 CLI（仓库开发模式）
pip install -e .

# 2) 在目标项目目录初始化 project scope
agent-flow init

# 3) 查看生效插件
agent-flow plugin list

# 4) 验证 hooks 是否正确注册
agent-flow plugin verify

# 5) 检查 skills 注册（Claude/Codex）
ls -la .claude/skills .agents/skills
```

## 安装指定插件（示例）

```bash
agent-flow plugin install workflow-guards --scope project --source builtin:workflow-guards
agent-flow plugin install workflow-pipeline --scope project --source builtin:workflow-pipeline
agent-flow plugin install mcp-factory --scope project --source builtin:mcp-factory
```

安装/启用/禁用/卸载插件后，都会触发项目 hooks 重同步。

## Skill 注册结果位置

- Claude Code 运行时 skills：`.claude/skills/agent-flow-*`
- Codex 运行时 skills：`.agents/skills/agent-flow-*`
- 注册状态清单：`.agent-flow/state/skill-registrations.json`

默认会注册三层来源（按存在性）：

- `agent-flow-project` -> `.agent-flow/skills`
- `agent-flow-team` -> `<team_root>/.agent-flow/skills`（仅绑定团队后）
- `agent-flow-global` -> 全局或 bundled skills

## 注册结果位置

- 插件托管 hooks：`.claude/settings.local.json`
- 项目默认 hooks（非插件托管）：`.claude/settings.json`

说明：插件 hooks 以 `settings.local.json` 为主，并会清理 legacy `settings.json` 里历史插件项，避免 stale hooks。

## 验证通过标准

执行：

```bash
agent-flow plugin verify
```

应满足：

- `missing hooks` 为空
- `stale hooks` 为空
- 输出 `plugin hooks verified: OK`

## 常见问题

1. `plugin verify` 有 missing hooks
   先执行 `agent-flow plugin list` 确认插件是否 enabled，再执行一次 `agent-flow plugin enable <name> --scope project` 触发重同步。

2. 项目没有 `.claude/settings.local.json`
   通常是还未安装任一含 hooks 的插件；先 `plugin install` 后再 `plugin verify`。
