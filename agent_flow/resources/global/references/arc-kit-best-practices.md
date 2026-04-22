---
name: arc-kit-best-practices
description: ArcKit 企业架构治理工具包的最佳实践与设计模式，可借鉴到 AgentFlow
type: reference
originSessionId: 30f3cac0-f961-4027-9d6a-72ae879702b0
---

# ArcKit 最佳实践参考

> 来源: https://github.com/tractorjuice/arc-kit — Enterprise Architecture Governance Toolkit (v4.9.1, MIT)

## 1. 插件式命令架构

每个治理能力是一个独立 slash command，用 Markdown + YAML frontmatter 定义。Frontmatter 声明 description、effort level、argument hints 和 handoff 关系。

**借鉴点**: AgentFlow 的 Skill 体系可参考此模式——每个 Skill 用统一 frontmatter 声明元数据，而非纯自由文本。

## 2. 模板驱动文档生成

每个命令对应 `.arckit/templates/{name}-template.md`，定义输出文档结构（Document Control 14字段 + 领域特定章节）。用户可通过 `templates-custom/` 覆盖默认模板而不 fork。

**借鉴点**: AgentFlow 的 Wiki/Skill 模板可引入 override 机制——默认模板可刷新，用户自定义保留在单独目录。

## 3. 依赖结构矩阵 (DSM)

命令间依赖分 MANDATORY / RECOMMENDED / OPTIONAL 三级，形成有序工作流链：principles → stakeholders → risk/SOBC → requirements → data-model → research → procurement → design review → backlog → traceability。

**借鉴点**: AgentFlow 的 Skill 之间可增加显式依赖声明（M/R/O），形成可验证的前置条件检查链。

## 4. 自主研究 Agent 隔离

重型 web-research 命令委托给隔离的 agent 子进程（10个专项 agent），避免大量 WebSearch 结果污染主对话。Agent 定义包含 `maxTurns`、`effort`、`disallowedTools` 约束。

**借鉴点**: AgentFlow 的 main-agent-dispatch 协议已采用此模式，可进一步细化 agent 约束声明（如 disallowedTools）。

## 5. Hook 驱动自动化

五类 Hook 强制执行治理规则：

- **SessionStart**: 自动检测版本、扫描项目状态
- **UserPromptSubmit**: 注入项目上下文、检测密钥泄露、命令预处理
- **PreToolUse**: 自动修正文件名到 ARC-{ID}-{TYPE}-v{VERSION} 规范
- **Stop/StopFailure**: Session learner 捕获会话结果到 memory
- **PermissionRequest**: 自动授权 MCP 工具权限

**借鉴点**: AgentFlow 可参考其 Hook 体系设计，特别是文件命名自动修正、密钥检测、和 session-learner 自动沉淀。

## 6. 引用可追溯性

命令读取外部参考文档时，产出内联引用标记（如 `[PP-C1]`），源自文档缩写，配合结构化 External References 章节。形成从生成需求到源材料的可追溯链。

**借鉴点**: AgentFlow 的 Wiki 条目和 Skill 可引入类似引用标记体系，确保知识来源可追溯。

## 7. 需求 ID 分类法

五类需求唯一前缀：BR-xxx（业务）、FR-xxx（功能）、NFR-xxx（非功能，含子前缀如 NFR-P 性能、NFR-SEC 安全）、INT-xxx（集成）、DR-xxx（数据）。每条需求有 MoSCoW 优先级和干系人目标追溯。

**借鉴点**: 适用于 AgentFlow 项目中需要需求管理的场景。

## 8. 质量清单强制执行

10点通用质量清单（文档控制完整、无占位文本、分类正确、表格一致、标题层级正确）+ 每类型专项检查（如需求必须有唯一 ID、研究须含3年 TCO、风险须有可能性/影响/缓解）。

**借鉴点**: AgentFlow 的 VERIFY 阶段可引入类似的清单式验收，而非仅靠 Verifier agent 自由审查。

## 9. Handoff 声明

命令在 YAML frontmatter 中声明 `handoffs`，指定逻辑下一步及条件，形成显式工作流图引导用户完成架构生命周期。

**借鉴点**: AgentFlow Skill 可增加 handoff 声明，使工作流推荐更智能。

## 10. 多 AI 分发架构

单一 source-of-truth（Claude Code plugin），通过 `scripts/converter.py` 转换到 Gemini CLI、Copilot、Codex CLI、OpenCode CLI 等格式。添加新目标只需新增 `AGENT_CONFIG` 字典条目。

**借鉴点**: 如果 AgentFlow 需要跨 AI 工具分发，可参考此 config-driven converter 模式。

## 11. 文档 ID 命名规范

`ARC-{PROJECT_ID}-{TYPE}-{SEQUENCE?}-v{VERSION}`，TYPE 代码包括 PRIN, STKE, RISK, SOBC, REQ, DATA, RSCH, SOW, EVAL, ADR, DIAG, WARD, TRAC 等。

**借鉴点**: AgentFlow 产出物可参考此结构化命名规范。

## 12. keep-coding-instructions

长时运行命令设置此标记，使指令在 `/compact` 后仍保留，防止长任务中上下文丢失。

**借鉴点**: 适用于 AgentFlow 中长时间运行的 EXECUTE 阶段。

## 13. Wardley Mapping 深度集成

5个独立命令 + 1个 skill，含数学模型引用和验证 hook。

**借鉴点**: 特定领域方法论可通过 Skill 体系深度集成到 AgentFlow。

## 关键差异

ArcKit 是**领域特定**（企业架构，偏英国政府）且**命令驱动**（显式 `/arckit:*` 调用），AgentFlow 是**领域无关**且使用认知循环（THINK-PLAN-EXECUTE-VERIFY-REFLECT）。ArcKit 刻意选择命令而非自动触发，因为治理文档是重量级的，应仅按需生成。
