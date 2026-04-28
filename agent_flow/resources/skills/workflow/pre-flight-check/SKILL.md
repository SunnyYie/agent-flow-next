---
name: pre-flight-check
version: 3.0.0
trigger: 任何任务开始前, 新任务, task start, pre-flight, 开始工作, 新需求
confidence: 1.0
abstraction: universal
created: 2026-04-13
updated: 2026-04-14
---

# Skill: Pre-Flight Check

> **强制入口技能**。每个任务开始前必须执行，不可跳过。v3.0 新增量化的 5 维复杂度评估（替代主观 S/M/X）、分级工作流差异、临界知识区预加载。

## Trigger

**每个任务开始前必须执行**，无论任务大小。这是 AgentFlow 的强制入口。

## Procedure

### Step 1: 项目配置检查（不可跳过）

**v3.2 新增：缓存优先机制**。先检查 `.agent-flow/state/.preflight-cache.md` 缓存，命中则跳过大量文件读取。

```text
0. 缓存检查（新增，优先执行）
   ├─ .agent-flow/state/.preflight-cache.md 存在且未过期（<24h）？
   │   ├─ 是 → 读取缓存获取项目配置摘要、Skills索引、Wiki索引
   │   │        跳过 Agent.md/purpose.md/INDEX.md/SOUL.md 全文读取
   │   └─ 否 → 继续常规流程
   └─ 缓存不存在 → 生成缓存（读取所有源文件后提取摘要写入）

1. .dev-workflow/ 是否存在？
   ├─ 存在 → 读取 .dev-workflow/Agent.md（如缓存命中则只读摘要）
   └─ 不存在 → 继续检查

2. .agent-flow/ 是否存在？
   ├─ 存在 → 读取配置继续
   └─ 不存在 → 停止，询问用户是否初始化

3. .agent-flow/config.yaml 是否有项目上下文？
   ├─ tech_stack 为空 → 询问用户补充项目信息
   └─ 有内容 → 继续读取

4. 如 .dev-workflow/ 不存在但 .agent-flow/ 存在：
   → 提示用户："本项目没有 .dev-workflow/，是否要初始化？(agent-flow init --dev-workflow)"
   → 用户拒绝 → 继续使用 .agent-flow/ 即 Layer 2

5. Hook/插件就绪检查（新增）：
   ├─ `.claude/settings.json` 或 `.claude/settings.local.json` 中是否存在 Agent-flow hooks？
   ├─ 当前任务依赖插件（如 lark-cli、jira-cli）是否可用？
   └─ 缺失时先补齐；`hook-readiness-guard` 会硬阻断代码修改和变更命令
```

**缓存失效条件**（任一满足则重新生成）：
- 缓存文件不存在
- 缓存文件修改时间 > 24 小时
- 任一源文件（Agent.md/config.yaml/SOUL.md）修改时间 > 缓存修改时间

**输出**：确认项目配置状态，记录到 Memory.md。

### Step 2: 任务复杂度量化评估（v3.0 改进）

在本 Step 内直接执行 5 维量化评分（原 `task-complexity` 内容已并入此处），替代主观 S/M/X 判断：

```text
在 pre-flight-check Step 2 内完成评分 → 逐维评分（范围/跨模块/新颖度/风险/外部依赖）→ 总分 0-10

0-3  → Simple  (快速路径)
4-6  → Medium  (标准路径)
7-10 → Complex (严格路径)
```

**各分级对应行为差异**：

| 行为 | Simple | Medium | Complex |
|------|--------|--------|---------|
| 知识搜索 | 2步（全局Skills+Wiki） | 5步全做 | 5步+强制WebSearch |
| GO/NO-GO | 无，用户确认即可 | Plan阶段门控 | 每阶段门控 |
| 双验收 | 自审即可 | 关键子任务 | 改动量≥50行或3+文件时双验收 |
| 文档化 | 分析→Memory.md | 分析+计划写入 | 分析+计划+每阶段记录 |
| 多Agent | 不需要 | 验收时双Agent | 执行+验收都多Agent |
| Hook行为 | 30min标记，首次软提醒 | 10min，硬阻断 | 5min，硬阻断 |

