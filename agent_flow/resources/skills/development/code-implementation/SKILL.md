---
name: code-implementation
version: 1.0.0
trigger: 写代码, 实现, 编码, coding, 开发, implement, 写函数, 开发功能
confidence: 0.85
abstraction: universal
created: 2026-04-13
---

# Skill: code-implementation

## Trigger
当需要编写代码实现功能、修复Bug、重构代码时触发

## Procedure
1. **查找相关技能**（必须先做）：
   - 搜索 `.agent-flow/skills/` 和 `~/.agent-flow/skills/` 中是否有相关实现技能
   - 搜索 Wiki 中是否有相关设计模式或实现模式
   - 搜索 Soul.md 中是否有相关经验
   - WebSearch 搜索 "{技术栈} {功能} best practice" 或 "{技术栈} {功能} implementation"
2. **TDD 流程**：
   - RED: 先写测试（定义期望行为）
   - GREEN: 实现功能（让测试通过）
   - IMPROVE: 重构（消除重复、改善结构）
3. **实现步骤**：
   - 读取设计文档/需求，明确完成标准
   - 搜索同类开源实现，理解核心模式（`gh search code`, WebSearch）
   - 按设计文档编码，不做超出范围的实现
   - 自检：对照完成标准逐条检查
4. **安全底线**：
   - 不硬编码密钥
   - 不引入注入漏洞（SQL/XSS/命令注入）
   - 输入校验在系统边界
   - 使用参数化查询
5. **记录沉淀**：
   - 实现模式 → Skill.md（如果可复用）
   - 踩坑 → Soul.md（module:{模块}, type:pitfall）
   - 设计决策 → Wiki decisions/

## Rules
- 必须先搜索相关技能和开源实现再编码
- 严格按设计文档实现，不自行扩展功能
- 不加多余的注释、类型注解（除非任务要求）
- 遇到不确定的需求 → 暂停报告，不自行假设
- 代码安全：每次实现后自检 OWASP Top 10
