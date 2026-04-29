#!/usr/bin/env python3
"""
AgentFlow Phase Reminder — PostToolUse hook
在代码修改（Write/Edit）后，如果缺少 current_phase.md，提醒执行 pre-flight-check。

这是一个轻量提醒（不阻断），确保 agent 不会忘记初始化流程。
"""
import json
import os
import sys


def main():
    # 只在 agent-flow 项目中生效
    if not os.path.isdir(".agent-flow"):
        sys.exit(0)

    try:
        input_data = json.loads(sys.stdin.read())
    except Exception:
        sys.exit(0)

    tool_name = input_data.get("tool_name", "")
    if tool_name not in ("Write", "Edit"):
        sys.exit(0)

    # 检查 current_phase.md 是否存在
    has_phase = False
    phase_path = os.path.join(".agent-flow/state", "current_phase.md")
    if os.path.isfile(phase_path):
        has_phase = True

    if not has_phase:
        print("[REMINDER] No current_phase.md found. Did you run pre-flight-check?")

    sys.exit(0)


if __name__ == "__main__":
    main()