**评估结果写入** `.agent-flow/state/.complexity-level`，hooks 自动读取调整行为。

**记录**: `复杂度: {Simple|Medium|Complex} (总分:{0-10})` 写入 Memory.md。

### Step 3: 知识检索（强制，但按复杂度分级调整深度）

将任务描述分词，提取关键词，按以下顺序搜索。

**全量搜索（5步，Skills 使用三级查找优化）**：
```text
搜索1: Read ~/.agent-flow/skills/topics/{关键词}.md    → Skills 主题枢纽（O(1)）
       或 Grep "{关键词}" ~/.agent-flow/skills/TAG-INDEX.md → Skills 标签索引（O(1)）
       兜底: Grep "{关键词}" ~/.agent-flow/skills/   → Skills 全量搜索
搜索2: Grep "{关键词}" .agent-flow/skills/             → 项目技能（递归）
搜索3: Grep "{关键词}" .agent-flow/memory/main/Soul.md → 项目经验
搜索4: Grep "{关键词}" .agent-flow/wiki/               → 项目知识（优先主题枢纽）
搜索5: Grep "{关键词}" ~/.agent-flow/wiki/              → 全局知识（优先主题枢纽）
```

**按复杂度调整搜索深度**：
- Simple: 只做搜索2+5（全局 Skills + 全局 Wiki）
- Medium: 全部 5 步
- Complex: 全部 5 步 + 强制 `WebSearch "{任务关键词} best practice"`

**飞书需求文档特殊顺序（新增）**：
- 若输入包含 `feishu.cn/wiki` 或飞书文档线索，必须先完成：
  1. 项目级 wiki/skills 检索
  2. 团队级 wiki/skills 检索
  3. 仅当前两层都无结果时才允许 WebSearch
- 禁止直接 WebSearch 作为第一步

**有结果** → 读取匹配的 Skill/Wiki，记录到分析文档。
**全部无结果** → `WebSearch "{任务关键词} best practice"` → 网络搜索

### Step 4: 环境变量优化检查（新增，中等+复杂任务必做）

检查 Claude Code 关键环境变量是否已优化：

```text
1. CLAUDE_AUTOCOMPACT_PCT_OVERRIDE 是否设置？
   ├─ 未设置 → 建议: export CLAUDE_AUTOCOMPACT_PCT_OVERRIDE=50（降低自动压缩阈值）
   └─ 已设置 → 记录当前值

2. ENABLE_TOOL_SEARCH 是否设置？（MCP 工具多时）
   ├─ 未设置 → 建议: export ENABLE_TOOL_SEARCH=auto:30
   └─ 已设置 → 记录当前值

3. CLAUDE_CODE_SUBAGENT_MODEL 是否设置？
   ├─ 未设置 → 默认（子Agent继承主模型）
   └─ 已设置 → 记录当前值

4. 对于复杂任务(X): 检查 worktree 配置是否就绪
```

**输出**: 环境优化建议记录到 Memory.md。

### Step 5: 任务分析文档化（必须写入文件）

将 Step 1-2 的结果写入 `.agent-flow/memory/main/Memory.md`：

```markdown
[THINK] {日期时间}
任务: {任务描述}
复杂度: {S|M|X}
RPI阶段: {Research|Plan|Implement}
项目配置: .agent-flow={有/无} | .dev-workflow={有/无} | config={完整/空}
相关经验: {找到的经验摘要，或"无-需WebSearch"}
相关技能: {技能名(confidence)，或"无"}
相关Wiki: {Wiki条目，或"无"}
环境优化: {已优化项/建议项}
执行模式: {serial|parallel}
所需工具: {预估工具列表}
未知项: {需要确认或搜索的事项}
```

**绝对禁止**：分析只在脑中完成而不写入文件。

### Step 6: 执行计划文档化（必须写入文件）

将任务分解写入 `.agent-flow/state/current_phase.md`（canonical）：

