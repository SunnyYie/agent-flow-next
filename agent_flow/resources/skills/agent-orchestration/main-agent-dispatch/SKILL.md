---
name: main-agent-dispatch
version: 2.0.0
trigger: 主Agent派发, 子Agent, Agent dispatch, context overflow, 上下文溢出
confidence: 1.0
abstraction: universal
created: 2026-04-14
updated: 2026-04-15
---

# Skill: 主 Agent 派发协议

> **解决上下文溢出**：主 Agent 只保留流程状态，任务执行由独立子 Agent 完成，结果压缩后回传。

## Trigger

- 任务复杂度 ≥ Medium（4-10分）时，EXECUTE 阶段自动触发
- 主 Agent 上下文预算 > 70% 时强制触发
- 需要并行执行多个独立子任务时

## 核心原则

**主 Agent = 状态机 + 指针表**

主 Agent 上下文只包含：
1. 工作流阶段和任务清单（每任务 1 行）
2. 已完成任务的 L1 摘要（OUTCOME + 文件列表）
3. 活跃子 Agent 状态（名称、角色、任务 ID）

**子 Agent = 独立执行者**

子 Agent 拥有独立上下文窗口，负责：
1. 读取任务包获取完整上下文
2. 执行任务并增量写制品
3. 按模板写压缩摘要

## Procedure

### Step 1: 检查是否需要派发

```
条件检查:
├── 复杂度 ≥8 (Complex) → 始终派发
├── 复杂度 5-7 (Medium) → 派发验证子Agent，执行可自行
├── 复杂度 ≤4 (Simple) → 不派发，直接处理
├── 上下文预算 >70% → 强制派发任何剩余工作
├── 子任务涉及 ≥3 文件修改 → 派发 executor
└── 子任务需要 WebSearch → 派发 executor（Developer）
```

### Step 2: 更新 flow-context.yaml

在派发前，主 Agent 必须更新 `.agent-flow/state/flow-context.yaml`：

```yaml
workflow:
  id: "{唯一标识}"
  phase: "{当前阶段}"
  context_budget:
    used: {估算值}
    max: 200000
    status: "{healthy|warning|critical}"

tasks:
  - id: {任务ID}
    title: "{任务标题}"
    status: "{pending|in_progress|completed|failed}"
    agent: "{子Agent名称，in_progress时必填}"
    summary: "{L1摘要，completed时必填}"
    artifact: "{摘要文件路径，completed时必填}"

agents:
  - name: "{子Agent名称}"
    role: "{executor|verifier}"
    status: "{running|completed|failed}"
    task: {任务ID}
```

### Step 3: 生成任务包

为每个子 Agent 创建任务包文件 `.agent-flow/artifacts/task-{id}-packet.md`：

```markdown
# Task {id}: {title}

## 任务描述
{具体任务描述}

## 验收标准
- [ ] {标准1}
- [ ] {标准2}

## 依赖制品
- Task {dep_id} 输出: .agent-flow/artifacts/task-{dep_id}-summary.md

## 技能路径
- {项目技能路径}
- {全局技能路径}

## 记忆路径
- 读: {wiki/知识路径}
- 写: .agent-flow/memory/{agent_name}/Memory.md
- 写: .agent-flow/memory/{agent_name}/Soul.md

## 上下文预算
目标: {token数}
```

### Step 4: 派发子 Agent

使用 Claude Code Agent tool 派发：

**Executor 子 Agent**:

```
Agent({
    description: "executor-{n}: {任务标题}",  // Replace {n} with worker number, {任务标题} with a short task title
    prompt: "你是执行者 Agent。\n任务: {任务描述}\n验收标准: {验收标准}\n任务包: .agent-flow/artifacts/task-{id}-packet.md\n完成后写摘要到: .agent-flow/artifacts/task-{id}-summary.md\n完整结果写到: .agent-flow/artifacts/task-{id}-result.md\n修改文件列表写到: .agent-flow/artifacts/task-{id}-files.txt",
    // ^ Replace {任务描述} with the specific work items, {验收标准} with acceptance criteria
    // ^ {id} must match the task ID in flow-context.yaml so the main agent can find artifacts later
    subagent_type: "general-purpose"  // Always "general-purpose" — Claude Code's only subagent type
})
```

