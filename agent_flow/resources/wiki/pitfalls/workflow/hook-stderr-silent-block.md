---
name: hook-stderr-silent-block
type: pitfall
module: workflow
status: verified
confidence: 0.85
created: 2026-04-29
tags: [hook, stderr, debug, preflight, agent-flow, claude-code]
---

# Hook 阻断时无错误信息（No stderr output）

## 问题描述

agent-flow 的 Python hook（如 `preflight-enforce.py`）使用 `print()` + `sys.exit(2)` 输出阻断原因。但 Claude Code 捕获 hook 输出时，有时仅显示：

```
PreToolUse:Edit hook error: [python3 .../preflight-enforce.py]: No stderr output
```

而非预期的详细阻断原因（如 "Pre-flight 未完成，禁止修改代码文件"）。

## 典型表现

1. Hook 明确返回 exit code 2（阻断），但 Claude Code 不显示具体原因
2. 同一个 hook 脚本，有时能正确显示消息，有时只显示 "No stderr output"
3. 其他 hook（如 `thinking-chain-enforce.py`）有时能正确显示消息

## 根因

Python 的 `print()` 默认写入 stdout。Claude Code 对 hook 错误的捕获机制可能期望 stderr 输出，或存在管道缓冲问题导致 stdout 消息丢失。

## 解决方案

### 临时：手动运行 hook 查看实际输出

```bash
echo '{"tool_name":"Edit","tool_input":{"file_path":"/path/to/file"}}' | \
  python3 /path/to/.agent-flow/plugins/workflow-guards/hooks/{hook-name}.py 2>&1
```

### 长期：Hook 脚本输出到 stderr

方式一：统一重定向
```python
# 在 main() 开头添加
sys.stdout = sys.stderr
```

方式二：错误信息同时写 stderr
```python
def print_error(msg):
    print(msg, file=sys.stderr)
```

方式三：在 contract_utils.py 中提供统一的错误输出函数
```python
def hook_block(msg):
    """Hook 阻断输出，同时写 stdout 和 stderr"""
    print(msg)
    print(msg, file=sys.stderr)
    sys.exit(2)
```

## 适用场景

- 使用 agent-flow workflow-guards hooks 的 Claude Code 项目
- 任何通过 `sys.exit(2)` 返回阻断信号且使用 `print()` 输出消息的 hook

## 相关条目
- [[hook-project-root-mismatch|Hook find_project_root 误判]]
