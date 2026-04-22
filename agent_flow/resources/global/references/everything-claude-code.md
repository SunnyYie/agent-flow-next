# everything-claude-code 最佳实践参考

> 来源：https://github.com/affaan-m/everything-claude-code
> 版本：v1.10.0（2026-04）
> 规模：48 agents, 183 skills, 79 commands, hooks, rules, MCP configs

## 一句话结论

ECC 是 Claude Code 生态最大规模的实践集合，核心贡献不在数量而在**模式发现**——尤其是 instinct 学习、迭代检索、策略压缩、自主循环和成本感知管道五个方面，值得 agent-flow 借鉴。

## 与 agent-flow 的关系映射

| ECC 概念 | agent-flow 对应 | 差距 |
|----------|----------------|------|
| Instinct → Skill 晋升 | Soul.md → Skill.md 管道 | ECC 有 confidence 演化规则和项目级作用域 |
| Iterative Retrieval | pre-flight-check + subtask-guard | ECC 有 4 阶段渐进收敛（DISPATCH→EVALUATE→REFINE→LOOP） |
| Strategic Compact | 无对应 | agent-flow 缺少策略性压缩建议 |
| Autonomous Loops | 无对应 | agent-flow 无自主循环模式 |
| Cost-Aware Pipeline | performance.md 模型选择 | ECC 有不可变成本追踪和窄重试逻辑 |
| Verification Loop | VERIFY 双验收 | ECC 有 6 阶段连续验证 + Hook 集成 |
| Hook Runtime Controls | settings.json 24 个 Hook | ECC 有 profile 分级和动态禁用 |

---

## 关键最佳实践

### 1. Instinct 学习架构（continuous-learning-v2）

**核心洞察**：通过 Hook 100% 可靠地观察会话，将行为模式原子化为 instinct，按 confidence 晋升为 skill/command/agent。

**instinct 模型**：
```
观察 → 提取 instinct（confidence: 0.3-0.9）→ 多次验证 → 晋升
```

**confidence 演化规则**：
- 初始 0.3（观察到的单次模式）
- 每次验证通过 +0.1，上限 0.9
- 验证失败 -0.2
- confidence ≥ 0.7 + validations ≥ 3 → 晋升为 Skill
- confidence ≥ 0.9 + validations ≥ 5 → 晋升为 Command/Agent

**项目级作用域**（v2.1）：
- 全局 instinct：`~/.claude/instincts/`（跨项目通用）
- 项目 instinct：`.claude/instincts/{project}/`（项目特定）
- 作用域决策：如果模式涉及项目路径/框架 → 项目级；否则 → 全局级

**agent-flow 借鉴点**：
- Soul.md 经验条目已有 confidence + validations，但缺少**自动演化规则**
- 可增加：Soul.md 条目 confidence ≥ 0.7 + validations ≥ 3 → 自动提示创建 Skill
- 项目级 vs 全局级判定逻辑可复用

### 2. 迭代检索（iterative-retrieval）

**核心洞察**：子 Agent 的上下文问题——派发后信息不足，需要渐进式收敛。

**4 阶段循环**（最多 3 轮）：
1. **DISPATCH**：派发子 Agent，提供初始上下文
2. **EVALUATE**：评估子 Agent 返回结果，识别信息缺口
3. **REFINE**：补充缺失上下文，重新派发
4. **LOOP**：重复直到结果满足要求或达到 3 轮上限

**最佳实践**：
- 起始广度优先（搜索术语和领域知识）
- 学习术语后再深挖具体细节
- 跟踪每轮的信息缺口
- "足够好"即停，不追求完美

**agent-flow 借鉴点**：
- 主 Agent 派发子 Agent 时，目前是单次派发
- 可增加：子 Agent 返回"信息不足"标记 → 主 Agent 补充上下文 → 重新派发
- 与 Main Agent Protocol 的 L2/L3 压缩策略互补

### 3. 策略压缩（strategic-compact）

**核心洞察**：不应让自动压缩随机丢弃上下文，应在**策略性时机**手动 `/compact`。

**压缩决策指南**：

| 场景 | 是否压缩 | 原因 |
|------|---------|------|
| 完成一个阶段，开始新阶段 | ✅ | 旧阶段上下文已固化到文件 |
| 长搜索链结束后 | ✅ | 搜索结果已记录到文件 |
| 调试陷入循环 | ✅ | 重新聚焦问题定义 |
| 正在调试复杂 bug | ❌ | 需要完整调用栈 |
| 多文件重构中间 | ❌ | 需要跨文件一致性 |
| 等待用户确认时 | ❌ | 需要保留决策上下文 |

