---
title: "Agent Teams：多会话协作"
category: pattern
module: workflow
agents: [main, coder, verifier]
scope: global
tags: [agent-teams, multi-session, parallel, tmux, coordination]
confidence: 0.75
sources: [shanraisshan/claude-code-best-practice]
status: draft
created: 2026-04-14
updated: 2026-04-14
---

# Agent Teams：多会话协作

> 多个独立 Claude Code 会话并行工作，通过共享任务列表协调。

## 模式描述

Agent Teams 允许多个 Claude Code 实例在不同终端/工作树中并行工作，通过共享任务列表和接口契约协调，显著提升大型任务的处理速度。

## 前置条件

- 环境变量: `CLAUDE_CODE_EXPERIMENTAL_AGENT_TEAMS=1`
- 终端复用: tmux 或 iTerm2 分屏
- Git worktree: 每个 teammate 在独立 worktree 中工作

## 架构

```
Main Session (Supervisor)
├── Teammate 1: Workflow Developer (worktree: feature/workflow)
├── Teammate 2: Runtime Developer  (worktree: feature/runtime)
└── Teammate 3: Skill Developer    (worktree: feature/skill)
    ↕ 通过共享任务列表协调
    ↕ 仅在接口层同步
```

## Team Prompt 模板

```markdown
你是 Agent Team 的成员 [角色名]。

## 职责
[具体职责描述]

## 共享数据契约
- 输入: [从其他 teammate 接收什么]
- 输出: [向其他 teammate 提供什么]
- 接口: [文件路径/API 格式]

## 协调规则
1. 只在接口层与其他 teammate 同步
2. 不要修改其他 teammate 负责的文件
3. 完成任务后更新共享任务列表
4. 遇到阻塞时标记任务状态为 blocked

## 工作目录
[worktree 路径]
```

## 适用场景

| 场景 | Team 配置 | 预期加速 |
|------|----------|---------|
| 大型功能开发 | 3 teammates 按架构层分工 | 2-3x |
| 代码迁移 | N teammates 按模块分工 | Nx |
| 多方案评估 | 3 teammates 各实现一种方案 | 并行评估 |
| 前后端并行 | 2 teammates 前端+后端 | 2x |

## 与 AgentFlow 多Agent并行的区别

| 维度 | AgentFlow 多Agent | Agent Teams |
|------|-------------------|-------------|
| 上下文 | 共享主对话上下文 | 独立上下文窗口 |
| 文件系统 | 共享工作目录 | 独立 worktree |
| 协调方式 | Main Agent 编排 | 共享任务列表 |
| 适合 | 互补性任务 | 独立性任务 |
| 冲突风险 | 低（Main 控制） | 需接口契约防止 |

## 实践建议

1. **每个 teammate 有独立 worktree** — 避免文件冲突
2. **只定义接口，不定义实现** — 让 teammate 自主决策
3. **定期同步共享任务列表** — 防止重复工作
4. **合并前做集成测试** — 独立开发的代码可能不兼容
5. **从 2-3 个 teammate 开始** — 不要一次启动太多

## 相关页面

- [[agent-resolution-order|Agent调度优先级]]
- [[rpi-workflow|RPI 工作流]]
- [[cross-model-workflow|跨模型工作流]]
