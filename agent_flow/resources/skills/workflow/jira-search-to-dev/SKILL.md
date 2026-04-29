---
name: jira-search-to-dev
version: 1.1.0
trigger: jira建单, jira流转, 需求入开发, 从搜索到开发中
confidence: 0.97
abstraction: workflow
created: 2026-04-27
updated: 2026-04-27
---

# Skill: Jira Search To Dev

## Purpose

标准化执行 Jira 的“搜索 -> 建单 -> 子任务 -> 流转开发中”流程，确保需求、分支、责任人可追溯。

## Defaults

1. 开发预估工期：`8`
2. 端：`RN`
3. 需求目标：`OKR相关`
4. 需求描述：不填写
5. 相关角色：`sunyi`

## Procedure

1. 前置阅读（强制）：
   - `.agent-flow/wiki/jira.md`（若存在）
   - `agent_flow/resources/wiki/tools/mai-jira-cli.md`
   - `agent_flow/resources/wiki/patterns/workflow/jira-search-to-dev.md`
2. 认证检查（Cookie 优先）：先执行 `jira auth status`，若已 `Authenticated: Active`，禁止再执行 `jira auth login`
3. 搜索历史单：`jira issue search ...`
4. 判断是否复用；不可复用则新建父单（产品需求）
5. 创建子任务（platform=RN）
6. 流转父单到开发中
7. 流转子任务到开发中（开发预估工期=8）
8. 评论写入需求文档、分支、角色
9. 字段判定：
   - 默认值字段按约定自动填充
   - 非默认/有歧义字段必须请求用户确认，禁止猜填
10. 写入标记（供 hook 审核）：
   - `.jira-context-ready`（已完成前置阅读）
   - 如存在非默认字段：`.jira-field-decision-confirmed`（已获用户确认）

## Output

- 父单 key
- 子任务 key
- 两者状态（均为开发中）
- 可追溯信息（文档/分支/角色）

## Rules

1. 禁止跳过前置阅读直接建单
2. 禁止为“需业务决策字段”填入随意值
3. 无法确定字段时，先提问确认，再继续流程
4. `jira-workflow-guard` 会硬阻断：无前置阅读、占位值、未确认的非默认字段
5. Jira 会话存在时必须复用 cookie/session，只有会话失效且用户确认后才允许登录

## 变更历史

- v1.1.0 (2026-04-27): 增加前置阅读强约束、字段判定规则与禁止随意填值要求
- v1.0.0 (2026-04-27): 初始版本
