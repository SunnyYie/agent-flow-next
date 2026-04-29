---
name: hook-project-root-mismatch
type: pitfall
module: workflow
status: verified
confidence: 0.9
created: 2026-04-29
tags: [hook, agent-flow, find_project_root, sub-package, monorepo, preflight]
---

# Hook find_project_root 误判：子包 .agent-flow 优先于仓库根

## 问题描述

在 monorepo 项目中，`contract_utils.py` 的 `find_project_root()` 从 CWD 向上遍历，返回**第一个**包含 `.agent-flow` 的目录。当子包下也存在 `.agent-flow` 时（即使是 hook 自动创建的空目录），子包路径会优先于仓库根路径被选中。

## 典型表现

1. 仓库根 `/repo/.agent-flow/` 包含完整的 state 文件（`current_phase.md`、`.complexity-level`、`task-list.md`）
2. 子包 `/repo/packages/pkg-a/.agent-flow/state/` 被 hook 自动创建（仅含标记文件如 `.subtask-guard-state.json`）
3. `preflight-enforce.py` 调用 `find_project_root()` → 返回子包路径 → 找不到 `current_phase.md` → 阻断所有代码修改
4. 即使手动删除子包 `.agent-flow`，hook 下次执行又会重建它，问题循环出现

## 根因

1. `find_project_root()` 的设计目标是"就近查找"，没有考虑 monorepo 中多级目录结构
2. Hook 的副作用：某些 hook 在执行时会写入标记文件到 `find_project_root()` 返回的路径，如果该路径是子包，就会在那里创建 `.agent-flow/state/` 目录
3. 删除子包 `.agent-flow` 不是永久解决方案——hook 会自动重建

## 解决方案

### 方案 A：双写 state 文件（临时）

同步关键 state 文件到子包 `.agent-flow/state/`：
```bash
cp .agent-flow/state/current_phase.md packages/pkg-a/.agent-flow/state/
cp .agent-flow/state/.complexity-level packages/pkg-a/.agent-flow/state/
```

**缺点**：两份 state 需要手动同步，容易遗忘。

### 方案 B：修改 find_project_root 优先选 git root（根治）

```python
def find_project_root(start=None):
    current = Path(start or os.getcwd()).resolve()
    git_root = None
    for candidate in [current, *current.parents]:
        if (candidate / ".git").exists():
            git_root = candidate
        if git_root and (git_root / ".agent-flow").exists():
            return git_root  # 优先 git root 下的 .agent-flow
    # fallback: 最近的 .agent-flow
    for candidate in [current, *current.parents]:
        if (candidate / ".agent-flow").exists():
            return candidate
    return None
```

### 方案 C：子包添加 .agent-flow 到 .gitignore

避免子包 `.agent-flow` 进入版本控制，但不阻止 hook 创建。

## 适用场景

- monorepo 项目中工作目录是子包（如 `packages/xxx`）而非仓库根
- 使用 agent-flow workflow-guards hooks 的项目
- 在 `.claude/settings.local.json` 中配置了 hook 的 Claude Code 项目

## 相关条目
- [[hook-stderr-silent-block|Hook 阻断时无错误信息]]
