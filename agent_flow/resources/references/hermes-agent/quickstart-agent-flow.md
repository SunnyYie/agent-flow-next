# Hermes Agent + agent_flow 快速接入

## 目标

把 Hermes 作为“跨会话执行器”，复用 `agent_flow/resources/wiki` 的流程知识。

## 步骤

1. 初始化 Hermes：`hermes setup`
2. 绑定模型：`hermes model`
3. 在 Hermes 对话中引导其读取本项目 wiki/patterns
4. 把稳定流程沉淀为 skills（先做 Jira 链路）
5. 用 gateway 做远程触发（可选）

## 建议首批沉淀的技能

- `jira-search-to-dev`
- `search-before-execute`
- `implementation-plan-checklist`

## 验证标准

- 能在新会话中自动回忆上次需求上下文。
- 能通过固定技能模板输出一致的实现计划。
- 能在 CLI 与消息平台复用同一流程。
