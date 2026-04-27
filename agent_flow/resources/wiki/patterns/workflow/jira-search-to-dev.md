---
name: jira-search-to-dev
type: pattern
module: workflow
status: active
confidence: 0.97
created: 2026-04-27
last_validated: 2026-04-27
tags: [workflow, jira, transition, traceability]
---

# Jira 从搜索到开发中流程

## 场景

当需求链接和代码分支已确定，需要快速完成 Jira 跟踪闭环：
`搜索 -> 定位/新建 -> 子任务 -> 流转开发中 -> 关联信息`。

## 流程

1. `jira auth status` 检查会话。
2. `jira issue search` 按关键词查历史单，避免重复建单。
3. 若无可复用单：新建父单（`产品需求`）。
4. 创建子任务（Web/RN 等端任务）。
5. 流转父单到 `开发中`（按项目流转链）。
6. 流转子任务到 `开发中`。
7. 添加评论，写入需求文档、分支、责任人。

## 默认参数建议

- 需求目标：`OKR相关`
- 端：`RN`
- 开发预估工期：`8`
- 需求描述：留空
- 角色：`sunyi`

## 验收标准

1. 父单状态为 `开发中`
2. 子任务状态为 `开发中`
3. 父子单都可追溯到需求文档链接与代码分支
