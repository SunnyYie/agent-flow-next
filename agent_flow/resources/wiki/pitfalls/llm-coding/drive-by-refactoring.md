---
name: drive-by-refactoring
type: pitfall
module: llm-coding
status: deprecated
confidence: 0.9
created: 2026-04-13
last_validated: 2026-04-16
source: https://github.com/forrestchang/andrej-karpathy-skills
tags: [refactoring, style-drift, diff-noise, karpathy]
redirect: concepts/karpathy-principles.md
---

# 顺带重构陷阱

> 详细内容见 [[karpathy-principles|concepts/karpathy-principles]] 原则 3: Surgical Changes。

本文件独有的补充要点（karpathy-principles 中未展开的部分）：

## 为什么危险

- **diff 噪音**：reviewer 需要检查更多行，容易遗漏真正的变更
- **意外破坏**：风格修改可能改变行为（如布尔表达式重写）
- **责任模糊**：如果"顺便"的修改引入 bug，是谁的责任？
- **版本控制噪音**：git blame 追踪到不相关的提交
- **冲突放大**：无关修改增加了合并冲突的可能性

## 相关条目

- [[karpathy-principles|concepts/karpathy-principles]]（权威来源：原则 3）
