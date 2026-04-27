---
name: lark-cli-login-shell-path-mismatch
type: pitfall
module: environment
status: active
confidence: 0.97
created: 2026-04-27
last_validated: 2026-04-27
tags: [environment, lark-cli, path, login-shell, keychain, feishu]
---

# lark-cli 在交互终端可用但子进程不可用

## 现象

- 用户在交互终端可执行 `lark-cli`。
- Agent 子进程执行时报 `command not found` 或后续认证异常。

## 复现证据

1. 非登录 shell 环境 PATH 缺少 `~/.npm-global/bin`，`which lark-cli` 失败。
2. 登录 shell (`zsh -lic`) 可命中：`/Users/sunyi/.npm-global/bin/lark-cli`。
3. 在本次需求链路中，修复 PATH 后进一步暴露真实阻塞：`keychain not initialized`（认证缺失）。

## 根因

- 子进程与用户交互终端加载的 shell 初始化文件不同，导致 PATH 不一致。
- 工具缺失与认证缺失是两个独立问题，前者会掩盖后者。

## 处置

1. 与用户环境对齐执行：`zsh -lic '<command>'`。
2. 先做三步健康检查：
   - `which lark-cli`
   - `lark-cli --version`
   - `lark-cli doctor`
3. 若 PATH 正常但仍失败，继续判定认证状态：
   - `lark-cli auth status`
   - `lark-cli auth list`

## 预防

- 涉及 `lark-cli`/`npm-global` 工具链时，先做环境探测再执行业务命令。
- 记录错误分层：`工具缺失`、`认证缺失`、`权限缺失`，避免误判。

## 相关条目

- [[wiki-doc-read|patterns/feishu/wiki-doc-read]]
- [[lark-cli-params|pitfalls/feishu/lark-cli-params]]
