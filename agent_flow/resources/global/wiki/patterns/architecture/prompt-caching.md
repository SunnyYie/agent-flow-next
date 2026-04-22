---
name: prompt-caching
category: patterns
confidence: 0.9
sources:
  - claude-cookbooks/misc/prompt_caching.ipynb
  - Anthropic official docs
tags: [caching, performance, cost-optimization]
---

# Pattern: 提示词缓存优化

## 问题

Agent 系统中大量重复的上下文（系统提示词、知识库、工具定义）在每次 API 调用时被重新处理，导致高延迟和高成本。

## 解决方案

利用 Anthropic Prompt Caching API，将稳定的提示词前缀缓存起来，后续调用直接复用。

### 三层缓存架构

| 层级 | 内容 | 缓存策略 | 命中周期 |
|------|------|----------|----------|
| L1 系统提示词 | 角色定义、行为准则、规则 | 显式断点 `cache_control` | 跨会话 |
| L2 知识库 | Wiki、Skill handler | 按需加载 + 显式断点 | 任务级 |
| L3 对话上下文 | 历史消息、任务产物 | 自动缓存 | 对话内 |

### 缓存策略选择决策树

```
需要缓存什么？
├── 整个请求（系统提示词 + 对话）→ 自动缓存（cache_control 顶层参数）
├── 仅系统提示词 → 显式断点（system 块上 cache_control）
├── 多段不同稳定性内容 → 显式断点（最多 4 个）
└── 预判用户即将查询 → 投机缓存（1-token 预热请求）
```

### 关键参数

- **TTL**: 5 分钟（每次命中自动续期），1 小时 TTL 可选（2x 价格）
- **最小长度**: Sonnet 1024 tokens, Opus/Haiku 4,096 tokens
- **成本**: 写入 1.25x, 读取 0.1x 标准输入价格
- **断点上限**: 4 个显式 + 1 个自动

### 反模式

- 将任务相关内容放在提示词前缀（破坏缓存命中）
- 大文件内容内联到提示词中（应通过路径引用）
- 依赖跨会话缓存（TTL 仅 5 分钟）
- 忽略 cache_creation_input_tokens 指标（无法监控效果）

## 相关

- [投机缓存](speculative-caching.md)
- [编排者-工作者](orchestrator-workers.md)
- [AI 上下文管理](~/.agent-flow/skills/ai-context-management/handler.md)
