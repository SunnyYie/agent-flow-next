#!/usr/bin/env python3
"""Require local wiki/skill search evidence before running WebSearch.

PreToolUse hook: blocks direct WebSearch when project/team knowledge has not been
searched recently. This enforces "local first, web fallback" workflow.
"""

from __future__ import annotations

import json
import os
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from contract_utils import find_project_root, NO_RETRY_LINE, UNBLOCK_SUFFIX

MAX_AGE_SECONDS = 1800


def _marker_candidates(project_root, marker_name: str):
    return [
        project_root / ".agent-flow" / "state" / marker_name,
    ]


def _has_recent_marker(project_root, marker_name: str, max_age: int = MAX_AGE_SECONDS) -> bool:
    now = time.time()
    for marker in _marker_candidates(project_root, marker_name):
        if not marker.is_file():
            continue
        try:
            if now - marker.stat().st_mtime <= max_age:
                return True
        except OSError:
            continue
    return False


def main() -> None:
    project_root = find_project_root()
    if project_root is None:
        sys.exit(0)

    if os.getenv("AGENT_FLOW_ALLOW_DIRECT_WEBSEARCH", "") == "1":
        sys.exit(0)

    try:
        input_data = json.loads(sys.stdin.read() or "{}")
    except Exception:
        sys.exit(0)

    tool_name = str(input_data.get("tool_name", ""))
    if tool_name != "WebSearch":
        sys.exit(0)

    has_wiki_search = _has_recent_marker(project_root, ".wiki-search-done")
    has_skill_search = _has_recent_marker(project_root, ".subtask-guard-done")

    if has_wiki_search and has_skill_search:
        sys.exit(0)

    print(
        "[AgentFlow BLOCKED] WebSearch 前缺少本地知识检索证据。\n"
        f"{NO_RETRY_LINE}\n\n"
        "✅ 解除方法：\n"
        "  1. 先检索项目/团队 wiki（.agent-flow/wiki + team wiki）\n"
        "  2. 再检索项目/团队 skills（.agent-flow/skills + team skills）\n"
        "  3. 本地无结果时再执行 WebSearch\n"
        f"  {UNBLOCK_SUFFIX}"
    )
    sys.exit(2)


if __name__ == "__main__":
    main()
