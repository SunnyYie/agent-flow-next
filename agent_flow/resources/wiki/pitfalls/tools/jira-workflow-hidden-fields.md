---
name: jira-workflow-hidden-fields
type: pitfall
module: tools
status: active
confidence: 0.9
created: 2026-04-29
last_validated: 2026-04-29
tags: [jira, workflow, hidden-fields, validation, subtask]
---

# Jira 工作流隐藏字段与流转前置条件

## 问题描述

Jira 工作流中有两类隐藏要求会导致流转失败：
1. Jira 标记为 optional 但工作流验证器实际要求的字段
2. 流转前置条件（如必须先创建子任务）

这些信息不会在 `jira issue transitions` 的 Fields 列中明确标注，只能通过执行后报错发现。

## 踩坑记录

### 1. 父 Issue 流转到"开发中"必须先有子任务

```
! Jira 工作流校验未通过：
  - 需要创建研发子任务后才可以继续（更多-创建子任务）
```

**Why**: MPR 项目的 Jira 工作流配置了验证器，要求父 Issue 至少有一个子任务才能流转到"开发中"。

**How to apply**: 流转父 Issue 前，先 `jira issue subtask PARENT-KEY` 创建子任务。

### 2. 子任务"开始开发"流转的隐藏必填字段

`jira issue transitions` 显示 Fields 为 "4 fields (may require)"，但执行时验证器要求：

| 字段 ID | 名称 | 类型 | 实际要求 |
|---------|------|------|---------|
| customfield_11122 | 技术方案 | string | 工作流验证器必填 |
| customfield_10513 | 计划上线时间 | date | 工作流验证器必填 |
| customfield_11315 | 技术方案评审 | option | 可选（建议填"无需评审"） |
| customfield_11121 | 开发预估工期 | number | 可选 |

**Why**: Jira 的字段标记（required/optional）与工作流验证器的实际检查不一致。`jira issue transitions` 只显示 Jira 元数据标记，不反映验证器逻辑。

**How to apply**: 预填所有 "may require" 字段，即使 Jira 标记为 optional。典型命令：

```bash
jira issue transition SUBTASK-KEY --id 81 \
  --field "customfield_11122=技术方案描述" \
  --field "customfield_11315=无需评审" \
  --field "customfield_11121=0.5" \
  --field "customfield_10513=2026-04-30"
```

### 3. 状态不能跨步流转

从"开始"状态不能直接跳到"开发中"，必须按路径逐步流转：

```
开始 → 排期中（直接评审通过）→ 开发中（完成排期）
```

**Why**: Jira 工作流定义了线性状态路径，每个状态只有特定的可用流转。

**How to apply**: 每次 `jira issue transitions` 查看当前可用流转，按路径逐步执行。

### 4. 子任务 --platform 字段是 array 类型

```bash
# 错误
--platform PC
# 报错：值 "PC"无效

# 正确
--platform "PC Web"
```

**Why**: `customfield_10013`（端）是 Jira 的多选 array 类型，值必须是预定义选项的完整名称，不支持模糊匹配或简称。

**How to apply**: 创建子任务前，先用 `jira issue discover --create --project PROJECT --type "子任务"` 查看字段允许值。常用值：`iOS`、`Android`、`Harmony`、`PC Web`、`Server`、`RN`。

### 5. 用户名参数必须用英文

```bash
# 错误
--assignee 孙毅 --rd-owner 孙毅 --pd-owner 刘珊珊
# 报错：未在系统中找到用户 "孙毅"

# 正确
--assignee sunyi --rd-owner sunyi --pd-owner liushanshan
```

**Why**: Jira 的 user 类型字段需要英文用户名（username/key），不是显示名称。

**How to apply**: 通过 `jira issue view` 查看已有 Issue 的 assignee 获取用户名格式。

### 6. 认证过期后 auth login 是交互式命令

```bash
# 交互式（会卡住等待输入）
jira auth login

# Agent 模式（管道输入，避免交互 prompt）
echo "chrome" | jira auth login
```

**Why**: `jira auth login` 使用 Typer prompt 等待用户输入浏览器类型，Agent 必须用管道输入避免卡住。
