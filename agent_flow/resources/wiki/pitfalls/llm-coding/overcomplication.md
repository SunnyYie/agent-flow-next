---
name: overcomplication
type: pitfall
module: llm-coding
status: deprecated
confidence: 0.9
created: 2026-04-13
last_validated: 2026-04-16
source: https://github.com/forrestchang/andrej-karpathy-skills
tags: [over-engineering, strategy-pattern, abstraction, karpathy]
redirect: concepts/karpathy-principles.md
---

# LLM 代码过度复杂化陷阱

> 详细内容见 [[karpathy-principles|concepts/karpathy-principles]] 原则 2: Simplicity First。

本文件独有的补充要点（karpathy-principles 中未展开的部分）：

## 危险性量化

- 更难理解（认知负荷增加）
- 引入更多 bug（代码越多 bug 越多）
- 耗时更长（实现+测试+审查）
- 更难测试（需要为不需要的功能写测试）
- **死代码的真正成本不在写它的时候，而在读它、维护它、重构它的时候**

## 检测方法

- **行数对比**：如果 50 行能搞定但你写了 200 行，需要简化
- **类数对比**：如果 1 个函数能搞定但你创建了 5 个类，需要简化

## 相关条目

- [[karpathy-principles|concepts/karpathy-principles]]（权威来源：原则 2）
