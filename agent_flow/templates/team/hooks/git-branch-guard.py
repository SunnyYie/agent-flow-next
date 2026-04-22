#!/usr/bin/env python3
"""
AgentFlow Git Branch Guard — PreToolUse hook
防止在 main/master/develop 分支上执行 git commit/push。

核心规则：保护分支上禁止直接提交，必须先创建 feature 分支。
仅拦截 Bash 工具中的 git commit/push 命令。
"""
import json
import subprocess
import sys


PROTECTED_BRANCHES = {"main", "master", "develop"}


def get_git_branch() -> str:
    """获取当前 git 分支名"""
    try:
        result = subprocess.run(
            ["git", "branch", "--show-current"],
            capture_output=True, text=True, timeout=5
        )
        return result.stdout.strip()
    except Exception:
        return ""


def main():
    try:
        input_data = json.loads(sys.stdin.read())
    except Exception:
        sys.exit(0)

    tool_name = input_data.get("tool_name", "")
    if tool_name != "Bash":
        sys.exit(0)

    command = input_data.get("tool_input", {}).get("command", "").strip()

    # 只拦截 git commit 和 git push
    if not (command.startswith("git commit") or command.startswith("git push")):
        sys.exit(0)

    branch = get_git_branch()
    if branch in PROTECTED_BRANCHES:
        print(
            f"[BLOCKED] Git commit/push on protected branch: {branch}\n"
            f"Do not retry — the same action will be blocked again.\n\n"
            f"Create a feature branch first, then retry:\n"
            f"  git pull --rebase && git checkout -b feat/xxx"
        )
        sys.exit(2)

    sys.exit(0)


if __name__ == "__main__":
    main()
