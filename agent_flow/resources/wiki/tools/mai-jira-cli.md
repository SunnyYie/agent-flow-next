---
name: mai-jira-cli
type: tool
module: jira
status: active
confidence: 0.98
created: 2026-04-27
last_validated: 2026-04-30
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

## 认证策略（Cookie 优先）

1. 默认先复用本地现有会话（cookie/session），先执行 `jira auth status` 验证。
2. 若 `jira auth status` 已显示 `Authenticated: Active`，禁止再次执行 `jira auth login`。
3. 仅在会话失效且用户确认后，才允许执行 `jira auth login`（可能触发浏览器登录）。
4. 如果有 cookie 但状态异常，优先排查本地配置/环境变量，再考虑重新登录。

### 认证过期后重新登录

`jira auth login` 是交互式命令，会提示选择浏览器类型。Agent 必须用管道输入：

```bash
# Agent 模式（管道输入，避免交互 prompt）
echo "chrome" | jira auth login

# 检查当前认证状态
jira auth status
# 输出: Authenticated: Expired / Active
```

**Why**: `jira auth login` 使用 Typer prompt 等待用户输入浏览器类型，Agent 不用管道会卡住。

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
5. 流转父单到开发中（不能跨步，需逐步流转）：
```bash
# 先查看当前可用流转
jira issue transitions MPR-父单号

# 典型路径：开始 → 排期中 → 开发中
jira issue transition MPR-父单号 --id 291  # 直接评审通过 → 排期中
jira issue transition MPR-父单号 --id 261 --field customfield_11154=否  # 完成排期 → 开发中
```
6. 流转子任务到开发中（注意隐藏必填字段）：
```bash
jira issue transition MPR-子任务号 --id 81 \
  --field customfield_11122=技术方案描述 \
  --field customfield_11315=无需评审 \
  --field customfield_11121=8 \
  --field customfield_10513=2026-04-30
```
7. 子任务提测（先查 ID，再补齐隐藏字段）：
```bash
# 每次先查，不能硬编码历史 ID
jira issue transitions MPR-子任务号

# 示例：本次 workflow 中提测 ID 为 91
jira issue transition MPR-子任务号 --id 91 \
  --field customfield_11123=1 \
  --field customfield_11124=通过 \
  --field customfield_11136="<CR链接>" \
  --field customfield_10531=lichen3 \
  --field customfield_10510="<开发分支>" \
  --field customfield_11308=灰度 \
  --field customfield_11310="自测环境选择依据"
```

## 关键踩坑

| 坑 | 现象 | 解决 |
|---|---|---|
| `--platform` 是 array 类型 | 值 "PC" 无效 | 用完整选项值（"PC Web"/"RN"/"Server"），先 discover 查允许值 |
| 用户名必须英文 | "未在系统中找到用户" | `--assignee sunyi` 而非 `--assignee 孙毅` |
| 子任务前置条件 | "需要创建研发子任务后才可以继续" | 先创建子任务，再流转父单到开发中 |
| 隐藏必填字段 | "XXX is required in this transition" | 预填所有 "may require" 字段（技术方案、计划上线时间等） |
| 不能跨步流转 | Transition ID not found | 先 `jira issue transitions` 查可用流转，逐步执行 |
| 提测 ID 不固定 | `Transition ID 161 not found` | 子任务提测前必须重新 `jira issue transitions` 获取当前 ID（例如 91） |
| 提测隐藏必填 | 报错要求 `实际开发工期/自测状态/CR地址/QA对接人/代码分支/自测环境` | 提测前预填这些字段，避免交互中断 |

## 关联信息建议

建议在父单和子任务都补充评论：
- 需求文档链接
- 代码分支
- 相关角色（默认 sunyi）

```bash
jira issue comment MPR-XXXXX -m "关联需求文档: ...\n关联代码分支: ref-company-circles\n相关角色默认: sunyi"
```
