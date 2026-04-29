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
updated: 2026-04-28
---

# Skills 技能索引

## Lookup Entry（检索入口）

- 项目级入口：`.agent-flow/skills/Index.md`
- 全局入口：`agent_flow/resources/skills/INDEX.md`
- 本机 Lark skills 目录：`/Users/sunyi/.agents/skills/`

## Topic Hubs（主题枢纽）

- `workflow` — 流程控制与验收
- `agent-orchestration` — 多 Agent 编排
- `knowledge` — 知识检索与晋升
- `development` — 开发与代码质量
- `documentation` — 文档处理
- `research` — 工具前置检查

## Keyword Quick Map（关键词速查）

- `飞书` `lark` `lark-cli` `feishu` `wiki token` `obj_token` `docs +search`:
  - `/Users/sunyi/.agents/skills/lark-shared/SKILL.md`
  - `/Users/sunyi/.agents/skills/lark-doc/SKILL.md`
- `飞书技术文档` `wiki tech doc` `生成技术文档` `写文档到飞书`:
  - [feishu-wiki-tech-doc](development/feishu-wiki-tech-doc/SKILL.md)
- `飞书需求链接` `本地优先检索` `wiki fallback` `websearch fallback`:
  - [knowledge-search](knowledge/knowledge-search/SKILL.md)
  - [pre-flight-check](workflow/pre-flight-check/SKILL.md)
- `日历` `会议` `空闲时间` `calendar`:
  - `/Users/sunyi/.agents/skills/lark-calendar/SKILL.md`
- `多维表格` `base` `bitable`:
  - `/Users/sunyi/.agents/skills/lark-base/SKILL.md`
- `电子表格` `sheets`:
  - `/Users/sunyi/.agents/skills/lark-sheets/SKILL.md`
- `通讯录` `员工` `部门`:
  - `/Users/sunyi/.agents/skills/lark-contact/SKILL.md`
- `邮件` `mail`:
  - `/Users/sunyi/.agents/skills/lark-mail/SKILL.md`
- `Jira` `需求单` `任务单`:
  - `/Users/sunyi/.agents/skills/lark-openapi-explorer/SKILL.md`
  - `agent_flow/resources/wiki/tools/mai-jira-cli.md`
  - [jira-search-to-dev](workflow/jira-search-to-dev/SKILL.md)
- `plugin` `插件` `hook注册` `settings.local.json` `plugin verify`:
  - `agent_flow/resources/wiki/tools/claude-code-plugin-hooks.md`
- `cdn` `上传图片` `批量上传图片` `assets/icons`:
  - [batch-upload-images-to-cdn](development/batch-upload-images-to-cdn/SKILL.md)
- `agent-flow初始化` `项目初始化` `agent-flow init` `.agent-flow`:
  - `agent_flow/resources/wiki/tools/project-init-agent-flow.md`
- `CLAUDE.md模板` `AGENTS.md模板` `项目协议模板`:
  - `agent_flow/resources/wiki/patterns/project/claude-template.md`
  - `agent_flow/resources/wiki/patterns/project/agents-template.md`
- `需求拆解` `前后端划分` `验收点`:
  - [requirement-decomposition](documentation/requirement-decomposition/SKILL.md)
- `UI需求` `功能需求` `前端需求列表` `project-structure模板`:
  - [requirement-decomposition](documentation/requirement-decomposition/SKILL.md)
  - `agent_flow/resources/wiki/patterns/requirement/frontend-requirement-list-template.md`
  - `agent_flow/resources/wiki/patterns/requirement/project-structure-template.md`
- `同事圈` `公司圈` `company circles` `ref-company-circles`:
  - [knowledge-search](knowledge/knowledge-search/SKILL.md)
  - [requirement-decomposition](documentation/requirement-decomposition/SKILL.md)

## Workflow（任务流程控制）

- [pre-flight-check](workflow/pre-flight-check/SKILL.md) — 任务入口检查
- [subtask-guard](workflow/subtask-guard/SKILL.md) — 子任务执行前搜索
- [phase-review](workflow/phase-review/SKILL.md) — 阶段总结与用户门控
- [acceptance-check](workflow/acceptance-check/SKILL.md) — 交付验收
- [jira-search-to-dev](workflow/jira-search-to-dev/SKILL.md) — Jira 搜索到开发中的建单与流转

## Agent-Orchestration（多 Agent 编排）

- [main-agent-dispatch](agent-orchestration/main-agent-dispatch/SKILL.md)
- [orchestrator-worker](agent-orchestration/orchestrator-worker/SKILL.md)

## Knowledge（知识管理与检索）

- [knowledge-search](knowledge/knowledge-search/SKILL.md)
- [critical-knowledge](knowledge/critical-knowledge/SKILL.md)

## Development（代码开发与质量）

- [code-implementation](development/code-implementation/SKILL.md)
- [batch-upload-images-to-cdn](development/batch-upload-images-to-cdn/SKILL.md)
- [feishu-wiki-tech-doc](development/feishu-wiki-tech-doc/SKILL.md) — 从分支代码生成飞书 Wiki 技术文档
- [tdd-workflow](development/tdd-workflow/SKILL.md)
- [implementation-patterns](development/implementation-patterns/SKILL.md)
- [security-checks](development/security-checks/SKILL.md)
- [code-review](development/code-review/SKILL.md)
- [architecture-design](development/architecture-design/SKILL.md)

## Documentation（文档处理）

- [doc-conversion](documentation/doc-conversion/SKILL.md)
- [content-filter](documentation/content-filter/SKILL.md)
- [requirement-decomposition](documentation/requirement-decomposition/SKILL.md)

## Research（研究与发现）

- [tool-precheck](knowledge/tool-precheck/SKILL.md)

> 注：`web-research` 与 `source-code-research` 已并入 [knowledge-search](knowledge/knowledge-search/SKILL.md)。
