---
title: "权限梯度管理"
category: concept
module: workflow
agents: [main]
tags: [permissions, security, authorization]
confidence: 0.95
sources: [S1.4, S2.2]
created: 2026-04-11
updated: 2026-04-12
status: verified
---

# 权限梯度管理

> 按命令破坏性分级授权，低破坏性自动授权，高破坏性需用户确认

## 概念描述

阶段完成后，Main Agent回顾使用的Bash命令，按破坏性分级处理：

| 破坏性 | 特征 | 处理方式 |
|--------|------|----------|
| **低** | 只读、查询、测试、lint、本地构建 | 自动写入`.claude/settings.local.json`，通知用户 |
| **中** | 本地写入但不影响远程/他人 | 自动写入但输出变更内容供审阅 |
| **高** | 影响远程仓库、删除数据、系统级修改 | 必须用户明确授权后才写入 |

**低破坏性示例**：`pytest`, `ruff`, `python -c`, `git log`, `git diff`, `ls`, `pip list`

**中破坏性示例**：`git add`, `git commit`, `touch`, `mkdir`, `pip install -e .`

**高破坏性示例**：`git push --force`, `rm -rf`, `brew install`

**子Agent规则**：Executor/Verifier Agent遇到需要授权的命令时，只能在报告中记录并通知Main Agent，绝对禁止直接修改配置文件。

## 应用方式

1. 每个阶段完成后回顾使用的命令
2. 按破坏性分级写入配置
3. 子Agent无权写入配置文件，只能报告给Main Agent
4. 配置文件路径：`.claude/settings.local.json`

## 相关页面

- [[three-agent-model|三Agent协作模型]]
