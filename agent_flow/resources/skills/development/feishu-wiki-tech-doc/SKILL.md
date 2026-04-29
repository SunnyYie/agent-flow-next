---
name: feishu-wiki-tech-doc
version: 1.0.0
trigger: 飞书技术文档, wiki tech doc, 生成技术文档, feishu wiki document, 写文档到飞书
confidence: 0.85
abstraction: project
created: 2026-04-29
---

# Skill: 从分支代码生成飞书 Wiki 技术文档

## Trigger

当需求开发完成或进行中，需要在飞书 Wiki 目录下生成/更新技术文档时触发。

## Required Reading

- 全局 Wiki: `wiki/patterns/workflow/feishu-wiki-tech-doc.md` — 完整模式说明
- 全局 Wiki: `wiki/pitfalls/environment/lark-cli-login-shell-path-mismatch.md` — lark-cli 路径问题
- 全局 Skill: `skills/knowledge/tool-precheck/SKILL.md` — 工具预检

## Procedure

1. **收集分支信息** → `git diff master..HEAD --stat` + `git diff master..HEAD -- '*.tsx' '*.ts' '*.scss'`
2. **定位 Wiki 目录** → `lark-cli wiki spaces get_node --params '{"token":"<TOKEN>"}' --as user` 获取 space_id
3. **参考已有文档** → `lark-cli wiki nodes list` 列出子节点 + `lark-cli docs +fetch` 读取一篇参考
4. **编写 Markdown** → 按参考文档结构：需求链接→功能实现（关联代码+片段）→自测→待完成→CR
5. **创建文档** → `lark-cli docs +create --title "<标题>" --wiki-node "<父TOKEN>" --markdown "$CONTENT" --as user`
6. **权限处理** → 若报 `wiki:wiki` / `wiki:node:create` 权限不足：`lark-cli auth login --scope "wiki:wiki" --as user`

## 文档结构模板

```
需求文档：{链接}
JIRA：{链接}
代码分支：{branch}
仓库：{repo path}

# 需求背景
# 技术方案（页面信息表格 + 目录结构 + 数据流）
# 前端功能实现（按模块分节：关联代码 + 代码片段）
# 自测（UI测试 / 功能测试 checkbox）
# 待完成项（表格）
# Code Review
```

## Rules

- 开头不写一级标题（title 参数即为文档标题）
- 代码文件路径用行内代码格式
- 关键设计决策用 `<callout>` 高亮说明
- 遵循同目录已有文档的结构风格
- 权限不足时走 device-flow 授权，输出链接让用户打开
