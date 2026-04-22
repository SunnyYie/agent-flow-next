# gstack — 需求评审到上线的流水线设计

> 来源: [garrytan/gstack](https://github.com/garrytan/gstack) | MIT | 23个Claude Code Skill

## 项目简介

Y Combinator CEO Garry Tan 的 AI 辅助开发工具集。将单人开发者武装为虚拟工程团队（CEO/设计师/工程经理/QA/SRE），60天产出60万行生产代码。**纯 Markdown 定义 Skill，零代码依赖**。

## 核心架构

- **Skill = Markdown文件**：每个角色一个 `.md`，通过 Claude Code skill 机制加载
- **文档驱动传递**：Skill间通过共享 Markdown 设计文档/测试计划传递上下文，非API调用
- **符号链接安装**：`setup` 脚本自动链接到 `~/.claude/skills/`

## 需求评审到上线流程（7步流水线）

```
Think → Plan → Build → Review → Test → Ship → Reflect
```

| 阶段 | 命令 | 角色 | 关键动作 |
|------|------|------|----------|
| 需求澄清 | `/office-hours` | YC导师 | 6个强制提问，质疑前提假设 |
| CEO评审 | `/plan-ceo-review` | CEO | 四种模式(扩展/选择扩展/保持/缩减) |
| 工程评审 | `/plan-eng-review` | 工程经理 | ASCII数据流图、状态机、测试矩阵 |
| 设计评审 | `/plan-design-review` | 设计师 | 0-10评分，AI slop检测 |
| 代码评审 | `/review` | Staff Eng | 自动修复明显问题，标记生产级bug |
| QA测试 | `/qa` | QA Lead | 真实浏览器点击，bug修复自动生成回归测试 |
| 发布部署 | `/ship` → `/land-and-deploy` | Release Eng | 同步main→跑测试→推送→合并PR→验证生产 |
| 监控复盘 | `/canary` → `/retro` | SRE/EM | 部署后监控循环 + 交付复盘 |

**一键全流程**：`/autoplan` 自动串联评审链，仅暴露品味决策给人类。

## 关键设计模式

1. **角色模拟**：每个Skill扮演组织角色，有明确职责边界和决策权限
2. **评审与实现分离**：`/review` 不实现，`/ship` 不评审
3. **智能路由**：自动检测变更类型决定需哪些评审
4. **渐进式安全**：`/careful` → `/freeze` → `/guard` 分级控制
5. **跨AI二审**：`/codex` 调用 OpenAI 做独立代码审查
6. **自动化测试闭环**：bug fix 自动生成回归测试

## 可借鉴要点

- **流水线而非工具箱**：关键是上下游 Skill 的数据传递约定
- **Skill 纯 Markdown 化**：零代码门槛，最高可移植性
- **一键 autoplan**：多步评审封装为单命令，仅暴露决策点
- **角色分工明确**：评审和实现严格分离
