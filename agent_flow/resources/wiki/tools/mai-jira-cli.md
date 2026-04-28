---
name: mai-jira-cli
type: tool
module: jira
status: active
confidence: 0.98
created: 2026-04-27
last_validated: 2026-04-27
tags: [jira, tool, sso, workflow]
---

# mai-jira-cli 工具参考

## 目标

用于私有 Jira（`https://jira.in.taou.com`）的需求搜索、建单、子任务创建与状态流转。

## 前置检查

```bash
jira auth status
jira issue transitions MPR-XXXXX
```

认证要求：`Authenticated: Active` 且 `Session verified`。

## 默认规则（团队约定）

1. 开发预估工期默认：`8`
2. 端默认：`RN`
3. 需求目标默认：`OKR相关`
4. 需求描述默认：不填写（留空）
5. 相关角色默认：`sunyi`

## 字段决策规则（新增）

1. 仅对“团队已约定默认值字段”自动填充。
2. 对业务含义不明确、存在多选项、影响排期/范围/责任归属的字段，必须先向用户确认。
3. 禁止为未知字段填入临时值或猜测值。

## Hook 硬约束（新增）

执行 `jira issue create/subtask/transition/comment/update` 时：

1. 必须先有 `.jira-context-ready`（已检索 Jira wiki/skill）。
2. 命令中若出现非默认 `customfield_xxx`，必须先有 `.jira-field-decision-confirmed`。
3. 命令中若出现占位值（如 `xxx/todo/tmp/随便/待定`），会被直接阻断。

## 标准流程（搜索文档 -> 操作 Jira）

1. 搜索需求：
```bash
jira issue search "text ~ \"找实习\" ORDER BY updated DESC" -n 10
```
2. 查看候选单详情：
```bash
jira issue view MPR-XXXXX
```
3. 新建父单（产品需求）：
```bash
jira issue create -p MPR -t 产品需求 -s "标题" \
  --field priority=Medium \
  --field customfield_11154=否 \
  --field customfield_11001=OKR相关 \
  --field customfield_11157="社区/同事圈" \
  --field customfield_11000="<需求文档链接>" \
  --field assignee=sunyi \
  --field customfield_11114=sunyi
```
4. 新建子任务：
```bash
jira issue subtask MPR-父单号 -s "[Web] 子任务标题" \
  -a sunyi --rd-owner sunyi --pd-owner sunyi --platform RN
```
5. 流转父单到开发中：
```bash
jira issue transition MPR-父单号 --id 311
jira issue transition MPR-父单号 --id 321
jira issue transition MPR-父单号 --id 261 --field customfield_11154=否
```
6. 流转子任务到开发中：
```bash
jira issue transition MPR-子任务号 --id 81 \
  --field customfield_11121=8 \
  --field customfield_11315=无需评审
```

## 关联信息建议

建议在父单和子任务都补充评论：
- 需求文档链接
- 代码分支
- 相关角色（默认 sunyi）

```bash
jira issue comment MPR-XXXXX -m "关联需求文档: ...\n关联代码分支: ref-company-circles\n相关角色默认: sunyi"
```