**Verifier 子 Agent**:

```
Agent({
    description: "verifier-{n}: 验证任务{id}",  // Replace {n} with verifier number, {id} with the task being verified
    prompt: "你是验证者 Agent。\n验证任务: {任务描述}\n验收标准: {验收标准}\n被验证的摘要: .agent-flow/artifacts/task-{id}-summary.md\n被验证的文件列表: .agent-flow/artifacts/task-{id}-files.txt\n任务包: .agent-flow/artifacts/task-{id}-packet.md\n写验证结果到: .agent-flow/artifacts/task-{id}-verification.md",
    // ^ The verifier reads the executor's summary + file list (not the full result) to check accuracy
    // ^ {id} must match the executor task ID — verifier and executor share the same task-{id} prefix
    subagent_type: "general-purpose"
})
```

**Developer（调研模式）子 Agent**:

```
Agent({
    description: "executor-{n}: 调研{主题}",  // Replace {n} with worker number, {主题} with the research topic
    prompt: "你是开发者 Agent（调研模式）。\n调研主题: {主题}\n任务包: .agent-flow/artifacts/task-{id}-packet.md\n写调研结果到: .agent-flow/artifacts/task-{id}-result.md\n写摘要到: .agent-flow/artifacts/task-{id}-summary.md",
    // ^ Developer(research mode) needs a topic but no acceptance criteria — output is informational
    // ^ {id} must match the task ID in flow-context.yaml
    subagent_type: "general-purpose"
})
```

### Step 5: 收集子 Agent 结果（三级压缩 + 渐进式加载）

子 Agent 完成后，主 Agent 按需加载：

1. **L1（始终读取）**: flow-context.yaml 中的任务状态和 1 行摘要
2. **L2（按需读取）**: `.agent-flow/artifacts/task-{id}-summary.md` — 结构化摘要（≤20行）
3. **L3（深度需求时）**: 不得直接读取，通过"深度上下文分析师"子 Agent 间接访问

**渐进式上下文加载协议**:

```
主 Agent 需要子 Agent 工作细节时：
├── 先读 L2 摘要（~500 tokens）
├── 摘要不够？
│   └── 定向读取 L3 结果的特定段落（用 offset/limit 参数）
└── 还不够？
    └── 派发"深度上下文分析师"子 Agent：
        Agent({
            description: "analyst: 分析任务{id}结果",
            prompt: "读取 .agent-flow/artifacts/task-{id}-result.md，回答以下问题：\n{具体问题}\n只返回答案，不要返回完整结果内容。",
            subagent_type: "general-purpose"
        })
```

**禁止**: 主 Agent 不能将 L3 完整内容加载到自身上下文。

**预算感知加载**:
- healthy 状态: 可自由读取 L2 摘要
- warning 状态: 限制 L2 读取数量（同时最多 3 个摘要）
- critical 状态: 禁止读取任何 L2/L3，只能看 flow-context.yaml 中的 L1

### Step 6: 验证摘要准确性（Verifier 抽检）

对于 Medium/Complex 任务的摘要，按 summary-verifier Skill 派发 Verifier 子 Agent 抽检：

**抽检策略**:
| 复杂度 | 抽检比例 | 触发条件 |
|--------|---------|---------|
| Simple | 0% | 不抽检 |
| Medium | 50% | 变更文件 ≥3 个时必须抽检 |
| Complex | 100% | 始终抽检 |