**压缩后保留的内容**：
- CLAUDE.md 和 Rules
- 当前任务目标和状态
- TodoWrite 任务列表
- 最近 3-5 次工具调用
- Soul.md 中的关键经验

**Token 优化模式**：
1. **Trigger-table 懒加载**：在 CLAUDE.md 中只放触发关键词表，详细内容放 Skill 文件
2. **上下文组合感知**：避免 CLAUDE.md + Rules + Skill 三处重复相同指令
3. **重复指令检测**：定期审计多配置文件间的冗余指令

**agent-flow 借鉴点**：
- 可在 Hook 中增加 `suggest-compact` 建议
- 当前 phase 切换时（THINK→PLAN→EXECUTE）是天然压缩点
- Soul.md 的固定区 vs 动态区分离已部分实现"压缩后保留"

### 4. 自主循环模式（autonomous-loops）

**6 种模式从简到繁**：

**模式 1：顺序管道**（`claude -p`）
- 最简：每步新上下文，模型路由，工具限制
- 适用：明确的多步流水线
- 命令：`claude -p "step1" | claude -p "step2"`

**模式 2：REPL 循环**
- 内置持久会话
- 适用：需要上下文连续的任务

**模式 3：无限代理循环**
- 双提示编排器 + 子 Agent
- 适用：规格驱动的生成任务

**模式 4：持续 PR 循环**
- 生产级 shell 循环 + CI 门控 + 自动修复
- 关键：`SHARED_TASK_NOTES.md` 跨迭代传递上下文
- 适用：持续集成修复

**模式 5：去泥化模式（De-Sloppify）**
- 核心洞察：**两个专注的 Agent 优于一个受限的 Agent**
- 实现 Agent 先写功能 → 清理 Agent 后优化质量
- 适用：功能实现 + 代码质量双重目标

**模式 6：RFC 驱动 DAG 编排**
- 最复杂：RFC → DAG 分解 → 分层质量管道
- 分离上下文窗口消除作者偏见
- 合并队列 + 驱逐恢复

**反模式**：
- 无退出条件
- 无上下文桥接
- 重试相同失败
- 负面指令（"不要做X"比"做Y"效果差）
- 所有 Agent 共享一个上下文窗口
- 忽略文件重叠

**agent-flow 借鉴点**：
- De-Sloppify 模式适用于 EXECUTE 阶段：功能 Agent + 质量检查 Agent
- SHARED_TASK_NOTES.md 思路可复用为跨迭代的 `.agent-flow/state/task-notes.md`
- 反模式清单应加入 pitfall 库

### 5. 成本感知 LLM 管道（cost-aware-llm-pipeline）

**模型路由策略**：

| 任务复杂度 | 推荐模型 | 成本比 |
|-----------|---------|--------|
| 简单查询/格式化 | Haiku | 1x |
| 日常编码/重构 | Sonnet | 3x |
| 架构决策/深度分析 | Opus | 15x |

**关键模式**：
1. **不可变成本追踪**：每次 LLM 调用记录 model + tokens + cost
2. **窄重试逻辑**：仅重试瞬态错误（429/500/502/503），不重试 400/401/403
3. **Prompt 缓存**：固定前缀 + 动态后缀；重用 system prompt

**反模式**：
- 所有任务都用最大模型
- 宽泛重试（重试所有错误）
- 无成本追踪
- 不利用缓存

**agent-flow 借鉴点**：
- 子 Agent 派发时可按任务复杂度选择模型
- 失败重试应区分瞬态 vs 永久错误
- 可在 flow-context.yaml 中增加 cost_tracking 字段

### 6. 验证循环（verification-loop）

**6 阶段验证**：
1. Build — 编译/构建通过
2. Type Check — 类型检查通过
3. Lint — 代码规范通过
4. Test Suite — 测试套件通过
5. Security Scan — 安全扫描通过
6. Diff Review — 变更审查通过

**输出格式**：
```
[VERIFY] Phase 1: Build → PASS (0 errors, 0 warnings)
[VERIFY] Phase 2: Type Check → FAIL (3 errors in auth.py)
```

**连续模式**：长时间会话中，每 N 次工具调用自动触发验证。

