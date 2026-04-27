---
name: jira-search-to-dev
version: 1.0.0
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

1. 认证检查：`jira auth status`
2. 搜索历史单：`jira issue search ...`
3. 判断是否复用；不可复用则新建父单（产品需求）
4. 创建子任务（platform=RN）
5. 流转父单到开发中
6. 流转子任务到开发中（开发预估工期=8）
7. 评论写入需求文档、分支、角色

## Output

- 父单 key
- 子任务 key
- 两者状态（均为开发中）
- 可追溯信息（文档/分支/角色）
