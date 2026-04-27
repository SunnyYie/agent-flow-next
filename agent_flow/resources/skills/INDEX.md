---
title: "Skills 技能索引"
category: index
module: meta
agents: [main, coder, verifier]
scope: global
tags: [index, meta, skills]
confidence: 1.0
status: verified
created: 2026-04-16
---

# Skills 技能索引

> 按 **主题枢纽** 一键查找相关技能 -> Read ~/.agent-flow/skills/topics/{keyword}.md
> 按 **标签** 精确查找 -> Grep "{keyword}" ~/.agent-flow/skills/TAG-INDEX.md
> 兜底 **全量搜索** -> Grep "{keyword}" ~/.agent-flow/skills/

## Topic Hubs（主题枢纽）— 跨分类快速查找

> 按主题一键查找所有相关技能，无需逐个搜索 handler.md。

- [[workflow|topics/workflow]] — 任务流程控制（8个技能）
- [[agent-orchestration|topics/agent-orchestration]] — 多Agent编排（5个技能）
- [[knowledge|topics/knowledge]] — 知识管理与检索（5个技能）
- [[development|topics/development]] — 代码开发与质量（7个技能）
- [[git|topics/git]] — Git操作（2个技能）
- [[integration|topics/integration]] — 外部系统集成（5个技能）
- [[ai-optimization|topics/ai-optimization]] — AI/LLM优化（5个技能）
- [[documentation|topics/documentation]] — 文档处理（4个技能）
- [[python|topics/python]] — Python模式（3个技能）
- [[research|topics/research]] — 研究与发现（4个技能）

## Workflow（任务流程控制）

- [pre-flight-check](workflow/pre-flight-check/handler.md) — 任务入口强制检查（配置→知识检索→分析→计划→确认）
- [subtask-guard](workflow/subtask-guard/handler.md) — 子任务执行前强制搜索知识
- [phase-review](workflow/phase-review/handler.md) — 阶段完成后汇总与用户确认门控
- [task-complexity](workflow/task-complexity/handler.md) — 5维量化复杂度评估
- [acceptance-check](workflow/acceptance-check/handler.md) — 子任务双验收（Verifier + 主Agent）
- [self-questioning](workflow/self-questioning/handler.md) — VERIFY后REFLECT前自我质询
- [error-recovery](workflow/error-recovery/handler.md) — OODA循环系统化调试
- [evidence-collection](workflow/evidence-collection/handler.md) — 验收报告证据收集

## Agent-Orchestration（多Agent编排）

- [agent-orchestration](agent-orchestration/agent-orchestration/handler.md) — 多子Agent流水线编排（已合并至 orchestrator-worker）
- [main-agent-dispatch](agent-orchestration/main-agent-dispatch/handler.md) — 上下文隔离派发协议（含预算估算）
- [orchestrator-worker](agent-orchestration/orchestrator-worker/handler.md) — 编排者-工作者模式（多视角并行）
- [context-budget](agent-orchestration/context-budget/handler.md) — 上下文预算追踪（已合并至 main-agent-dispatch）
- [ai-context-management](agent-orchestration/ai-context-management/handler.md) — 多Agent间上下文传递策略

## Knowledge（知识管理与检索）

- [knowledge-search](knowledge/knowledge-search/handler.md) — 统一知识检索（本地→外部→工具发现）
- [critical-knowledge](knowledge/critical-knowledge/handler.md) — 重复踩坑自动晋升临界知识区
- [experience-promotion](knowledge/experience-promotion/handler.md) — 经验晋升到全局知识库
- [promotion-verify](knowledge/promotion-verify/handler.md) — 晋升内容多Agent验收
- [summary-verifier](knowledge/summary-verifier/handler.md) — 子Agent摘要准确性抽检

## Development（代码开发与质量）

- [code-implementation](development/code-implementation/handler.md) — TDD代码实现+安全自检
- [tdd-workflow](development/tdd-workflow/handler.md) — 红-绿-重构TDD工作流
- [testing-strategies](development/testing-strategies/handler.md) — 测试金字塔（单元/集成/E2E/模拟）
- [implementation-patterns](development/implementation-patterns/handler.md) — 扩展模式+Pydantic验证+序列化
- [security-checks](development/security-checks/handler.md) — 安全验证（输入/子进程/认证）
- [code-review](development/code-review/handler.md) — 四柱并行代码审查
- [architecture-design](development/architecture-design/handler.md) — 架构设计+技术选型+ADR

## Git（Git操作）

- [git-workflow](git/git-workflow/handler.md) — Git操作（分支保护+提交格式+worktree）
- [gitlab-mr-creation](git/gitlab-mr-creation/handler.md) — 自托管GitLab MR创建

## Integration（外部系统集成）

- [feishu-doc-access](integration/feishu-doc-access/handler.md) — 飞书文档/Wiki访问
- [mai-jira-cli](integration/mai-jira-cli/handler.md) — mai-jira-cli工具使用（安装/配置/认证/Python API）
- [jira-workflow](integration/jira-workflow/handler.md) — Jira需求完整生命周期
- [jira-quick-ops](integration/jira-quick-ops/handler.md) — Jira只读查询与轻量写入
- [jira-remotelink](integration/jira-remotelink/handler.md) — Jira远程链接管理

## AI-Optimization（AI/LLM优化）

- [prompt-engineering](ai-optimization/prompt-engineering/handler.md) — 三层提示词架构设计
- [prompt-caching-optimization](ai-optimization/prompt-caching-optimization/handler.md) — 提示词缓存优化与预热
- [claude-code-design](ai-optimization/claude-code-design/handler.md) — Agent/Skill设计+自进化机制
- [claude-code-configuration](ai-optimization/claude-code-configuration/handler.md) — Claude Code 7配置系统
- [workflow-design](ai-optimization/workflow-design/handler.md) — DAG工作流设计（容错+断点续跑）

## Documentation（文档处理）

- [doc-conversion](documentation/doc-conversion/handler.md) — 文档格式转换+需求规格说明书
- [content-filter](documentation/content-filter/handler.md) — 内容过滤/脱敏/去冗余
- [markitdown](documentation/markitdown/handler.md) — 文件转Markdown（PDF/DOCX/PPTX/XLSX）
- [requirement-decomposition](documentation/requirement-decomposition/handler.md) — 需求拆解+边界场景+代码影响分析

## Python（Python模式）

- [pydantic-patterns](python/pydantic-patterns/handler.md) — 双TypedDict/Pydantic模式+约束字段
- [python-async-patterns](python/python-async-patterns/handler.md) — 异步代码+信号量+重试+优雅关闭
- [yaml-configuration](python/yaml-configuration/handler.md) — YAML配置验证+Pydantic Schema

## Research（研究与发现）

- [source-code-research](research/source-code-research/handler.md) — GitHub开源实现搜索
- [web-research](research/web-research/handler.md) — 网络技术方案搜索
- [tool-precheck](research/tool-precheck/handler.md) — 关键工具使用前检查
- [mongodb-query](research/mongodb-query/handler.md) — MongoDB数据查询
