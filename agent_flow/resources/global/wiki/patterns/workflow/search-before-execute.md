---
name: search-before-execute
type: pattern
module: workflow
status: verified
confidence: 0.95
created: 2026-04-13
last_validated: 2026-04-16
tags: [workflow, execute, quality, cognitive-loop, search-to-develop, pitfall, search-first, skill-first, 需求分析, 关键词, 精准定位]
---

# 先查后执行模式

> 每个子任务执行前必须查找已有方案，搜索完成后立即切分支开发。不搜索就执行是 AgentFlow 最高频违规行为。

## 正确流程

### 步骤 1: 搜索已有方案（按顺序，不可跳过）

1. `.agent-flow/skills/` 和 `~/.agent-flow/skills/` — 查找相关技能
2. `.agent-flow/memory/main/Soul.md` — 查找相关经验
3. `.agent-flow/wiki/` 和 `~/.agent-flow/wiki/` — 查找相关知识
4. WebSearch — 搜索专业标准和最佳实践

**每个子任务前必须重新搜索**，即使前置阶段已做过搜索。原因：

- 前置搜索针对整体任务，子任务有特定知识需求
- 连续编码时上下文窗口可能已丢失前置搜索结果
- 误将"已做过搜索"等同于"搜索结果仍然适用"是常见误区

### 步骤 2: 搜索完成后的标准流程（线性执行，无分支）

```
搜索相关代码 → 分析结果
  ├─ 找到相关代码 → 定位修改点 → git pull --rebase → git checkout -b feat/xxx → 开始开发
  └─ 搜索不到字段 → 判定为新增字段 → git pull --rebase → git checkout -b feat/xxx → 开始开发
```

### 步骤 3: 关键词精准化

需求文档通常包含**业务领域关键词**，而非技术实现关键词。按技术关键词搜索会匹配到不相关功能。

**正确做法**：

1. 从需求文档提取业务领域关键词（如"实习圈"、"简历诊断"）
2. 用业务关键词精确搜索代码位置
3. 定位到具体目录/文件后再用技术关键词补充了解

**示例**：

- 错误：搜索"AI评论" → 匹配到 AICommentTag、AiCommentGuide、AICommentRelatedFeedList 等多个不相关功能
- 正确：搜索"实习圈" → 精确定位到 `gossip_detail_new/` 目录

### 关键判断规则

1. 搜索不到 = 新增 → 直接开发，不需要验证其他分支
2. 搜索到但不确定 = 问用户 → 不要自行 git 考古
3. 搜索到且确认 = 立即切分支开发 → 不要过度分析

## 常见违规表现（4种）

### 违规 1: 完全不搜索就执行

EXECUTE 阶段跳过搜索现有方案就自行执行：

- 内容过滤：没搜索过滤规范 → 保留了冗余内容
- 格式转换：没搜索标准模板 → 自行臆断格式
- 双验收：没搜索验收标准 → 验收项不专业

### 违规 2: 跳过搜索导致已知问题重复

全局已有 `gitlab-mr-creation` skill 明确记录了"glab mr create 可能 404，优先用 API"，但跳过搜索步骤直接用了 `glab mr create`。

### 违规 3: 先试错再查 Skill

先用自己的方式尝试，失败后才去搜索。根因：对已知操作过于自信，试错成本心理预期过低。

### 违规 4: 以为搜索是一次性动作

研究阶段搜过，实施阶段不再搜。结果：前端状态枚举类型不对齐的问题未在编码阶段发现，验收阶段才被捕获。

**修复**：实施阶段每个子任务前必须重新执行 subtask-guard，关键词应更精确（2-3个核心词），而非重复前置搜索的大范围关键词。

## 禁止行为

- 搜索完后用 git log/show/diff 继续考古
- 搜索不到字段时去其他分支验证
- 读取需求文档后不立即切分支开发
- **不搜索就直接执行，即使"觉得自己知道怎么做"**

## 验证案例

- 飞书文档转需求规格说明书：不搜索就直接写 → 保留了冗余引言和项目管理占位符；搜索后发现只需功能需求/非功能需求/埋点 → 优化后质量大幅提升

## 相关条目

- [[git-archaeology-oversearch|pitfalls/workflow/git-archaeology-oversearch]]（反面：搜索过度）
