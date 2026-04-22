# Global Wiki 知识导航

## Topic Hubs（主题枢纽）— 跨分类快速查找

> 按主题一键查找所有相关知识，无需跨分类搜索。

- [[workflow|topics/workflow]] — 工作流（模式+踩坑+概念+决策，22篇）
- [[llm-coding|topics/llm-coding]] — LLM编程（踩坑+原则+退化，10篇）
- [[feishu|topics/feishu]] — 飞书（模式+踩坑+工具，3篇）
- [[multi-agent|topics/multi-agent]] — 多Agent（模式+踩坑+角色，9篇）
- [[agent-flow-cli|topics/agent-flow-cli]] — AgentFlow CLI（踩坑+配置+决策，7篇）
- [[architecture|topics/architecture]] — 架构（模式+概念+决策，7篇）
- [[security|topics/security]] — 安全（踩坑+权限，2篇）
- [[react-native|topics/react-native]] — React Native（踩坑，2篇）

## Tag Index（标签索引）

> 按标签精确查找文档。[[TAG-INDEX|查看完整标签索引]]

## Patterns（成功模式）

- [feishu](patterns/feishu/) — 飞书相关模式
  - [wiki-doc-read](patterns/feishu/wiki-doc-read.md) — Wiki文档读取三步流程
- [workflow](patterns/workflow/) — 工作流模式
  - [search-before-execute](patterns/workflow/search-before-execute.md) — 先查后执行 + 4种违规表现 + 关键词精准化
  - [three-agent-model](patterns/workflow/three-agent-model.md) — 三Agent协作模型（双验收 + 生命周期 + 并行执行 + 跳过Verifier违规）
  - [orchestrator-workers](patterns/workflow/orchestrator-workers.md) — 编排者-工作者并行模式
  - [rpi-workflow](patterns/workflow/rpi-workflow.md) — RPI 工作流：Research→Plan→Implement + GO/NO-GO 门控
  - [cross-model-workflow](patterns/workflow/cross-model-workflow.md) — 跨模型交叉验证（Claude 规划 + Codex QA）
  - [agent-teams](patterns/workflow/agent-teams.md) — 多会话并行协作（tmux + worktree + 共享任务列表）
  - [test-matrix-5-dimension-check](patterns/workflow/test-matrix-5-dimension-check.md) — 测试矩阵5维检查（覆盖度/可追溯/自动化映射/边界场景/双验收）
  - [e2e-script-three-part-structure](patterns/workflow/e2e-script-three-part-structure.md) — 联调脚本三段式结构（输入模板+预期输出+验证要点）
- [architecture](patterns/architecture/) — 架构模式
  - [adr-decision-record](patterns/architecture/adr-decision-record.md) — 架构决策记录(ADR)
  - [fatal-transient-errors](patterns/architecture/fatal-transient-errors.md) — FATAL/TRANSIENT错误分类与容错
  - [prompt-caching](patterns/architecture/prompt-caching.md) — 提示词缓存模式
  - [speculative-caching](patterns/architecture/speculative-caching.md) — 投机性缓存（1-token预热）
- [document](patterns/document/) — 文档转换模式
  - [requirements-spec-template](patterns/document/requirements-spec-template.md) — 需求规格说明书四段式模板
- [requirement](patterns/requirement/) — 需求分析模式
  - [frontend-backend-classification](patterns/requirement/frontend-backend-classification.md) — 需求文档前后端功能分类
- [gitlab](patterns/gitlab/) — 自托管GitLab模式
  - [self-hosted-gitlab-auth](patterns/gitlab/self-hosted-gitlab-auth.md) — glab CLI认证与API操作

## Pitfalls（踩坑记录）

- [feishu](pitfalls/feishu/) — 飞书相关踩坑
  - [lark-cli-params](pitfalls/feishu/lark-cli-params.md) — lark-cli参数格式陷阱
- [workflow](pitfalls/workflow/) — 工作流踩坑
  - [execute-without-search](pitfalls/workflow/execute-without-search.md) — 不查就执行（4种表现：跳过搜索/已知问题重复/先试错再查/研究阶段搜过以为实施阶段不用搜）
  - [git-archaeology-oversearch](pitfalls/workflow/git-archaeology-oversearch.md) — Git考古过度搜索
  - [skip-implementation-plan](pitfalls/workflow/skip-implementation-plan.md) — 跳过实施计划文档直接开发
  - [broad-keyword-search](pitfalls/workflow/broad-keyword-search.md) — 泛化关键词搜索导致范围扩大
  - [skipping-verifier](pitfalls/workflow/skipping-verifier.md) — 跳过验证者的后果
  - [promotion-duplication](pitfalls/workflow/promotion-duplication.md) — 晋升时创建重复内容而非更新已有文档
  - [parallel-execution-not-enforced](pitfalls/workflow/parallel-execution-not-enforced.md) — 多Agent并行未强制执行
  - [code-review-not-triggered](pitfalls/workflow/code-review-not-triggered.md) — 代码审查未自动触发
  - [multi-agent-rate-limit-recovery](pitfalls/workflow/multi-agent-rate-limit-recovery.md) — 多Agent并行429失败：主Agent必须Glob检查+兜底