**Verifier 派发**:
```
Agent({
    description: "verifier-{n}: 抽检任务{id}摘要",
    prompt: "你是摘要验证者 Agent。\n验证目标: Task {id} 摘要准确性\n验证材料:\n1. 摘要: .agent-flow/artifacts/task-{id}-summary.md\n2. 文件列表: .agent-flow/artifacts/task-{id}-files.txt\n3. 任务包: .agent-flow/artifacts/task-{id}-packet.md\n\n检查项: 文件一致性|变更准确性|测试结果|遗漏检测|格式合规\n输出: .agent-flow/artifacts/task-{id}-verification.md\nVerdict: PASS|FAIL|PARTIAL",
    subagent_type: "general-purpose"
})
```

**验证结果处理**:
| Verdict | 动作 |
|---------|------|
| PASS | 确认完成，更新 flow-context.yaml |
| PARTIAL | 补充摘要缺失项 |
| FAIL | 重新派发 executor 修复，或由主 Agent 直接修复摘要 |

详见 `~/.agent-flow/skills/knowledge/summary-verifier/handler.md`

### Step 7: 更新流程状态

收集并验证完成后，更新 flow-context.yaml：

1. 将任务状态改为 completed/failed
2. 写入 L1 摘要（1 行）
3. 更新 agent 状态为 completed
4. 更新上下文预算

## 上下文预算估算方法

Claude Code 不暴露 token 计数，使用启发式方法追踪：

### 方法 1: 文件大小追踪（PostToolUse Hook 自动执行）

```python
# 每次读取文件时，累加文件大小到预算追踪器
# 估算公式: tokens ≈ file_size_bytes / 4 (英文) / 2 (中文)
def estimate_tokens(file_path: str) -> int:
    size = os.path.getsize(file_path)
    # 保守估算：假设混合内容，1 byte ≈ 0.3 token
    return int(size * 0.3)
```

### 方法 2: 对话轮次估算

```text
估算 tokens ≈ 对话轮次数 × 2000 (平均每轮)
```

### 预算不足时的压缩策略

当 status = warning 或 critical 时：

1. **摘要淘汰**: flow-context.yaml 中的 L1 摘要只保留最近 5 条，更早的只保留 artifact 路径
2. **避免读取大文件**: 优先读取 summary 文件而非 result 文件
3. **强制派发**: 将剩余任务全部派发给子 Agent
4. **状态最小化**: 只保留当前阶段和待处理任务列表
5. **新阶段重置**: 每个阶段开始时重置预算，因为上下文压缩会释放空间

## 并行派发规则

- 最多 3 个并行子 Agent
- 无依赖的任务在一条消息中并行派发（多个 Agent tool call）
- 有依赖的任务串行派发，前一个的制品路径写入后一个的任务包
- 递归深度限制：子 Agent 可再派发 1 层子子 Agent，但不能再深

## 递归派发（1层限制）

当 executor 子 Agent 发现自身上下文即将溢出时：

1. 子 Agent 可再派发 1 层子子 Agent
2. 子子 Agent 的任务包必须包含 `recursion_depth: 1` 标记
3. `recursion_depth: 1` 的 Agent 不允许继续派发
4. 子子 Agent 的摘要路径格式: `.agent-flow/artifacts/task-{id}-sub-{n}-summary.md`

## Rules

1. **主 Agent 不执行具体任务**: EXECUTE 阶段的代码编写、测试执行必须由子 Agent 完成
2. **摘要模板必须遵守**: 子 Agent 必须按摘要模板写 summary，不得自由发挥
3. **增量写制品**: 子 Agent 在执行过程中应增量写中间结果，而非仅完成时一次性写
4. **L3 完整结果禁止全量加载**: 主 Agent 上下文中不能包含任何 task-result.md 的完整内容
5. **flow-context.yaml 必须同步**: 每次状态转换前必须先更新 YAML
6. **并行上限 3**: 同时运行的子 Agent 不超过 3 个
7. **递归深度 ≤1**: 子子 Agent 不能再派发

## 变更历史

- v1.0.0 (2026-04-14): 初始版本，主 Agent + 子 Agent 派发协议
