---
name: agents-template
category: project-template
tags: [AGENTS.md, 模板, 角色协作, 子Agent]
updated: 2026-04-27
---

# 项目级 AGENTS.md 模板

```markdown
# AGENTS.md

## 1. 角色定义
- Main Agent：流程编排、风险控制、用户沟通
- Coder Agent：实现与测试
- Verifier Agent：独立验收
- Supervisor Agent：分支/Jira/发布治理

## 2. 子Agent执行前置
- 必须读取：
  - `.agent-flow/wiki/INDEX.md`
  - `.agent-flow/skills/Index.md`
  - 与任务相关的分支/Jira工具文档
- 必须回传：
  - 修改文件列表
  - 测试证据
  - 风险与待确认项

## 3. Jira字段规则
- 默认值字段可自动填写：
  - 开发预估工期=8
  - 端=RN
  - 需求目标=OKR相关
  - 需求描述留空
  - 相关角色=sunyi
- 非默认或有歧义字段：必须请求用户确认，禁止猜填。

## 4. 质量闸门
- 未完成需求澄清：禁止开发
- 未完成测试证据：禁止提交验收
- 未获用户确认：禁止推送/提PR
```
