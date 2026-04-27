---
name: agent-roles
type: concept
module: architecture
status: verified
confidence: 0.95
created: 2026-04-13
updated: 2026-04-27
tags: [agent, roles, orchestration, multi-agent]
---

# AgentFlow 多角色协作体系

> 每个角色有独立的 Soul（性格+经验），详细定义见 `~/.agent-flow/souls/`。

## 角色速查

| 角色 | Soul | 职责 | 启动时机 |
|------|------|------|---------|
| Supervisor | main.md | 监督分支/Jira流转/推送与MR创建 | 始终在线 |
| Developer | coder.md | 阅读需求、拆解任务、关联代码、开发与测试 | 开发阶段 |
| Acceptance | verifier.md | 独立验收：复核需求/任务/代码并给出PASS/FAIL | 验收阶段 |

## 角色选择策略
- 需要流程治理与发布收口 → Supervisor
- 需要需求解析与开发落地 → Developer
- 需要独立质量判定与验收门禁 → Acceptance

## 协作规则
详见 [[three-agent-model|三Agent协作模型]]：Supervisor 只编排与门禁，Developer 负责实现与测试，Acceptance 独立验收，通过后才允许推送与创建 MR。
