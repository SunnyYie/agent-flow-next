---
name: claude-template
category: project-template
tags: [CLAUDE.md, 模板, 项目规范, hooks]
updated: 2026-04-27
---

# 项目级 CLAUDE.md 模板

> 目标：统一 Claude Code 在项目内的行为边界、流程入口与执行约束。

```markdown
# CLAUDE.md

## 1. 项目目标
- 项目名称：{项目名}
- 业务目标：{一句话说明}
- 当前阶段：{需求/开发/验收}

## 2. 执行协议
- 必须先执行：pre-flight-check
- 必须遵循：search-before-execute
- 需求澄清后才能开发：requirement-decomposition

## 3. 知识检索顺序（强制）
1. `.agent-flow/wiki` / `.agent-flow/skills`
2. 团队级 `agent-flow-team` wiki/skills
3. WebSearch（仅前两层无结果时）
4. 全部失败后再向用户升级

## 4. 开发约束
- 禁止在 `main/master/develop` 直接改代码
- 禁止无计划直接实现
- 每个子任务前必须检索相关 wiki/skill
- 关键工具操作（Jira/MR/发布）必须先读对应工具文档

## 5. 产出要求
- 需求拆解文档：`.agent-flow/state/requirement-decomposition.md`
- 代码影响地图：`.agent-flow/state/code-impact-map.md`
- 项目结构映射：`.agent-flow/wiki/project-structure.md`
- 验收材料：需求映射 + 文件变更 + 测试证据 + 风险说明

## 6. 门控点
- G1 初始化就绪
- G2 需求拆解与代码映射确认
- G3 测试完成
- G4 用户验收通过
```
