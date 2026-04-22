---
name: orchestrator-workers
category: patterns
confidence: 0.9
sources:
  - claude-cookbooks/patterns/agents/orchestrator_workers.ipynb
tags: [multi-agent, orchestration, parallel, task-decomposition]
---

# Pattern: 编排者-工作者

## 问题

复杂任务需要多个不同视角来处理，但无法预先确定哪些视角最有价值。简单并行化会生成相同的变体，不适应具体输入。

## 解决方案

编排者 Agent 动态分析任务，决定最佳子任务分解方式，然后分派给专门的工作者 Agent 执行。

### 两阶段工作流

```
Phase 1: 分析 & 计划
  输入 → 编排者 LLM → <analysis> + <tasks> (XML)

Phase 2: 执行
  每个 task → 工作者 LLM(original_task + task_type + description) → <response>
```

### 核心实现

```python
from agent_flow.core.orchestrator import FlexibleOrchestrator

orchestrator = FlexibleOrchestrator(
    orchestrator_prompt=ORCHESTRATOR_PROMPT,
    worker_prompt=WORKER_PROMPT,
    llm_call=my_llm_call_fn,
    max_workers=3,
)
result = orchestrator.process(task, context)
```

### 与简单并行化的区别

| 维度 | 简单并行化 | 编排者-工作者 |
|------|-----------|--------------|
| 子任务定义 | 预先硬编码 | 运行时动态决定 |
| 适应性 | 对所有输入生成相同变体 | 根据输入特点定制分解策略 |
| 灵活性 | 低 | 高 |
| 复杂度 | 低 | 中（N+1 次 LLM 调用） |

### 适用场景决策树

```
任务是否需要多种方法/视角？
├── 否 → 单一 LLM 调用
└── 是 → 子任务是否可预先确定？
    ├── 是 → 简单并行化（更简单高效）
    └── 否 → 编排者-工作者（动态分解是核心价值）
```

### 结构化状态同步

编排者通过 `StructuredState` 与工作者同步状态：

```
编排者 → TaskState(task_id, task_type, description)
         ↓ EventBus TASK_ASSIGNED 事件
工作者 → WorkerResultState(worker_id, task_type, result, status)
         ↓ EventBus TASK_COMPLETED 事件
编排者 → OrchestratorOutput(analysis, tasks, worker_results)
```

### 反模式

- 编排者输出不使用结构化格式（无法可靠解析）
- 工作者仅收到子任务 ID 而无完整上下文（质量差）
- 不验证工作者输出（空值/格式错误导致下游崩溃）
- 延迟敏感场景使用编排者-工作者（额外 LLM 调用增加延迟）
- 子任务永远相同时使用编排者（过度工程化）

### 进阶优化

1. **并行执行**：使用 `ThreadPoolExecutor` 或 `asyncio` 并行运行工作者
2. **重试逻辑**：失败的工作者可自动重试
3. **合成阶段**：增加一个 LLM 合并工作者输出为最终结果
4. **混合模型**：编排者用 Opus（深度推理），工作者用 Haiku（快速执行）
5. **投机缓存**：编排者完成后预热缓存，工作者复用

## 相关

- [提示词缓存](prompt-caching.md)
- [AI 上下文管理](~/.agent-flow/skills/ai-context-management/handler.md)
