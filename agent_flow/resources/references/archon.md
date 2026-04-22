# Archon — AI 工作流引擎设计模式研究笔记

> 来源: [coleam00/Archon](https://github.com/coleam00/Archon) | MIT | v0.3.6 | Bun + TypeScript

## 项目概述

Archon 是一个开源 AI 编码工作流引擎。用 YAML 定义多步骤开发流程（规划、实现、验证、审查、PR），通过 DAG 执行器可靠调度 Claude Code / Codex 子进程。

**定位类比**：Dockerfiles 之于基础设施，GitHub Actions 之于 CI/CD，Archon 之于 AI 编码工作流。

**核心理念**：Archon 本身不是 AI，它是一个编排层——在隔离的 Git Worktree 中调度 AI 子进程，提供确定性的工作流结构、隔离、持久化和多平台路由。

## 核心架构

```
平台适配器（Web UI, CLI, Telegram, Slack, Discord, GitHub）
        │
        ▼
   编排器（消息路由 & 上下文管理）
        │
   ┌────┴────┐
   ▼         ▼
命令处理器  工作流执行器    AI 助手客户端
(Slash)    (YAML DAG)     (Claude / Codex)
   │         │
   └────┬────┘
        ▼
  SQLite / PostgreSQL（7 张表）
```

### 7 种节点类型

| 类型 | 字段 | 需要 AI？ | 说明 |
|------|------|----------|------|
| Command | `command: name` | 是 | 运行 `.archon/commands/name.md` 模板 |
| Prompt | `prompt: "..."` | 是 | 内联 AI 提示词 |
| Bash | `bash: "..."` | 否 | Shell 脚本，stdout = 输出 |
| Script | `script: "..."` | 否 | TypeScript/Python 脚本 |
| Loop | `loop: {...}` | 是 | 迭代执行直到完成条件 |
| Approval | `approval: {...}` | 否 | 暂停等待人工审核 |
| Cancel | `cancel: "reason"` | 否 | 终止工作流 |

### DAG 执行器

- 拓扑排序 → BFS 分层 → `Promise.allSettled` 同层并发
- 4 种触发规则：`all_success`、`one_success`、`none_failed_min_one_success`、`all_done`

### 关键特性

- **Git Worktree 隔离**：每个工作流运行独立 worktree，可并行 5 个修复
- **变量替换**：`$ARGUMENTS`、`$WORKFLOW_ID`、`$ARTIFACTS_DIR`、`$nodeId.output`
- **20 个内置工作流** + **37 个内置命令**
- **断点续跑**：自动检测失败运行，从上次完成节点恢复
- **多平台**：CLI、Web UI、Telegram、Slack、Discord、GitHub/GitLab Webhook

## 可借鉴的设计模式

### 模式1: DAG 工作流与条件路由

- 依赖图拓扑排序执行，4 种 trigger_rule 控制依赖满足策略
- `when` 条件 + `output_format` 结构化输出实现条件分支
- 示例：archon-fix-github-issue 的分类/修复/审查条件路由
- **详细技能**: `shared/skills/dag_workflow_design.md`

### 模式2: 循环节点的三种变体

- **信号循环**（`until: ALL_TASKS_COMPLETE`）：AI 自主迭代直到输出完成信号
- **交互循环**（`interactive: true`）：人在环路，每轮暂停等待用户输入
- **Bash 门控循环**（`until_bash: "..."`）：外部命令 exit 0 判定完成
- **Ralph Pattern**（`fresh_context: true`）：每轮新会话，通过产物文件传递状态
- **Fix-Iterate Pattern**（`context: shared`）：同一会话持续，保留推理链
- **详细技能**: `shared/skills/iterative_ai_refinement.md`

### 模式3: 并行审查 Agent 扇出/扇入

- 5 个专业审查 Agent：code-review、error-handling、test-coverage、comment-quality、docs-impact
- 同层并行执行 → synthesize 节点 fan-in 合并结果
- smart-pr-review：复杂度分类决定启用哪些审查 Agent
- **详细技能**: `shared/skills/parallel_review_pipeline.md`

### 模式4: 容错与断点续跑

- **FATAL/TRANSIENT 错误分类**：认证/权限/余额永不重试，超时/限流/503 指数退避重试
- **节点级重试**：`max_attempts` + `delay_ms` 翻倍 + `on_error: transient|all`
- **断点续跑**：记录已完成节点，恢复时跳过
- **详细技能**: `shared/skills/workflow_fault_tolerance.md`

### 模式5: AI 上下文管理

- **fresh vs shared context**：每次迭代新建会话 vs 继承上文
- **$ARTIFACTS_DIR 产物目录**：节点间通过文件传递状态
- **变量替换**：`$nodeId.output` 在节点间传递数据
- **详细技能**: `shared/skills/ai_context_management.md`

### 模式6: Hook 质量门控

- 23 种 SDK 钩子事件（PreToolUse, PostToolUse, SessionStart 等）
- 只读节点拒绝写入、编辑后强制类型检查
- Sandbox：OS 级文件系统/网络限制
- **注意**：SDK 实现细节，概念层与现有 `security_checks.md` 重叠，不单独提取为技能

### 模式7: 编排器-路由器-执行器三层分离

- **编排器**：消息路由 + 上下文管理 + 工作流选择
- **路由器**：4 级名称解析（精确 → 忽略大小写 → 后缀 → 子串）
- **执行器**：DAG 执行 + 隔离管理 + AI 子进程调度
- **详细技能**: `main/skills/workflow_architecture.md`

### 模式8: 环境泄露防护

- AI 子进程生成前扫描目标仓库中的敏感密钥
- 防止 API key/token 泄露到 AI 会话上下文
- **注意**：单点安全模式，适合作为 security_checks.md 条目而非独立技能

## 与本项目的关系

| 维度 | agent-workflow | Archon |
|------|---------------------------|--------|
| **实现语言** | Python (LangGraph) | TypeScript (Bun) |
| **工作流定义** | 编程式（Python 代码） | 声明式（YAML DAG） |
| **AI 后端** | Claude Code CLI 子进程 | Claude Agent SDK（进程内） |
| **隔离** | Git Worktree（per Agent） | Git Worktree（per 工作流运行） |
| **多 Agent 模型** | 6 个专业 Agent + 角色分工 | DAG 节点（可多 AI 步骤） |
| **状态管理** | TypedDict + LangGraph checkpoint | 文件 + SQLite |
| **记忆/进化** | Soul.md + Skills + ChromaDB（丰富） | Commands（Markdown 模板） |
| **审查循环** | 内置驳回循环（动态次数上限） | Approval + Loop 节点 |
| **认知模式** | 元认知、失败学习、多 Agent 审议 | 无 |
| **平台集成** | GitHub + GitLab（via CLI） | GitHub + GitLab + Slack + Discord + Telegram |

**互补要点**：
- Archon 的 DAG 声明式设计与 LangGraph 的编程式状态图互补——YAML 适合流程标准化，代码适合逻辑复杂化
- 并行审查 Agent 模式可直接借鉴到 Verifier 的多维度验收
- 循环节点的 fresh_context vs shared_context 决策可指导 Agent 上下文策略
- 容错模式（FATAL/TRANSIENT 分类）可增强 error_recovery.md

## 搜索策略

- **原始资料**：GitHub 仓库源码（`gh api repos/coleam00/Archon/contents/`）+ archon.diy 文档站
- **分析路径**：README → 工作流 YAML 示例（`.archon/workflows/defaults/`）→ DAG 执行器源码（`packages/workflows/src/dag-executor.ts`）→ 内置命令模板（`.archon/commands/defaults/`）
- **关键发现路径**：archon-comprehensive-pr-review 工作流（并行审查）→ 5 个 Agent 命令文件 → synthesize 命令 → 识别 fan-out/fan-in 模式
- **使用手册**：`documents/Archon使用手册.md`（36KB，16 章节，基于 v0.3.6 源码）
