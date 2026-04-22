---
title: "Claude Code 四层记忆系统"
category: concept
module: workflow
agents: [main, coder, writer, researcher]
scope: global
tags: [memory, claude-code, auto-memory, agent-memory, CLAUDE.md]
confidence: 0.9
sources: [shanraisshan/claude-code-best-practice]
status: verified
created: 2026-04-14
updated: 2026-04-14
---

# Claude Code 四层记忆系统

> 理解四种记忆的写入者、读取者和作用域，避免误用。

## 问题描述

Claude Code 有四种记忆机制，职责不同但容易混淆。选错机制会导致：
- 临时信息写入 CLAUDE.md → 每次启动都加载无用信息
- 关键指令只放 auto-memory → Agent 无法读取
- Agent 经验不共享 → 重复踩坑

## 四层记忆对比

| 系统 | 写入者 | 读取者 | 作用域 | 生命周期 |
|------|--------|--------|--------|----------|
| **CLAUDE.md** | 人工手动 | 主 Claude + 所有 Agent | 项目级 | 永久，手动维护 |
| **Auto-memory** | 主 Claude 自动 | 仅主 Claude | 每项目每用户 | 永久，自动管理 |
| **/memory** | 用户通过编辑器 | 仅主 Claude | 每项目每用户 | 永久，手动编辑 |
| **Agent memory** | Agent 自身 | 仅该 Agent | 可配置 | 永久，Agent 管理 |

## 各系统详解

### 1. CLAUDE.md（项目指令）

- **位置**: 项目根目录或 `~/.claude/CLAUDE.md`
- **加载**: 启动时立即加载（祖先目录）或延迟加载（子目录）
- **限制**: 建议不超过 200 行，超出会导致遵守率下降
- **适合**: 项目规则、技术栈、编码规范、禁止事项

### 2. Auto-memory（自动记忆）

- **位置**: `.claude/memory/` 项目级，`~/.claude/memory/` 全局
- **机制**: 主 Claude 自动判断何时保存
- **格式**: MEMORY.md 索引 + 独立文件，索引前 200 行注入系统提示
- **适合**: 用户偏好、项目上下文、跨会话经验

### 3. /memory（手动记忆）

- **位置**: 同 auto-memory
- **机制**: 用户显式触发编辑
- **适合**: 用户想精确控制的内容

### 4. Agent Memory（Agent 专属记忆）

- **位置**: 三种作用域
  - `user`: `~/.claude/agent-memory/`（跨项目）
  - `project`: `.claude/agent-memory/`（项目内）
  - `local`: `.claude/agent-memory-local/`（本地临时）
- **机制**: Agent 通过 memory frontmatter 字段声明
- **适合**: Agent 的领域知识、执行经验

## 选择决策

```
需要持久化信息：
├── 是项目规则/禁止项？ → CLAUDE.md
├── 是用户偏好/跨会话经验？ → Auto-memory 或 /memory
├── 是 Agent 的领域知识？ → Agent memory
└── 是仅本次会话临时信息？ → 不持久化，用 state/
```

## AgentFlow 记忆映射

在 AgentFlow 三层架构中：
- **Layer 1 (全局)**: `~/.agent-flow/memory/` ≈ Agent memory (user scope)
- **Layer 2 (项目)**: `.agent-flow/memory/` ≈ Agent memory (project scope)
- **Layer 3 (开发)**: `.dev-workflow/` 内的记忆配置

## 相关页面

- [[agent-roles|多角色协作体系]]
- [[wiki-management|Wiki知识库管理规范]]
