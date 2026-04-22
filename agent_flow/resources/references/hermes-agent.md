# hermes-agent — Agent自主进化机制

> 来源: [NousResearch/hermes-agent](https://github.com/NousResearch/hermes-agent) | MIT | 自改进AI智能体

## 项目简介

Nous Research 的"自改进AI智能体"，核心是**闭环学习机制**——从经验中创建技能、使用中自我改进、周期性持久化知识、搜索历史对话、跨会话构建用户模型。支持多模型(OpenRouter 200+)、多平台(Telegram/Discord/CLI)、多终端(Docker/SSH/Modal)。

## 核心架构

```
run_agent.py (AIAgent类, tool-calling循环, 最多90轮)
├── agent/           — prompt_builder, memory_manager, context_engine
├── tools/           — 40+工具, registry.register()注册
├── plugins/memory/  — 可插拔记忆后端(Honcho/Mem0/Hindsight等8种)
└── skills/          — 25+领域技能包(YAML frontmatter + Markdown)
```

## 自主进化的四子系统闭环

### 1. 技能自创建与自改进 (`tools/skill_manager_tool.py`)
- `skill_manage` 工具：create/edit/patch/delete/write_file/remove_file
- **触发指令内嵌系统提示**：`SKILLS_GUIDANCE` — "完成复杂任务(5+工具调用)后、修复棘手错误后，自动保存为技能"
- **自改进**："使用技能时发现过时/不完整/错误，立即用patch更新"
- 技能存储 `~/.hermes/skills/`，YAML frontmatter元数据，安全扫描后写入

### 2. 持久化记忆与用户建模 (`tools/memory_tool.py`)
- 双文件记忆：`MEMORY.md`(Agent观察笔记) + `USER.md`(用户偏好画像)
- **冻结快照模式**：会话开始加载到系统提示，会话中写入仅更新磁盘不改提示，保持prefix cache稳定
- Honcho集成：跨会话辩证式用户建模，异步写入、背景预取

### 3. 跨会话经验搜索 (`tools/session_search_tool.py`)
- SQLite FTS5全文检索历史会话，Top N 相关会话
- 低成本模型(Gemini Flash)对匹配会话做聚焦摘要，避免污染主上下文
- 系统提示引导："用户提及过去对话时，先用session_search召回"

### 4. MemoryProvider生命周期钩子 (`agent/memory_provider.py`)
- `on_turn_start` → `on_pre_compress` → `on_session_end` → `on_delegation` → `on_memory_write`

## 关键设计模式

1. **Provider/Plugin ABC模式**：MemoryProvider、ContextEngine 均为抽象基类
2. **Progressive Disclosure**：技能三层递进 — 元数据列表 → 完整指令 → 关联文件
3. **Frozen Snapshot + Live State**：系统提示冻结、工具调用返回实时状态
4. **三层注入扫描**：记忆/上下文/技能均做正则+不可见Unicode安全检测

## 可借鉴要点

- **技能即程序性记忆**：将"如何做某类任务"编码为可检索、可更新的Markdown技能文件
- **系统提示内嵌进化指令**：`SKILLS_GUIDANCE`/`MEMORY_GUIDANCE` 直接写入system prompt，LLM自主决定何时创建/更新
- **冻结快照模式**：会话内记忆只写磁盘不改提示，实用的缓存策略
- **多后端记忆架构**：MemoryManager编排内置+外部provider，ABC统一生命周期
- **FTS5+LLM摘要的会话搜索**：低成本长期记忆检索
