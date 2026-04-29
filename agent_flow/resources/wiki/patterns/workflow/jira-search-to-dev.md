---
name: jira-search-to-dev
type: pattern
module: workflow
status: active
confidence: 0.97
created: 2026-04-27
last_validated: 2026-04-29
tags: [workflow, jira, transition, traceability]
---

# Jira 从搜索到开发中流程

## 场景

当需求链接和代码分支已确定，需要快速完成 Jira 跟踪闭环：
`搜索 -> 定位/新建 -> 子任务 -> 流转开发中 -> 关联信息`。

## 流程

1. 读取流程文档（`.agent-flow/wiki/jira.md`、`tools/mai-jira-cli.md`、`pitfalls/tools/jira-workflow-hidden-fields.md`）确认字段规则和踩坑。
2. `jira auth status` 检查会话。若过期：`echo "chrome" | jira auth login`。
3. `jira issue search` 按关键词查历史单，避免重复建单。
4. 若无可复用单：新建父单（`产品需求`）。
5. 创建子任务（注意：`--platform` 必须用完整选项值如 "PC Web"/"RN"，用户名必须英文）。
6. 流转父单到 `开发中`（**不能跨步**，需逐步流转。先 `jira issue transitions` 查可用流转，典型路径：开始→排期中→开发中）。
7. 流转子任务到 `开发中`（注意隐藏必填字段：技术方案、计划上线时间必须提供）。
8. 添加评论，写入需求文档、分支、责任人。
9. 对非默认或业务决策字段向用户确认，禁止猜填。

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
4. 默认字段与用户确认字段区分明确，无随意填值

## 常见阻断与解决

| 阻断信息 | 原因 | 解决 |
|---------|------|------|
| 需要创建研发子任务后才可以继续 | 父单无子任务 | 先创建子任务再流转 |
| XXX is required in this transition | 隐藏必填字段 | 预填所有 may require 字段（技术方案、计划上线时间） |
| 值 "PC" 无效 | --platform 是 array 类型 | 用完整选项值，先 discover 查看 |
| 未在系统中找到用户 | 用户名用了中文 | 必须用英文用户名 |
