# Hermes Agent 参考（面向 agent_flow）

最后验证时间：2026-04-29

## 1. 本机全局安装与配置状态

已在本机完成：

- 安装目录：`~/.hermes/hermes-agent`
- 全局命令：`~/.local/bin/hermes`（已链接）
- 当前版本：`Hermes Agent v0.11.0 (2026.4.23)`
- 配置目录：`~/.hermes/`
- 配置文件：`~/.hermes/config.yaml`
- 密钥文件：`~/.hermes/.env`

你本机可直接执行：

```bash
hermes --version
hermes setup
hermes model
hermes config show
```

## 2. 核心能力清单

- 自进化技能系统：可在复杂任务后自动沉淀技能，并在使用中持续修补。
- 长期记忆：`MEMORY.md` + `USER.md`，支持跨会话用户画像。
- 历史会话检索：基于 SQLite FTS5 + LLM 摘要召回。
- 多平台入口：CLI + Telegram/Discord/Slack/WhatsApp/Signal（通过 gateway）。
- 工具调用与子代理：支持并行委派、脚本化工具链。
- 定时任务：内置 cron 调度。
- 多模型后端：OpenRouter/OpenAI/Nous Portal 等可切换。

## 3. 与当前项目的结合场景

### 场景A：将 agent_flow 的流程模式沉淀成 Hermes skills

适用：`jira-search-to-dev`、`search-before-execute` 这类稳定流程。

做法：

1. 在本项目跑完一次完整流程。
2. 将步骤模板化为 Hermes skill（输入、前置检查、输出格式）。
3. 存入 `~/.hermes/skills/`，让 Hermes 在后续项目中复用。

收益：减少重复提示词，提升流程一致性。

### 场景B：跨会话追踪需求上下文

适用：多天迭代同一个 Jira/需求。

做法：

1. 每轮结束写入关键决策到记忆。
2. 新会话先做 session search，再继续开发。

收益：降低上下文丢失，减少“重复解释历史”。

### 场景C：消息网关远程驱动开发流程

适用：不在电脑前时继续执行异步任务。

做法：

1. 本机/云端运行 `hermes gateway`。
2. 在 Telegram/Discord 触发固定流程技能（如“Jira 检索 -> 生成实现计划”）。

收益：把 agent_flow 流程变成可远程触发的自动化工作流。

## 4. 推荐最小配置（agent_flow）

建议先配置：

1. 一个主模型（例如 OpenRouter）。
2. 一个安全的工具集（限制高风险 shell 操作）。
3. 2~3 个项目流程技能（先从 Jira 相关开始）。

## 5. 常用命令

```bash
# 首次向导
hermes setup

# 选择/切换模型
hermes model

# 查看与修改配置
hermes config show
hermes config set model openrouter/<model>

# 启动 CLI
hermes

# 启动消息网关
hermes gateway setup
hermes gateway start

# 健康检查
hermes doctor
```

## 6. 官方资料

- 仓库：<https://github.com/NousResearch/hermes-agent>
- 文档：<https://hermes-agent.nousresearch.com/docs/>
- 快速安装：`curl -fsSL https://raw.githubusercontent.com/NousResearch/hermes-agent/main/scripts/install.sh | bash`
