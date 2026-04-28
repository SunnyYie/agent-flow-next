---
name: claude-code-plugin-hooks
type: tool
module: plugin
status: active
confidence: 0.98
created: 2026-04-27
last_validated: 2026-04-27
tags: [plugin, hooks, claude-code, settings.local, project-scope]
---

# Claude Code 插件 Hook 接入规范

## 目标

确保插件启用后，Hook 注册在**项目级**而非全局，且运行流程严格跟随当前生效插件（effective plugins）。

## 关键约束

1. 插件 Hook 统一同步到项目目录：`.claude/settings.local.json`
2. 禁止把插件 Hook 写入全局 `~/.claude/` 或全局 AgentFlow 配置
3. Hook 注册采用“全量同步”而非增量加减：
   - 以当前 effective plugins 为准
   - 自动清理过期/stale 插件 Hook

## 实现方式（对齐 Claude Code 插件机制）

- 插件目录包含 `manifest.yaml`
- `manifest.yaml` 中声明 `hooks`（event + matcher + script path）
- 安装/启停/卸载后重建项目 hook 集合并写回 `.claude/settings.local.json`

## 验证命令

```bash
agent-flow plugin list
agent-flow plugin verify
```

`plugin verify` 应满足：
- missing hooks = 0
- stale hooks = 0

## 工作流插件示例

内置示例插件：`workflow-guard`
- `PostToolUse`：搜索证据追踪
- `PreToolUse`：先搜索再执行硬拦截
- `UserPromptSubmit`：反思总结提醒

用于验证“引入插件后流程按插件执行”。
