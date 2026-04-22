# agency-agents — Skill与Soul角色设计

> 来源: [msitarzewski/agency-agents](https://github.com/msitarzewski/agency-agents) | 60+专业化AI Agent角色

## 项目简介

AI Agent角色集合库，将"数字代理公司"(The Agency)拆解为60+专业化Agent角色，涵盖工程/设计/产品/营销/测试/财务/策略等16个部门。每个Agent以Markdown文件定义，安装到 `~/.claude/agents/` 作为System Prompt。核心理念：**每个Agent不是泛泛的提示词模板，而是拥有独特个性、专业能力和交付物的领域专家**。

## 核心架构 — NEXUS编排框架

七阶段流水线 + Quality Gate：
```
Phase 0 发现 → Phase 1 策略 → Phase 2 基础 → Phase 3 构建 → Phase 4 加固 → Phase 5 发布 → Phase 6 运营
```

三种部署模式：Full(12-24周)、Sprint(2-6周)、Micro(1-5天)

指挥链：Agents Orchestrator → Studio Producer / Project Shepherd → 各部门Agent

## Soul（灵魂/人格）设计

每个Agent文件通过以下结构定义"灵魂"：

1. **YAML Front Matter**：`name` / `description` / `color` / `emoji` / `vibe`（一句话气质描述）
2. **Identity & Memory 区块**：Role（角色）、Personality（性格特质）、Memory（记忆模式）、Experience（经验背景）
   - 例：AI Engineer — "data-driven, systematic, performance-focused, ethically-conscious"
   - 例：Code Reviewer — "constructive, thorough, educational, respectful"
3. **Critical Rules**：每个Agent的不可违反铁律
   - PM的"Lead with the problem, not the solution"
   - Reviewer的"Be specific, Explain why"
4. **Communication Style**：规定输出风格

## Skill（技能）设计

1. **Core Capabilities**：工具栈和框架清单
2. **Workflow Process**：带具体命令的分步工作流
3. **Technical Deliverables**：产出物模板（如PM的PRD模板含Problem Statement/Goals/Non-Goals/User Stories）
4. **Success Metrics**：量化成功标准

## 角色协作模式

**协调层** (`strategy/coordination/`)：
- `agent-activation-prompts.md`：激活Prompt模板（Phase + Task + Acceptance Criteria + Reference Docs）
- `handoff-templates.md`：7种标准化交接模板（标准交接/QA PASS/FAIL/升级报告/阶段门控/Sprint交接/事件交接）

**核心协作循环** — Dev↔QA Loop：
```
Developer实现 → Evidence Collector QA验证 → PASS(继续) / FAIL(反馈重试,最多3次) → 升级
```

**Workflow Architect**：桥梁角色，不做实现只设计"工作流树"，四维注册表（工作流/组件/用户旅程/状态）

## 可借鉴要点

- **Front Matter + 结构化Markdown** 的Agent定义模式：轻量、可读、版本可控
- **vibe一句话定位 + Critical Rules铁律**：快速传达Agent气质和边界
- **标准化Handoff协议**：7种交接模板解决多Agent协作的上下文丢失问题
- **Dev↔QA循环 + 3次重试上限 + 升级机制**：实用的质量保证模式
- **Agent激活Prompt模板**：上下文注入标准化，新Agent不"冷启动"
- **Workflow Registry四维视图**：按工作流/组件/用户旅程/状态交叉索引
