#!/usr/bin/env python3
"""AgentFlow Project Init Guard — UserPromptSubmit hook

Detects whether the current project has been initialized with .agent-flow/.
If it doesn't exist, automatically runs `agent-flow init ` to bootstrap
the project before any workflow can proceed.
"""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path


def _find_project_root() -> Path | None:
    """Walk up from cwd to find a directory with .agent-flow/."""
    cwd = Path.cwd()
    for parent in [cwd, *cwd.parents]:
        if (parent / ".agent-flow").exists():
            return parent
        if parent == Path.home():
            break
    return None


def _is_git_repo() -> Path | None:
    """Find the git repo root, if any."""
    cwd = Path.cwd()
    for parent in [cwd, *cwd.parents]:
        if (parent / ".git").exists():
            return parent
        if parent == Path.home():
            break
    return None


def _run_init(project_dir: Path) -> bool:
    """Run agent-flow init in the project directory."""
    try:
        result = subprocess.run(
            ["agent-flow", "init"],
            cwd=str(project_dir),
            capture_output=True,
            text=True,
            timeout=60,
        )
        if result.returncode == 0:
            return True
        print(
            f"[AgentFlow] init failed (exit {result.returncode}): {result.stderr.strip()}",
            file=sys.stderr,
        )
        return False
    except FileNotFoundError:
        print(
            "[AgentFlow] agent-flow CLI not found. Install: pip install agent-flow",
            file=sys.stderr,
        )
        return False
    except subprocess.TimeoutExpired:
        print("[AgentFlow] init timed out after 60s", file=sys.stderr)
        return False
    except Exception as e:
        print(f"[AgentFlow] init error: {e}", file=sys.stderr)
        return False


def main() -> None:
    # Already initialized — nothing to do
    if _find_project_root() is not None:
        return

    # Determine where to initialize: git repo root or cwd
    project_dir = _is_git_repo() or Path.cwd()

    print(
        f"<system-reminder>\n"
        f"[AgentFlow] 项目未初始化 — 正在自动执行 agent-flow init ...\n"
        f"目标目录: {project_dir}\n"
        f"</system-reminder>"
    )

    success = _run_init(project_dir)

    if success:
        print(
            f"<system-reminder>\n"
            f"[AgentFlow] 自动初始化完成！已创建 .agent-flow/。\n"
            f"并已自动生成项目根目录 CLAUDE.md / AGENTS.md（若原先不存在）。\n"
            f"下一步：\n"
            f"1) 检查 .claude/settings*.json 是否已注册 agent-flow hooks\n"
            f"2) 检查关键工具是否可用（lark-cli/jira）\n"
            f"3) 按 Agent.md 启动协议工作。\n"
            f"</system-reminder>"
        )
    else:
        print(
            f"<system-reminder>\n"
            f"[AgentFlow] 自动初始化失败。请手动运行:\n"
            f"  agent-flow init\n"
            f"初始化完成后，按 Agent.md 启动协议工作。\n"
            f"</system-reminder>"
        )


if __name__ == "__main__":
    main()