- [security](pitfalls/security/) — 安全踩坑
  - [path-traversal-bypass](pitfalls/security/path-traversal-bypass.md) — 路径遍历绕过漏洞 + 安全模块对抗性测试
- [environment](pitfalls/environment/) — 环境踩坑
  - [venv-path-resolution](pitfalls/environment/venv-path-resolution.md) — .venv路径解析错误
- [tools](pitfalls/tools/) — 工具踩坑
  - [codex-provider-auth-mismatch](pitfalls/tools/codex-provider-auth-mismatch.md) — Codex登录后config.toml与auth.json不匹配
  - [mongosh-wire-version](pitfalls/tools/mongosh-wire-version.md) — mongosh与旧版MongoDB不兼容（wire version报错）
- [agent-flow](pitfalls/agent-flow/) — agent-flow CLI踩坑
  - [agent-flow-ship-rebase](pitfalls/agent-flow/agent-flow-ship-rebase.md) — ship自动rebase导致历史分叉
  - [add-feature-branch-conflict](pitfalls/agent-flow/add-feature-branch-conflict.md) — add-feature与已有分支冲突
  - [hook-path-inconsistency](pitfalls/agent-flow/hook-path-inconsistency.md) — Hook路径不一致：current_phase.md双路径问题
  - [git-stash-agent-flow-conflict](pitfalls/agent-flow/git-stash-agent-flow-conflict.md) — git stash与agent-flow状态文件冲突
- [react-native](pitfalls/react-native/) — React Native踩坑
  - [jest-babel-compatibility](pitfalls/react-native/jest-babel-compatibility.md) — 旧版RN项目Jest/Babel不兼容
- [llm-coding](pitfalls/llm-coding/) — LLM编程踩坑（源自Karpathy原则）
  - [overcomplication](pitfalls/llm-coding/overcomplication.md) — 代码过度复杂化（→ karpathy-principles 原则2）
  - [drive-by-refactoring](pitfalls/llm-coding/drive-by-refactoring.md) — 顺带重构（→ karpathy-principles 原则3）
  - [context-pollution](pitfalls/llm-coding/context-pollution.md) — 上下文污染（→ llm-degradation 合并）
  - [frontend-backend-type-alignment](pitfalls/llm-coding/frontend-backend-type-alignment.md) — 跨模块类型枚举不对齐（前端简化导致运行时异常）
  - [constraint-fix-pairing](pitfalls/llm-coding/constraint-fix-pairing.md) — 约束-修复配对缺失
  - [shared-constants-dedup](pitfalls/llm-coding/shared-constants-dedup.md) — 共享常量去重
  - [circuit-breaker-halfopen-probe](pitfalls/llm-coding/circuit-breaker-halfopen-probe.md) — 熔断器半开探测缺失
  - [rollback-honest-marking](pitfalls/llm-coding/rollback-honest-marking.md) — 回滚诚实标记

## Tools（工具）

- [markitdown](tools/markitdown.md) — Microsoft 文件转 Markdown 工具（PDF/DOCX/PPTX/XLSX 等）
- [codex-cli](tools/codex-cli.md) — Codex CLI 配置参考（认证/Provider/常见坑）
- [claude-code-settings](tools/claude-code-settings.md) — Claude Code 关键设置与环境变量精选参考
- [advanced-tool-use](tools/advanced-tool-use.md) — 高级工具用法（PTC/Dynamic Filtering/Tool Search）
- [monorepo-claudemd](tools/monorepo-claudemd.md) — Monorepo CLAUDE.md 加载机制（祖先/后代/兄弟）
- [mai-jira-cli](tools/mai-jira-cli.md) — 私有部署 Jira Server CLI（飞书SSO认证/配置/API调用注意事项）
- [mongodb-query](tools/mongodb-query.md) — MongoDB查询工具参考（pymongo替代mongosh/BSON序列化/常用查询模式）

## Concepts（核心概念）

- [agent-roles](concepts/agent-roles.md) — 多角色协作体系（索引 → 详见 souls/）
- [agent-resolution-order](concepts/agent-resolution-order.md) — Agent 调度优先级：Skill → Agent → Command
- [memory-systems](concepts/memory-systems.md) — Claude Code 四层记忆系统（CLAUDE.md/Auto-memory//memory/Agent memory）
- [permission-gradation](concepts/permission-gradation.md) — 权限梯度管理
- [thinking-chain-guidelines](concepts/thinking-chain-guidelines.md) — 思维链准则（文档驱动 + ReAct/Plan-and-Resolve/Reflection/自主学习/升级规则）
- [wiki-management](concepts/wiki-management.md) — Wiki知识库管理规范（目录结构/页面格式/生命周期/Lint规则）
- [karpathy-principles](concepts/karpathy-principles.md) — Karpathy LLM编程四原则（Think/Simplicity/Surgical/Goal-Driven + 场景示例 + 反模式速查）
- [llm-degradation](concepts/llm-degradation.md) — LLM 输出质量退化9层因素与上下文污染修复

## Decisions（架构决策）

- [enforcement-structure](decisions/enforcement-structure.md) — 规则执行保障架构：短规则 + 详细技能 + 守卫技能三层
