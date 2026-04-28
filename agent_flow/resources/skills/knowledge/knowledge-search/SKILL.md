---
name: knowledge-search
version: 2.0.0
trigger: 搜索技能, 查找知识, 搜索完成, 工具发现, skill search, 查找方案, 安装工具, web-research, source-code-research, 代码调研
confidence: 0.95
abstraction: universal
created: 2026-04-14
updated: 2026-04-28
---

# Skill: Knowledge Search & Tool Discovery

> **统一检索入口**：本地知识检索 + Web 调研 + 开源源码调研 + 工具发现。  
> v2.0 已合并原 `research/web-research` 与 `research/source-code-research`。

## Trigger

- 需要查找已有方案、技能、经验时
- 需要使用某个工具但不确定是否已安装时
- 代码搜索完成，需要切分支开发时

## Procedure

### Step 1: 本地知识搜索（零成本，优先）

按以下顺序查找已有方案：

1. **Skills 主题查找**（快速路径，三级查找）：
   a. **主题枢纽**（O(1)）：`Read` 主题枢纽 `~/.agent-flow/skills/topics/{keyword}.md`
      → 存在则直接获取该主题所有相关技能链接
   b. **标签索引**（O(1)）：`Grep` 标签索引 `~/.agent-flow/skills/TAG-INDEX.md`
      → 按标签精确匹配技能路径
   c. **全量搜索**（兜底）：`Grep` 搜索 `~/.agent-flow/skills/` 和 `.agent-flow/skills/`
2. **Soul**: `Grep` 搜索 `.agent-flow/memory/main/Soul.md`
3. **Wiki 主题查找**（快速路径，三级查找）：
   a. **主题枢纽**（O(1)）：`Read` 主题枢纽 `~/.agent-flow/wiki/topics/{keyword}.md`
      → 存在则直接获取该主题所有相关文档链接
   b. **标签索引**（O(1)）：`Grep` 标签索引 `~/.agent-flow/wiki/TAG-INDEX.md`
      → 按标签精确匹配文档路径
   c. **全量搜索**（兜底）：`Grep` 搜索 `~/.agent-flow/wiki/` 和 `.agent-flow/wiki/` 全目录
4. **找到匹配** → 按 Procedure 执行，跳到 Step 4

### Step 2: 外部搜索（有成本，本地无果时）

| 工具 | 用途 | 方式 |
|------|------|------|
| gh CLI | 搜索GitHub开源实现 | `gh search repos/code` |
| WebSearch | 技术文档、最佳实践 | WebSearch工具 |
| find-docs | 权威技术文档 | find-docs skill |

**搜索技巧**：
- 技术搜索带年份避免过时信息
- 关键结论至少两个来源确认
- 排除营销和过时内容

### Step 3: 源码调研（实现问题场景）

当问题属于“需要参考开源实现方式”，在 Step 2 基础上执行：

1. `gh search repos "{关键词}" --limit 5`（候选项目）
2. `gh search code "{关键词}" --limit 10`（实现片段）
3. 选 1-2 个最近仍活跃的项目阅读关键模块
4. 提炼“可借鉴模式”，禁止直接复制代码
5. 记录检索路径和结论，便于复现

**重点观察项**：
- 接口边界与抽象层次
- 错误处理与回退策略
- 测试覆盖方式
- 配置与扩展点设计

### Step 4: 工具发现（需要工具时）

1. **检测安装状态**：`which {tool_name}` 或 `{tool_name} --version`
2. **已安装** → 记录版本号，跳到 Step 4
3. **未安装** → WebSearch 搜索安装方案
4. **检查白名单**：
   - 白名单内（git, docker, npm, pip, python3, node, gh, uv, curl, wget, jq, yq）→ 自动安装
   - 需确认（lark-cli, cargo, brew, apt-get, yum, pipx, npx）→ 询问用户
   - 黑名单 → 拒绝并报告替代方案
5. **安装后三步记录**：验证安装 → 创建 Skill.md → 记录 Soul.md

### Step 5: 搜索完成后的标准动作

**搜索代码后立即行动**（线性执行，无分支）：

```text
搜索相关代码 → 分析结果
  ├─ 找到相关代码 → 定位修改点 → git pull --rebase → git checkout -b feat/xxx → 开始开发
  └─ 搜索不到字段 → 判定为新增字段 → git pull --rebase → git checkout -b feat/xxx → 开始开发
```

**关键判断规则**：
1. 搜索不到 = 新增 → 直接开发，不需要验证其他分支
2. 搜索到但不确定 = 问用户 → 不要自行 git 考古
3. 搜索到且确认 = 立即切分支开发

**禁止行为**：
- 搜索完后用 git log/show/diff 继续考古
- 搜索不到字段时去其他分支验证
- 不搜索就直接执行

## Rules

- 本地搜索零成本且高度相关，必须作为第一选择
- 先本地再外部，禁止一上来直接 WebSearch
- 调研代码只借鉴设计，不复制实现
- 安装前必须检查白名单
- 搜索完即行动，不做多余考古
- 不搜索就直接执行 = 臆断 = 质量差
