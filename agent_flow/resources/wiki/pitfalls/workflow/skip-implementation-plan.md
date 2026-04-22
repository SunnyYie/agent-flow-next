---
name: skip-implementation-plan
type: pitfall
module: workflow
status: verified
confidence: 0.95
created: 2026-04-14
tags: [implementation, plan, document-driven, agent-flow]
---

# 跳过实施计划文档直接开发

## 问题描述
搜索完代码后直接开始改代码，没有按照 requirement-decomposition 技能写出正式的需求拆解文档（requirement-decomposition.md + code-impact-map.md）就开始开发。

## 典型表现
1. 在 current_phase.md 写了任务列表就认为计划够了，没有写正式的需求拆解文档
2. 搜索到代码位置后直接编辑代码，跳过文档化步骤
3. 需求确认后直接实现，不写代码影响地图

## 根因
1. 任务量小就认为不需要正式计划文档
2. 混淆了"任务列表"和"实施计划文档"——任务列表是粗粒度的，实施计划需要包含需求拆解、代码映射、确认记录
3. 急于编码，跳过文档驱动步骤

## 正确做法
1. 需求确认后 → 执行 requirement-decomposition 技能 → 写出 requirement-decomposition.md
2. 代码定位后 → 执行 requirement-code-mapping 技能 → 写出 code-impact-map.md
3. 两个文档写完且用户确认后 → 才能开始编码

## 相关条目
- [[document-driven-thinking-chain|文档驱动思维链执行模式]]
