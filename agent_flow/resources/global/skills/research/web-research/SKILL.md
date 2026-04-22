---
name: web-research
version: 1.0.0
trigger: 搜索, 调研, 研究, 查找方案, 搜索解决方案, web search, research, 查资料
confidence: 0.9
abstraction: universal
created: 2026-04-13
---

# Skill: web-research

## Trigger
当需要搜索网络信息、查找解决方案、调研技术方案时触发

## Procedure
1. **明确搜索目标**：将模糊问题拆解为具体搜索关键词
2. **构造搜索查询**：
   - 技术问题：`{技术名} {问题} {年份}` 或 `{技术名} best practice`
   - 方案对比：`{方案A} vs {方案B} {场景}`
   - 工具查找：`{用途} CLI tool` 或 `{用途} library {语言}`
3. **执行搜索**：使用 WebSearch 工具
4. **筛选结果**：
   - 优先：官方文档、GitHub仓库、权威技术博客
   - 次选：Stack Overflow、技术论坛
   - 排除：营销内容、过时文章（检查日期）
5. **验证信息**：交叉验证关键结论，不依赖单一来源
6. **整理输出**：提取关键信息，标注来源
7. **记录经验**：
   - 搜索关键词和效果 → Soul.md（module:research）
   - 发现的新工具/方案 → Skill.md（创建新技能）
   - 搜索技巧 → Wiki patterns/

## Rules
- 搜索前先查 Soul.md/Skills/Wiki 是否有相关记录，有则直接复用
- 搜索技术方案时必须包含年份，避免过时信息
- 发现新工具时记录安装方法和使用步骤到 Skill.md
- 搜索结果需标注来源，不编造信息
- 每次搜索后评估：搜索关键词是否有效，无效则换关键词重试
