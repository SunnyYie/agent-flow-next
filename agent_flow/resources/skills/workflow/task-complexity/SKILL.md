---
name: task-complexity
version: 1.0.0
trigger: 任务复杂度评估, complexity assessment, 新任务分级
confidence: 1.0
abstraction: universal
created: 2026-04-14
status: integrated
integrated_into: workflow/pre-flight-check/handler.md
---

# Skill: Task Complexity Assessment（任务复杂度量化评估）

> **量化驱动的复杂度分级**。替代主观 S/M/X 判断，通过 5 维评分矩阵得出客观复杂度等级，决定后续流程强度。
>
> **注意**：本 Skill 已整合到 `pre-flight-check` Step 2 中。本文档保留 5 维评分矩阵的完整定义作为参考。

## Trigger

在 pre-flight-check Step 2 中自动调用。每个新任务开始时必须执行一次。

## Procedure

### Step 1: 5 维量化评分

对任务逐维评估，每维 0-2 分：

| 维度 | 0 分 | 1 分 | 2 分 |
|------|------|------|------|
| **范围**（影响文件数） | 单文件、<50 行变更 | 2-5 文件或 50-200 行 | 6+ 文件或 200+ 行 |
| **跨模块** | 同目录/模块内 | 2 模块，接口清晰 | 3+ 模块或未知接口 |
| **新颖度** | Soul.md/Skills 有精确匹配 | 部分匹配需适配 | 无匹配需调研 |
| **风险** | 无数据/安全影响 | 轻微配置/数据变更 | 安全、数据丢失或不可逆操作 |
| **外部依赖** | 仅标准工具（git, npm 等） | 1 个外部 API/工具 | 多个外部工具或未知 API |

**评分要点**：
- 范围：先估算文件数和行数再打分，不要凭感觉
- 跨模块：检查是否涉及不同目录层级、不同技术栈（前端/后端/DevOps）
- 新颖度：搜索 Soul.md 和 Skills 后再判定，"没搜就说无匹配" = 无效评分
- 风险：考虑数据变更、安全影响、可逆性
- 外部依赖：计算需要使用的外部 API/CLI 工具数量

### Step 2: 计算总分与分级

```
总分 = 范围 + 跨模块 + 新颖度 + 风险 + 外部依赖

0-3  → Simple  (快速路径)
4-6  → Medium  (标准路径)
7-10 → Complex (严格路径)
```

### Step 3: 写入复杂度标记

将评估结果写入 `.agent-flow/state/.complexity-level`：

```
level={simple|medium|complex}
scores=范围:{0-2},跨模块:{0-2},新颖度:{0-2},风险:{0-2},外部依赖:{0-2}
total={0-10}
timestamp={ISO8601}
```

同时更新 `current_phase.md` 中的复杂度字段。

### Step 4: 按分级选择工作流

根据分级执行对应的行为配置：

| 行为 | Simple (快速路径) | Medium (标准路径) | Complex (严格路径) |
|------|-------------------|-------------------|---------------------|
| **知识搜索** | 2 步（全局 Skills + Wiki） | 5 步全做 | 5 步 + 强制 WebSearch |
| **GO/NO-GO** | 无，用户确认即可 | Plan 阶段门控 | 每阶段门控 |
| **双验收** | 自审即可 | 关键子任务双验收 | 改动量≥50行或3+文件时双验收 |
| **文档化** | 分析写入 Memory.md 即可 | 分析+计划都写入 | 分析+计划+每阶段记录 |
| **多Agent并行** | 不需要 | 验收时双Agent | 执行+验收都多Agent |
| **Hook 行为** | 搜索标记 30min，首次软提醒 | 当前行为(10min，硬阻断) | 5min，硬阻断+每子任务搜 |
| **模型选择** | 默认（当前模型） | 默认 | Research+Plan 用 Opus，Implement 用 Sonnet |

**Simple 快速路径详细规则**：
- 知识搜索只做 2 步：`Grep "{关键词}" ~/.agent-flow/skills/` + `Grep "{关键词}" ~/.agent-flow/wiki/`
- 无需 GO/NO-GO 评审，用户确认"OK"即可开始
- 自审即可，无需启动 Verifier Agent
- 分析文档写入 Memory.md 即可，无需创建完整执行计划
- 思维链 hook 宽松模式：搜索标记有效期 30min，首次违规仅输出提醒不阻断

**Complex 严格路径详细规则**：
- 知识搜索 5 步全做 + 强制 `WebSearch "{任务关键词} best practice"`
- 每阶段（Research/Plan/Implement）都需要 GO/NO-GO 门控
- 所有子任务必须双验收（Verifier Agent + Main Agent）
- 每阶段产出的文档必须写入文件
- 思维链 hook 严格模式：搜索标记有效期 5min，每子任务必须独立搜索
- Research 和 Plan 阶段建议使用更强模型

## Rules

- **量化优先**：每维评分必须有依据（文件数、模块数、搜索结果），禁止凭感觉打分
- **搜索先行**：新颖度评分前必须先搜索 Soul.md 和 Skills，"未搜即判" = 违规
- **标记必写**：评估结果必须写入 `.complexity-level` 文件，hooks 依赖此文件
- **任务结束清理**：任务完成后删除 `.complexity-level` 文件，防止残留影响下次评估
- **默认 Medium**：如 `.complexity-level` 文件不存在或格式错误，hooks 默认按 Medium 处理
- **不可跳过**：复杂度评估是 pre-flight-check 的必要步骤，不可跳过

## 变更历史

- v1.0.0 (2026-04-14): 初始版本，5 维量化评分矩阵 + 3 级行为差异
