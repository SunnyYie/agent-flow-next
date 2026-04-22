# Claude Code Best Practice 参考项目

> 来源：https://github.com/shanraisshan/claude-code-best-practice

## 项目概述

shanraisshan/claude-code-best-practice 是 Claude Code 最佳实践的参考实现项目，提供了完整的 Command → Agent → Skill 架构模式、自进化 Agent 机制、漂移检测系统和 Hooks 音频通知系统。

## 核心架构：Command → Agent → Skill

```
用户输入 /command
    ↓
Command（编排入口）
    ├── 解析用户意图
    ├── 协调多步流程
    └── 启动 Agent
            ↓
        Agent（自主执行者）
            ├── 预加载 Skills（知识注入）
            ├── 受限工具集（安全边界）
            └── 独立上下文（context: fork）
                    ↓
                Skill（知识单元）
                    ├── SKILL.md（主定义）
                    ├── examples.md（示例）
                    └── reference.md（参考）
```

## 配置面全景

### CLAUDE.md
- 项目级指令文件，对话开始时自动加载
- 支持全局/项目/子目录三层优先级
- 定义触发规则、铁律、开发流程

### settings.json
- 权限配置（allow/deny/ask）
- 27 个 Hook 事件配置
- MCP 服务器自动审批
- 环境变量注入
- 三层合并（local > shared > default）

### Commands（13 字段 frontmatter）
- 用户自定义斜杠命令
- 支持 model/effort/context/hooks
- 编排入口，不直接执行

### Agents（16 字段 frontmatter）
- 自主执行单元
- 支持 tools/disallowedTools/skills/hooks
- 5 种设计模式：角色专用、自进化、研究代理、轻量、漂移检测

### Skills（13 字段 frontmatter）
- 可复用知识包
- 两种模式：预加载（Agent 注入）和调用（用户触发）
- 5 种设计模式：知识注入、过程执行、工具授权、轻量代理、上下文隔离

### Hooks（27 事件）
- 4 种类型：command/prompt/agent/http
- 支持异步、超时、一次性、条件匹配
- 可全局配置或 Agent 限定

### Rules
- glob 模式匹配自动激活
- 编码标准、文档规范

## 关键设计模式

### 1. 自进化 Agent
Agent 执行后更新自身 Skills，形成闭环学习。通过 prompt 内嵌自进化指令或 Stop Hook 触发。

### 2. 漂移检测系统
五维度（Commands/Settings/Skills/Subagents/Concepts）监控外部文档变化，标记 NEW/RECURRING/RESOLVED 状态。

### 3. 音频通知系统
32 个音频文件夹，Python 跨平台播放器，配置驱动的 Hook 开关。

### 4. Agent Memory
`.claude/agent-memory/` 目录持久化 Agent 知识，前 200 行注入系统提示词。

### 5. 角色委托规则
通过 Rules 的 glob 匹配，将特定文件类型的操作自动委托给专用 Agent。

## 数据统计

| 维度 | 数量 |
|------|------|
| Agent frontmatter 字段 | 16 |
| Skill frontmatter 字段 | 13 |
| Command frontmatter 字段 | 13 |
| 内置命令 | 68 |
| 内置 Agent | 5 |
| 内置 Skill | 5 |
| Hook 事件 | 27 |
| Settings 配置项 | 60+ |

## 提取的技能文档

本项目从 claude-code-best-practice 中提取了以下技能文档：

| 技能文件 | 内容 |
|---------|------|
| claude_code_configuration.md | 七大配置面全景 + Command→Agent→Skill 架构 |
| claude_code_skill_design.md | SKILL.md frontmatter + 五种 Skill 设计模式 |
| claude_code_agent_design.md | Agent frontmatter + 五种 Agent 设计模式 |
| claude_code_hooks_system.md | 27 事件 + 4 种 Hook 类型 + 音频通知 |
| claude_code_self_evolution.md | 自进化 Agent + 漂移检测 + 组合模式 |

## 可借鉴的改进方向

1. **Skill frontmatter 元数据**：为 Skill 文件增加 description 和适用场景
2. **漂移检测**：监控设计文档与代码实现的一致性
3. **自进化机制**：Executor Agent 实时更新 Skills（不限于阶段总结）
4. **音频通知**：长时间开发任务的完成提示
5. **Agent Memory**：项目特定配置的持久化存储
6. **工具授权模式**：通过 Skill 的 allowed-tools 简化常用命令授权
