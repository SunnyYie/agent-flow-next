---
name: thinking-chain-guidelines
type: concept
module: workflow
status: verified
confidence: 0.9
created: 2026-04-13
updated: 2026-04-14
tags: [thinking, ReAct, reasoning, autonomous-learning, escalation, document-driven]
---

# 思维链准则（文档驱动与结构化思考）

> 约束级别：准则（建议），非铁律。将思维过程以文档形式输出和驱动，每个阶段产出文档，文档指导下一步执行。

## 核心原则：文档驱动

传统认知循环（THINK → PLAN → EXECUTE → VERIFY → REFLECT）容易流于形式：THINK 只在脑中完成无产出，拿到任务就动手执行跳过拆分，REFLECT 经验只写 Soul 没按维度封装到 Wiki。

**解决方案**：将思维过程以文档形式输出和驱动。

### 五阶段文档驱动流程

```
理解拆分(文档) → 计划确认(文档) → 逐个执行(记录) → 关键验收(报告) → 知识封装(wiki)
```

### Phase 1: 理解与拆分（产出分析文档）
1. 接收任务后不立即执行
2. 文档化理解：重述目标、拆分子任务表格、列不确定项、判断执行模式
3. 知识检索（不可跳过）：Skill → Soul → Wiki → WebSearch
4. 产出：`.agent-flow/state/current_phase.md`

### Phase 2: 计划确认（等待用户确认）
1. 将分析文档展示给用户
2. 用户未确认 → 禁止执行

### Phase 3: 文档驱动执行
1. 每个子任务：先读分析文档 → 查找 Skill → 执行 → 记录
2. 执行记录写入 `.agent-flow/memory/main/Memory.md`

### Phase 4: 关键验收
1. 标记 ⚠️ 的子任务必须双验收
2. 先搜索验收标准（Skill/Wiki/WebSearch），再验收

### Phase 5: 知识封装
| 知识类型 | 封装位置 | 条件 |
|----------|---------|------|
| 可复用操作流程 | `.agent-flow/skills/` | 流程3步以上，可重复 |
| 项目特定成功模式 | `.agent-flow/wiki/patterns/` | 项目内可复用 |
| 跨项目通用模式 | `~/.agent-flow/wiki/patterns/` | confidence >= 0.7，跨项目验证 |
| 踩坑记录 | `.agent-flow/wiki/pitfalls/` | 避免重蹈覆辙 |
| 核心经验 | `.agent-flow/memory/main/Soul.md` | 关键决策和经验 |

每个知识条目必须包含：规则/事实描述 + **Why**（原因/背景）+ **How to apply**（何时/如何应用）。

## 思考流程（全流程贯穿）

### 1. ReAct（推理-行动循环）
```
Reason：分析问题根因，形成假设
Act：基于假设采取最小行动验证
Observe：观察行动结果
迭代：2轮未解决 → 进入自主搜索
```

### 2. Plan-and-Resolve（分解-求解）
```
复杂问题先分解为子问题
每个子问题独立求解
整合子解为完整方案
```

### 3. Reflection（反思沉淀）
```
解决后反思：根因是什么？模式是什么？搜索策略是否有效？
产出写入对应文档（Wiki/Soul/Skills）
```

## 自主学习能力（5种工具并行）

| 工具 | 用途 | 命令/方式 |
|------|------|-----------|
| 本地技能搜索 | 查找项目内已有的技能和经验 | Read `.agent-flow/skills/` + `~/.agent-flow/skills/` |
| gh CLI搜索 | 搜索GitHub开源实现 | `gh search repos/code` |
| Web搜索 | 技术文档、博客、问答 | WebSearch工具 |
| 文档搜索 | 权威技术文档 | find-docs skill |
| 源码阅读 | 理解具体实现逻辑 | Read工具 + gh api获取文件内容 |

**搜索优先级**：先搜本地（skills/ + Soul.md），再搜外部（gh/Web/文档），最后升级。

## 升级规则

```
子Agent：ReAct 2轮 → 并行搜索（4种工具同时） → 仍未解决 → 报告Main Agent
Main Agent：ReAct 2轮 → 并行搜索（4种工具同时） → 仍未解决 → 询问用户（铁律3：边界澄清）
```

## 相关条目
- [[search-before-execute|patterns/workflow/search-before-execute]]
- [[agent-roles|concepts/agent-roles]]
