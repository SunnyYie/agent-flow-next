---
name: tool-precheck
version: 1.0.0
trigger: 工具使用前检查, tool precheck, lark-cli, glab, gh, docker
confidence: 1.0
abstraction: universal
created: 2026-04-14
---

# Skill: Tool Precheck（工具使用前置检查）

> **在外部 CLI 工具执行前，自动检查临界知识区并提醒关键用法**。防止"知道有文档但不读"的重复犯错模式。

## Trigger

- 当 Agent 即将使用 `~/.agent-flow/config.yaml` 中 `critical_tools` 列表里的工具时
- 由 tool-precheck-guard.py hook 自动触发提醒
- 也可在 pre-flight-check Step 4 中主动调用

## Procedure

### Step 1: 提取工具名称

从即将执行的命令中提取工具名称：

```text
lark-cli wiki spaces get_node ... → 工具名: lark-cli
glab mr create ...               → 工具名: glab
gh pr create ...                 → 工具名: gh
docker run ...                   → 工具名: docker
```

### Step 2: 检查临界知识区

1. 读取 `souls/main.md` 中的 `## 临界知识区` 部分
2. 查找 `### TOOL: {工具名}` 条目
3. 如找到 → 显示要点摘要，提醒 Agent 注意

### Step 3: 检查 Wiki 已读标记

1. 检查 `.agent-flow/state/.tool-wiki-read` 中是否有该工具的"已读"标记
2. 有标记 → 静默放行（Agent 已读过相关 wiki）
3. 无标记 → 建议先读 wiki，然后创建标记

### Step 4: 读取完整 Wiki 条目（如需要）

如果临界知识区的摘要不够详细：

1. 从临界知识区条目中获取 wiki 路径
2. 读取 wiki 文件获取完整用法说明
3. 创建 `.tool-wiki-read` 标记，避免重复提醒

## 标记文件格式

`.agent-flow/state/.tool-wiki-read`：

```
lark-cli|2026-04-14T10:30:00|pitfalls/feishu/lark-cli-params.md
glab|2026-04-14T11:00:00|patterns/gitlab/self-hosted-gitlab-auth.md
```

格式：`{工具名}|{ISO8601时间}|{wiki路径}`

## 与 Hook 的协作

tool-precheck-guard.py 是 PreToolUse hook，在 Bash 命令执行前自动触发：

1. Hook 检测到 Bash 命令包含 critical_tools 中的工具名
2. Hook 检查 `.tool-wiki-read` 标记
3. 无标记 → Hook 输出提醒信息（不阻断，exit 0）
4. 有标记 → 静默放行

本 skill 是 hook 的补充，提供更详细的检查流程和 wiki 读取能力。

## Rules

- **不阻断执行**：tool-precheck 是提醒机制，不是阻断机制
- **标记有时效**：`.tool-wiki-read` 标记有效期 24 小时，过期需重新读取
- **只监控配置的工具**：只检查 `config.yaml` 中 `critical_tools` 列表的工具
- **临界知识区优先**：先查临界知识区（已加载），再查 wiki（需读取）

## 变更历史

- v1.0.0 (2026-04-14): 初始版本，工具前置检查 + wiki 已读标记 + hook 协作
