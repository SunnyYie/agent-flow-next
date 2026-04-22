---
name: adr-decision-record
type: pattern
module: architecture
status: verified
confidence: 0.85
created: 2026-04-13
last_validated: 2026-04-13
tags: [architecture, decision, ADR, trade-off]
---

# 架构决策记录模式（ADR）

## 问题描述
架构决策往往只在口头讨论中做出，没有记录决策背景和理由。当团队成员变更或时间推移后，"为什么这样做"变得不可追溯。

## 解决方案
用 ADR（Architecture Decision Record）格式记录每个重要架构决策：

```markdown
# ADR-{编号}: {决策标题}

## 状态
提议 | 已接受 | 已废弃 | 被ADR-{编号}替代

## 背景
{驱动此决策的问题是什么？}

## 决策
{我们打算做什么改变？}

## 后果
{此改变带来的利弊？什么变得更容易/更难？}
```

## 关键原则
1. 记录 WHY 而非只记录 WHAT
2. 每个决策至少列2个可选方案并对比 trade-off
3. 明确标注决策状态（提议/已接受/已废弃）
4. 被替代的 ADR 保留不删除，标注"被ADR-XXX替代"

## 相关条目
- [[concepts/architecture-decision|架构决策概念]]
