#!/usr/bin/env python3
"""
AgentFlow Error Search Reminder — PostToolUse hook
当 Bash 命令执行失败时，提醒 Agent 搜索 Skill/Wiki 寻找解决方案。
强制禁止：自行推测原因、盲目重试、忽略错误继续执行。

两轮循环上限：连续失败 2 次后，必须暂停并请求人工决策。
成功执行时自动重置计数器。

对应 Pitfall: skip-search-before-execute.md (confidence 1.0)
对应 Pitfall: skill-first-before-action.md (confidence 0.95)
"""
import json
import os
import sys

ERROR_COUNT_FILE = ".agent-flow/state/.error-count"
MAX_ERROR_ROUNDS = 2  # 两轮循环上限

# 错误指示关键词
ERROR_INDICATORS = [
    "Error:", "error:", "ERROR:",
    "Failed", "failed", "FAILED",
    "exit code: 1", "exit code: 2", "exit code: 127",
    "404 Not Found", "404", "500", "403 Forbidden",
    "not found", "Not Found",
    "Permission denied", "permission denied",
    "Cannot find", "cannot find",
    "No such file", "no such file",
    "fatal:", "Fatal:",
    "exception", "Exception",
    "Traceback",
]


def read_error_count() -> int:
    """读取连续错误计数"""
    try:
        if os.path.isfile(ERROR_COUNT_FILE):
            with open(ERROR_COUNT_FILE, "r") as f:
                return int(f.read().strip())
    except Exception:
        pass
    return 0


def write_error_count(count: int):
    """写入连续错误计数"""
    try:
        os.makedirs(os.path.dirname(ERROR_COUNT_FILE), exist_ok=True)
        with open(ERROR_COUNT_FILE, "w") as f:
            f.write(str(count))
    except Exception:
        pass


def reset_error_count():
    """重置错误计数（成功执行时调用）"""
    try:
        if os.path.isfile(ERROR_COUNT_FILE):
            os.remove(ERROR_COUNT_FILE)
    except Exception:
        pass


def main():
    # 只在 agent-flow 项目中生效
    if not os.path.isdir(".agent-flow") and not os.path.isdir(".dev-workflow"):
        sys.exit(0)

    # 读取 hook 输入
    try:
        input_data = json.loads(sys.stdin.read())
    except Exception:
        sys.exit(0)

    tool_name = input_data.get("tool_name", "")

    # 只对 Bash 工具进行错误检测
    if tool_name != "Bash":
        sys.exit(0)

    # 检查工具结果是否包含错误
    tool_result = str(input_data.get("tool_result", ""))
    tool_input = input_data.get("tool_input", {})
    stderr = str(tool_input.get("stderr", ""))
    combined_output = tool_result + "\n" + stderr

    has_error = any(indicator in combined_output for indicator in ERROR_INDICATORS)

    if has_error:
        # 增加错误计数
        count = read_error_count() + 1
        write_error_count(count)

        command = tool_input.get("command", "unknown")

        if count >= MAX_ERROR_ROUNDS:
            # 两轮循环上限 → 强制暂停，请求人工决策
            print(
                f"[AgentFlow ESCALATE] 思维链已循环 {count} 次仍未解决，必须暂停！\n"
                f"━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n"
                f"命令: {command[:80]}\n"
                f"连续失败次数: {count}/{MAX_ERROR_ROUNDS}\n"
                f"━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n"
                f"⛔ 强制暂停执行，必须请求人工决策:\n"
                f"  1. 向用户详细描述遇到的问题\n"
                f"  2. 列出已尝试的方案和失败原因\n"
                f"  3. 提出可能的解决方案供用户选择\n"
                f"  4. 等待用户明确指示后才能继续\n"
                f"━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n"
                f"⚠️ 禁止: 自行推测新方案、继续尝试、跳过此问题"
            )
        else:
            # 第 1 次失败 → 搜索提醒
            print(
                f"[AgentFlow ERROR WARNING] 命令执行失败 (第{count}/{MAX_ERROR_ROUNDS}轮): {command[:80]}\n"
                f"━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n"
                f"⚠️ 严厉禁止以下行为:\n"
                f"  ❌ 自行推测原因并重试\n"
                f"  ❌ 凭经验猜测解决方案\n"
                f"  ❌ 忽略错误继续执行\n"
                f"━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n"
                f"✅ 必须执行以下步骤:\n"
                f"  1. Grep 搜索 ~/.agent-flow/skills/ 查找相关 Skill\n"
                f"  2. Grep 搜索 ~/.agent-flow/wiki/pitfalls/ 查找已知坑\n"
                f"  3. Grep 搜索 .agent-flow/skills/ 查找项目 Skill\n"
                f"  4. 找到匹配 → 严格按 Skill/经验执行\n"
                f"  5. 未找到 → 向用户描述问题并请求指导\n"
                f"━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n"
                f"⚠️ 再失败 {MAX_ERROR_ROUNDS - count} 次将强制暂停，请求人工决策"
            )
    else:
        # 成功执行 → 重置错误计数
        reset_error_count()

    sys.exit(0)


if __name__ == "__main__":
    main()
