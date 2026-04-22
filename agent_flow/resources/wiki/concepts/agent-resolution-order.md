---
title: "Agent 调度优先级：Skill → Agent → Command"
category: concept
module: architecture
agents: [main, planner, architect]
scope: global
tags: [agent, skill, command, resolution, priority]
confidence: 0.9
sources: [shanraisshan/claude-code-best-practice]
status: verified
created: 2026-04-14
updated: 2026-04-14
---

# Agent 调度优先级：Skill → Agent → Command

> 当多种机制可满足同一意图时，按 Skill → Agent → Command 优先级选择。

## 问题描述

Claude Code 有三种可编排机制：Skill（内联）、Agent（独立上下文）、Command（需显式 `/` 触发）。选择不当会导致：
- 用 Agent 做简单查询 → 上下文开销大
- 用 Skill 做复杂推理 → 上下文污染主对话
- 用 Command 做高频操作 → 每次需手动触发

## 优先级规则

```
优先级从高到低：
1. Skill（内联执行，零上下文开销）—— 首选
2. Agent（独立上下文，自主执行）—— 需要隔离时
3. Command（需显式 `/` 触发）—— 仅入口点
```

## 选择决策树

```
需要执行一个操作：
├── 能在主对话中内联完成？ → Skill
├── 需要独立上下文/长时间运行？ → Agent
└── 是用户显式触发的入口？ → Command
    └── Command 可编排 Agent + Skill
```

## 三种机制对比

| 维度 | Skill | Agent | Command |
|------|-------|-------|---------|
| 执行方式 | 内联，在当前对话 | 独立上下文 | 触发后可编排 |
| 上下文开销 | 零（注入当前对话） | 新建上下文 | 取决于内部编排 |
| 适合场景 | 知识注入、简单操作 | 复杂推理、长时间任务 | 用户入口点 |
| 自动触发 | paths glob 匹配 | 不自动触发 | 需 `/command` |
| 并行能力 | 无 | 支持多Agent并行 | 可编排并行 |

## Agent 两种用法

1. **Agent Skill**（预加载型）：通过 agent frontmatter 的 `skills:` 字段，将 Skill 内容注入 Agent 启动时。Agent 自动获得该知识，无需单独调用。
2. **独立 Agent**：通过 Agent tool 启动，拥有独立上下文窗口，适合复杂任务。

## Agent Frontmatter 关键字段

```yaml
name: agent-name
description: 一句话描述
model: sonnet | opus | haiku          # 模型选择
tools: [Read, Grep, Glob]             # 允许的工具
disallowedTools: [Edit, Write]        # 禁止的工具
maxTurns: 30                          # 最大轮次
skills: [skill-name]                  # 预加载的 Skill
mcpServers:                           # Agent 独有的 MCP
  server-name: ...
isolation: worktree                   # 在独立 worktree 中运行
background: true                      # 始终后台运行
effort: high                          # 努力等级
color: blue                           # CLI 输出颜色
initialPrompt: "..."                  # 自动提交的首条消息
```

## 应用方式

- **简单查询/格式转换** → 写 Skill（如 `doc-conversion`）
- **代码审查/安全分析** → 用 Agent（独立上下文，不污染主对话）
- **多步工作流** → Command 编排 Agent + Skill（如 `/rpi:research`）

## 相关页面

- [[agent-roles|多角色协作体系]]
- [[three-agent-model|三Agent协作模型]]