```markdown
# 任务: {任务描述}

## 复杂度: {S|M|X}

## RPI 阶段规划
- Research: {已完成/跳过-简单任务/待执行}
- Plan: {待执行}
- Implement: {待执行}

## 实施计划
- T1: {子任务描述}（{有技能:xxx / 需搜索方案 / 需安装工具:xxx}）[{执行方式: Skill内联/Agent独立}]
- T2: {子任务描述}（{有技能:xxx / 需搜索方案}）[{执行方式}]
- T3: {子任务描述} ⚠️双验收 [{执行方式}]
- ...

## 变更点
- CP1: {核心变更点}

## 验收标准
- AC1: {验收标准}

模式: {serial|parallel}
依赖: {T1→T2→T3 或 T1→[T2,T3]→T4}
验收点: {标记⚠️的子任务编号}

## 每个子任务执行前
执行 subtask-guard 技能：搜索 Skill → Soul → Wiki → WebSearch → 选择执行方式
```

### Step 7: 用户确认 + GO/NO-GO 门控（按复杂度分级）

1. 向用户展示执行计划摘要（含复杂度、RPI 阶段、执行方式）
2. 有不确定项 → 列出选项和利弊，请求用户选择
3. **GO/NO-GO 评审**（按复杂度分级）：
   - **Simple**: 无需 GO/NO-GO，用户确认"OK"即可开始
   - **Medium**: Plan 阶段需 GO/NO-GO（需求无歧义 + 方案可行 + 依赖已识别 + 有验收标准）
   - **Complex**: 每阶段（Research/Plan/Implement）都需 GO/NO-GO
   - **NO-GO**: 需求模糊 / 方案风险大 / 缺关键信息 → 回退补充
4. 用户确认 GO → 开始按计划执行
5. **禁止**：用户未确认就开始执行

**用户验收标记**（v3.0 新增）：GO 通过后，Agent 应追加结构化记录到 `.agent-flow/state/.user-acceptance-done`：

```text
phase={research|plan|implement}
status=accepted
timestamp={ISO8601}
task={当前任务描述}
confirmed_by=user
summary={用户确认摘要}
```

多阶段验收使用空行分隔多条记录。

**此标记是推送代码的硬性前置条件**（Medium/Complex 任务）。`user-acceptance-guard.py` hook 会在 `git push` 和 MR 创建时检查此标记。

**绝对禁止**：不经用户确认就创建验收标记。

## Rules

- **不可跳过**：每个任务开始前必须执行全部7个Step
- **先查后执行**：Step 3 是所有后续执行的前提，不搜索就执行 = 违规
- **复杂度量化**：Step 2 必须执行 5 维量化评分，不可主观判断
- **分级执行**：根据复杂度等级调整搜索深度、门控强度、验收要求，不要一刀切
- **GO/NO-GO**：Simple 无需、Medium Plan 门控、Complex 每阶段门控
- **文档驱动**：分析和计划必须写入文件，不能只在脑中完成
- **不确定就问**：有模糊点立即停止并询问用户（铁律3）
- **提问后复判**：每次澄清后必须复判“是否已可开工”，可开工则停止继续追问
- **澄清复判硬闸**：每次 AskUserQuestion 后必须完成 `.clarification-recheck-done`，否则 `clarification-guard` 阻断实现
- **自动化节奏硬闸**：禁止连续“问一步停一步”；`clarification-guard` 会在无进展时阻断重复停顿
- **子任务守卫**：每个子任务执行前必须调用 subtask-guard 技能搜索知识库
- **临界知识预加载**：检查 Soul.md 临界知识区是否有与当前任务相关的工具条目
- **用户验收闸**：推送代码前必须有用户验收标记(.user-acceptance-done)，hook 强制执行

## 变更历史

- v3.1.0 (2026-04-14): Step 7 新增用户验收标记说明，与 user-acceptance-guard.py hook 联动
- v3.0.0 (2026-04-14): Step 2 改为 5 维量化评分；Step 3 按复杂度调整搜索深度；Step 7 GO/NO-GO 按复杂度分级；新增临界知识预加载规则
- v2.0.0 (2026-04-14): 新增任务复杂度分级(S/M/X)；新增 RPI 阶段规划；新增 GO/NO-GO 门控；新增环境变量优化检查；执行计划增加执行方式标注
- v1.0.0 (2026-04-13): 初始版本
