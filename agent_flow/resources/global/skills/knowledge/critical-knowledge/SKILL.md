---
name: critical-knowledge
version: 1.0.0
trigger: 临界知识注入, critical knowledge, 重复踩坑, 临界知识区管理
confidence: 1.0
abstraction: universal
created: 2026-04-14
---

# Skill: Critical Knowledge（临界知识注入与管理）

> **解决"wiki有文档但Agent不读"的根本问题**。将高频踩坑的工具用法从 wiki 自动晋升到 Soul.md 临界知识区，确保每次对话自动加载。

## Trigger

- self-questioning skill 检测到重复踩坑（同一 pitfall 在自查报告中出现 ≥2 次）
- 手动触发：当发现 Agent 反复在某个工具上犯错时

## Problem

当前系统的知识加载存在根本性不对称：
- **Soul.md**：每次对话自动加载，但只存抽象经验
- **Wiki**：存具体工具用法，但需主动搜索才加载
- **结果**：Agent 不搜 wiki 就执行 → 犯同样的错 → wiki 有记录但无效

**临界知识区**解决了这个问题：在 Soul.md 中开辟一个专区，自动存放高频踩坑工具的要点摘要。

## Procedure

### Step 1: 检测晋升条件

从 `.agent-flow/state/self-questioning-report.md` 中统计 pitfall 出现频率：

```text
条件1: 同一 pitfall 在自查报告中出现 ≥2 次
条件2: 对应 wiki 条目 confidence ≥ 0.9
条件3: 该工具不在临界知识区中（避免重复注入）

三个条件同时满足 → 执行晋升
```

### Step 2: 提取要点摘要

从 wiki pitfall 条目中提取关键信息，格式化为 5 行以内：

```markdown
### TOOL: {工具名称}

- 要点1（最常犯的错误和正确做法）
- 要点2（关键命令或参数格式）
- 要点3（必要的前置步骤）
- Wiki: {wiki路径}
```

**提取规则**：
- 每个工具最多 5 行要点
- 只保留"怎么做"，不保留"为什么"（原因在 wiki 中）
- 必须包含关键命令的精确格式
- 必须包含 wiki 链接供深入查阅

### Step 3: 注入 Soul.md 临界知识区

在 `souls/main.md` 的"临界知识区"部分添加新条目：

1. 读取当前 `souls/main.md`
2. 定位 `## 临界知识区` 部分
3. 在已有条目后追加新条目
4. 如已达 5 条上限 → 执行降级（Step 4）

### Step 4: 降级管理（临界知识区满时）

当临界知识区已有 5 条且新条目需要进入时：

1. 统计每个现有条目在最近 3 次 self-questioning 报告中被引用的次数
2. 引用次数最少的条目降级回 wiki-only
3. 降级操作：从 Soul.md 临界知识区删除该条目
4. 降级不删除 wiki 中的原始内容

**降级条件**（任一满足即降级）：
- 连续 3 次 self-questioning 报告中未被引用
- 对应 wiki 条目被标记为 deprecated
- 有更新的 wiki 条目取代了它

### Step 5: 注册工具监控

将新工具添加到监控列表：

1. 在 `.agent-flow/state/.tool-wiki-read` 中创建该工具的监控条目
2. 在 `~/.agent-flow/config.yaml` 的 `critical_tools` 列表中添加该工具
3. tool-precheck-guard.py hook 将自动开始监控该工具的使用

## 临界知识区格式规范

```markdown
## 临界知识区（自动注入 — 由 critical-knowledge skill 维护）

> 此区存放"犯错次数≥2 且 wiki confidence≥0.9"的工具用法要点。
> 最多 5 条，按犯错频率排序。超出时最低频条目降级回 wiki-only。
> 每次对话自动加载，确保高频踩坑知识始终可用。

### TOOL: lark-cli

- 参数格式：`--params '{"key":"value"}'`，不支持 `--key value`
- 使用前必查 schema：`lark-cli schema {resource}.{method}`
- Wiki: pitfalls/feishu/lark-cli-params.md

### TOOL: {下一个工具}
...
```

## Rules

- **上限 5 条**：临界知识区最多 5 个工具条目，防止 Soul.md 过长影响加载效率
- **每条 5 行**：每个工具最多 5 行要点，只保留最关键的信息
- **自动维护**：临界知识区由本 skill 自动管理，不可手动编辑
- **晋升有据**：必须有 self-questioning 报告和 wiki 条目双重依据才能晋升
- **降级有据**：降级基于引用频率统计，不是随意删除
- **Wiki 保留**：降级只删除 Soul.md 中的摘要，不删除 wiki 原始内容

## 变更历史

- v1.0.0 (2026-04-14): 初始版本，临界知识区管理 + 自动晋升 + 降级机制
