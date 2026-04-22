---
name: agent-roles
type: concept
module: architecture
status: verified
confidence: 0.95
created: 2026-04-13
updated: 2026-04-14
tags: [agent, roles, orchestration, multi-agent]
---

# AgentFlow 多角色协作体系

> 每个角色有独立的 Soul（性格+经验），详细定义见 `~/.agent-flow/souls/`。

## 角色速查

| 角色 | Soul | 职责 | 启动时机 |
|------|------|------|---------|
| Main | main.md | 任务监督与验收 | 始终在线 |
| Planner | planner.md | 任务分解与规划 | 需要规划时 |
| Coder | coder.md | 代码实现与测试 | 编码任务 |
| Writer | writer.md | 文档撰写与转换 | 文档任务 |
| Researcher | researcher.md | 信息调研与方案分析 | 调研任务 |
| Verifier | verifier.md | 质量验收与审查 | 验收检查点 |
| Architect | architect.md | 架构设计与决策 | 架构任务 |

## 角色选择策略
- 需求模糊 → Planner 澄清
- 需要编码 → Coder 实现
- 需要文档 → Writer 撰写
- 需要调研 → Researcher 搜索
- 需要验收 → Verifier 审查
- 需要架构 → Architect 设计

## 协作规则
详见 [[three-agent-model|三Agent协作模型]] — Main Agent 启停子 Agent，Executor/Verifier 互斥运行，用完即关。
