#!/usr/bin/env python3
"""AgentFlow Agent Team Initializer — UserPromptSubmit hook

Initializes the Agent Team based on task complexity.

Logic:
  - Read .complexity-level from state directory
  - Simple (0-3): no injection, solo mode
  - Medium (4-6): inject search-only team config (Main + Searcher)
  - Complex (7-10): inject full-team config (Main + Searcher + Executor + Verifier)
  - Write agent-team-config.yaml to .agent-flow/state/

Output: <system-reminder> block with team configuration summary (or nothing for simple).
"""
from __future__ import annotations

import sys
from pathlib import Path


def _find_project_root() -> Path | None:
    cwd = Path.cwd()
    for parent in [cwd, *cwd.parents]:
        if (parent / ".agent-flow").exists() or (parent / ".dev-workflow").exists():
            return parent
        if parent == Path.home():
            break
    return None


def _bootstrap_import_path(project_root: Path) -> None:
    """Ensure ``agent_flow`` package is importable when hooks run from ~/.agent-flow/hooks."""
    candidates = [project_root, *project_root.parents]
    for candidate in candidates:
        if (candidate / "agent_flow").is_dir():
            candidate_str = str(candidate)
            if candidate_str not in sys.path:
                sys.path.insert(0, candidate_str)
            return


def _get_complexity_level(project_root: Path) -> str:
    """Read complexity level from .complexity-level file."""
    for state_dir in [".agent-flow/state", ".dev-workflow/state"]:
        path = project_root / state_dir / ".complexity-level"
        if path.is_file():
            try:
                for line in path.read_text(encoding="utf-8").splitlines():
                    stripped = line.strip()
                    if stripped.startswith("level="):
                        level = stripped.split("=", 1)[1].strip().lower()
                        if level in ("simple", "medium", "complex"):
                            return level
                    elif stripped in ("simple", "medium", "complex"):
                        return stripped
            except OSError:
                pass
    return ""


def main() -> None:
    try:
        _ = sys.stdin.read()
    except Exception:
        pass

    project_root = _find_project_root()
    if project_root is None:
        return

    _bootstrap_import_path(project_root)

    complexity = _get_complexity_level(project_root)
    if not complexity or complexity == "simple":
        return  # Simple tasks don't need team initialization

    try:
        from agent_flow.core.agent_team import AgentTeamConfig

        config = AgentTeamConfig.from_complexity(complexity)
        config.write(project_root)
    except Exception:
        # If agent_team module not available, fall back to manual injection
        return

    summary = config.injection_summary()
    if not summary:
        return

    if config.is_search_only():
        print(
            "<system-reminder>\n"
            "[agent-team-init]\n"
            f"{summary}\n\n"
            "Instruction: Activate Searcher sub-agent during THINK phase for knowledge retrieval.\n"
            "Searcher output: .agent-flow/artifacts/search-{id}-results.md\n"
            "Read its structured results before proceeding to PLAN.\n"
            "</system-reminder>"
        )
    elif config.is_full_team():
        parallel_info = ""
        if config.is_parallel_execution():
            parallel_info = f" ({config.parallel_executor_count()} parallel executors)"
        print(
            "<system-reminder>\n"
            "[agent-team-init]\n"
            f"{summary}\n\n"
            "Full team protocol:\n"
            "  1. THINK: dispatch Searcher → read search results\n"
            f"  2. EXECUTE: analyze task DAG → dispatch parallel Executors{parallel_info} → read L2 summaries\n"
            "  3. VERIFY: dispatch Verifier → dual acceptance with Main Agent\n"
            "Main Agent = coordinator only. Prohibited: direct search/implementation/verification.\n"
            "</system-reminder>"
        )


if __name__ == "__main__":
    main()
