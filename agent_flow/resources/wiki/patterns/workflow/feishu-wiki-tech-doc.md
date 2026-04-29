---
name: feishu-wiki-tech-doc
type: pattern
module: workflow
status: verified
confidence: 0.85
created: 2026-04-29
last_validated: 2026-04-29
tags: [feishu, wiki, lark-cli, tech-doc, documentation, 分支代码]
---

# 从分支代码生成飞书 Wiki 技术文档

## 场景

需求开发完成或进行中，需要在飞书 Wiki 目录下生成技术文档供团队 review 和归档。

## 流程

### 1. 收集分支代码信息

```bash
# 获取分支变更文件列表
git diff master..HEAD --stat

# 获取业务代码变更
git diff master..HEAD -- '*.tsx' '*.ts' '*.scss'
```

### 2. 获取飞书 Wiki 目录结构

```bash
# 从 Wiki URL 提取 token → 查询节点信息获取 space_id
lark-cli wiki spaces get_node --params '{"token":"<TOKEN>"}' --as user

# 列出子节点（参考已有文档结构）
lark-cli wiki nodes list --params '{"space_id":"<SPACE_ID>","parent_node_token":"<TOKEN>","page_size":50}' --as user
```

### 3. 参考已有文档格式

```bash
lark-cli docs +fetch --doc "<OBJ_TOKEN>" --as user --format pretty
```

现有文档通用结构：需求链接 + JIRA → 前端功能更新（按模块分节，附关联代码+代码片段）→ 自测清单 → BugFix → Code Review

### 4. 编写 Lark-flavored Markdown

关键规范：
- 开头**不要写一级标题**（title 参数已设标题）
- 使用 `<callout>` 高亮关键设计决策
- 代码片段用围栏代码块，文件路径用行内代码
- 待办用 `- [ ]` / `- [x]`
- 参考同目录下其他文档的结构保持一致

### 5. 创建文档

```bash
lark-cli docs +create \
  --title "<文档标题>" \
  --wiki-node "<父节点TOKEN>" \
  --markdown "$MARKDOWN_CONTENT" \
  --as user
```

### 6. 权限处理

创建 wiki 节点需要 `wiki:wiki` 或 `wiki:node:create` scope：

```bash
lark-cli auth login --scope "wiki:wiki" --as user
```

授权流程为 device-flow，会输出浏览器链接 + user_code，需用户手动打开完成。

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

## 注意事项

- Wiki URL 中的 token 是 wiki_token，查询节点信息可获取 obj_token 和 space_id
- `docs +create --wiki-node` 在该节点下创建子节点
- 较长文档建议配合 `docs +update --mode append` 分段创建
- lark-cli 参数用 `--params` JSON 格式，不支持 `--token` 直接传参
- 权限不足时走 device-flow 授权，输出链接让用户打开

## 相关条目

- [[pitfalls/environment/lark-cli-login-shell-path-mismatch|lark-cli 路径不匹配]]
