#!/usr/bin/env python3
"""Ensure project bootstrap files exist before deeper workflow checks run."""

from pathlib import Path


def main() -> None:
    try:
        from agent_flow.core.config import ensure_project_claude_md, ensure_project_mcp_config
        from agent_flow.core.state_contract import find_project_root
    except Exception:
        return

    project_root = find_project_root(Path.cwd()) or Path.cwd()
    has_workflow = (project_root / ".agent-flow").exists() or (project_root / ".dev-workflow").exists()
    if not has_workflow:
        return

    ensure_project_claude_md(project_root)
    ensure_project_mcp_config(project_root)


if __name__ == "__main__":
    main()
