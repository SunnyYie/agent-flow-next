#!/usr/bin/env python3
"""workflow-guard: gentle reflection reminder after execution loop."""

from __future__ import annotations

import sys
from pathlib import Path

MARKER = ".agent-flow/state/.plugin-search-done"


def _find_project_root() -> Path | None:
    cwd = Path.cwd().resolve()
    for candidate in [cwd, *cwd.parents]:
        if (candidate / ".agent-flow").exists() or (candidate / ".dev-workflow").exists():
            return candidate
    return None


def main() -> None:
    _ = sys.stdin.read()
    project_root = _find_project_root()
    if project_root is None:
        return
    if not (project_root / MARKER).is_file():
        return

    print(
        "<system-reminder>\n"
        "[workflow-guard] 若本轮实现已完成，请先做简短总结：\n"
        "- 做了什么\n"
        "- 为什么这么做\n"
        "- 还剩哪些风险或待确认项\n"
        "</system-reminder>"
    )


if __name__ == "__main__":
    main()