**agent-flow 借鉴点**：
- 当前双验收是"最终验收"，缺少"过程验证"
- 可在 Hook 中增加：每 10 次 Edit/Write 工具调用后自动触发 lint + test
- 6 阶段清单可作为 VERIFY 阶段的结构化检查表

### 7. Hook 运行时控制

**Profile 分级**：

| Profile | 行为 | 适用场景 |
|---------|------|---------|
| minimal | 仅核心 Hook | 轻量任务 |
| standard | 大部分 Hook | 日常开发 |
| strict | 全部 Hook + 额外检查 | 安全敏感任务 |

**环境变量控制**：
- `ECC_HOOK_PROFILE=minimal|standard|strict` — 切换 profile
- `ECC_DISABLED_HOOKS=hook1,hook2` — 动态禁用特定 Hook

**Hook 最佳实践**：
- PreToolUse：拦截不安全操作，注入上下文
- PostToolUse：追踪状态变化，记录成本
- Stop：生成总结，触发反思
- SessionStart/End：初始化/清理
- PreCompact：建议压缩时机

**agent-flow 借鉴点**：
- 当前 24 个 Hook 无分级控制
- 可增加 `AGENT_FLOW_HOOK_PROFILE` 环境变量
- simple 任务 → minimal（仅铁律 Hook）；complex 任务 → strict（全部 Hook）

### 8. Search-First 工作流

**5 步流程**：
1. 需求分析 → 明确搜索目标
2. 并行搜索 → GitHub + docs + registry 同时搜索
3. 评估结果 → 可靠性、维护度、许可证
4. 决策 → 采用/扩展/组合/自建
5. 实现 → 基于搜索结果

**决策矩阵**：

| 条件 | 决策 |
|------|------|
| 现有方案满足 80%+ | 采用（Adopt） |
| 现有方案需小幅修改 | 扩展（Extend） |
| 多个方案各有所长 | 组合（Compose） |
| 无可用方案 | 自建（Build） |

**agent-flow 借鉴点**：
- agent-flow 的 search-first 主要是搜 Skill/Wiki
- ECC 额外强调搜 GitHub/registry，避免重复造轮子
- 可在 development-workflow.md 中强化 `gh search repos` + `gh search code` 步骤

---

## 文件组织原则

**核心规则**：多小文件优于少大文件

| 类型 | 典型大小 | 最大大小 |
|------|---------|---------|
| 组件/模块 | 200-400 行 | 800 行 |
| Skill 定义 | 50-150 行 | 300 行 |
| Agent 定义 | 30-100 行 | 200 行 |
| Hook 脚本 | 20-80 行 | 150 行 |

**不可变性原则（CRITICAL）**：
- 数据更新必须创建新对象，不修改原对象
- 函数参数视为不可变
- 配置对象一旦创建不修改
- 状态变更通过创建新状态实现

---

## Token 优化配置推荐

```json
{
  "model": "sonnet",
  "env": {
    "MAX_THINKING_TOKENS": "10000",
    "CLAUDE_CODE_SUBAGENT_MODEL": "haiku"
  }
}
```

**上下文管理命令**：
- `/compact` — 手动压缩
- `/cost` — 查看当前 token 使用
- `/context` — 查看上下文使用率

**Agent Teams 成本警告**：多 Agent 并行时成本倍增，需要：
1. 明确分工避免重叠
2. 子 Agent 用 Haiku 降低成本
3. 设置成本上限
4. 追踪每次调用的模型和 token 数

---

## 可借鉴的改进方向（优先级排序）

1. **Instinct 自动演化规则**：Soul.md 条目达到阈值时自动提示创建 Skill，而非等待 REFLECT 手动检查
2. **策略压缩 Hook**：在 phase 切换点自动建议 `/compact`
3. **Hook Profile 分级**：按任务复杂度切换 Hook 严格程度
4. **迭代检索**：子 Agent 上下文不足时支持补充后重新派发
5. **De-Sloppify 模式**：EXECUTE 阶段拆分为功能实现 + 质量优化两轮
6. **6 阶段验证清单**：VERIFY 阶段增加 Build/TypeCheck/Lint/Test/Security/DiffReview 结构化检查
7. **成本追踪**：flow-context.yaml 增加 cost_tracking，区分模型路由
8. **窄重试逻辑**：子 Agent 失败重试区分瞬态 vs 永久错误
9. **Search-First 决策矩阵**：在开发流程中增加 Adopt/Extend/Compose/Build 决策步骤
10. **自主循环反模式**：将 6 个反模式加入 pitfall 库
