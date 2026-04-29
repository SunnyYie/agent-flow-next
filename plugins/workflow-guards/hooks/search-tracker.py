#!/usr/bin/env python3
"""
AgentFlow Search Tracker — PostToolUse hook.
记录知识库搜索行为，为 thinking-chain-enforce 提供放行标记。
"""

from __future__ import annotations

import json
import sys
import time
from pathlib import Path

from contract_utils import find_project_root, reset_shared_search_session, write_state_path

DEFAULT_CRITICAL_TOOLS = ["lark-cli", "glab", "gh", "docker"]

VALID_SEARCH_KEYWORDS = [
    "agent-flow/skills",
    "agent-flow/wiki",
    "agent-flow/memory",
    ".agent-flow/skills",
    ".agent-flow/wiki",
    ".agent-flow/memory",
    "Soul",
    "soul.md",
]

SKILLS_SEARCH_KEYWORDS = [
    "agent-flow/skills",
    ".agent-flow/skills",
]

WIKI_SEARCH_KEYWORDS = [
    "agent-flow/wiki",
    ".agent-flow/wiki",
]

ALWAYS_SEARCH_TOOLS = {"WebSearch", "Agent", "Skill"}


def load_critical_tools(project_root: Path) -> list[str]:
    config_file = project_root / ".agent-flow" / "config.yaml"
    if not config_file.is_file():
        return DEFAULT_CRITICAL_TOOLS
    try:
        tools: list[str] = []
        in_section = False
        for raw_line in config_file.read_text(encoding="utf-8").splitlines():
            line = raw_line.strip()
            if line.startswith("critical_tools:"):
                in_section = True
                continue
            if not in_section:
                continue
            if line.startswith("- "):
                tools.append(line[2:].strip().strip('"').strip("'"))
                continue
            if line and not line.startswith("#") and not raw_line.startswith("  "):
                break
        return tools or DEFAULT_CRITICAL_TOOLS
    except OSError:
        return DEFAULT_CRITICAL_TOOLS


def is_valid_search(tool_name: str, tool_input: dict) -> bool:
    if tool_name in ALWAYS_SEARCH_TOOLS:
        return True

    search_param = ""
    if tool_name == "Grep":
        search_param = tool_input.get("path", "")
    elif tool_name == "Read":
        search_param = tool_input.get("file_path", "")
    elif tool_name == "Glob":
        search_param = tool_input.get("path", "")
    return any(keyword in search_param for keyword in VALID_SEARCH_KEYWORDS)


def _search_param(tool_name: str, tool_input: dict) -> str:
    if tool_name == "Grep":
        return tool_input.get("path", "")
    if tool_name == "Read":
        return tool_input.get("file_path", "")
    if tool_name == "Glob":
        return tool_input.get("path", "")
    return ""


def check_tool_wiki_read(project_root: Path, tool_name: str, tool_input: dict, critical_tools: list[str]) -> None:
    search_path = _search_param(tool_name, tool_input)
    search_pattern = tool_input.get("pattern", "") if tool_name == "Grep" else ""
    if "pitfalls" not in search_path and "pitfalls" not in search_pattern:
        return

    combined = f"{search_path} {search_pattern}".lower()
    hit_tools = [tool for tool in critical_tools if tool.lower() in combined]
    if not hit_tools:
        return

    marker_path = write_state_path(project_root, ".tool-wiki-read")
    marker_path.parent.mkdir(parents=True, exist_ok=True)

    existing: dict[str, str] = {}
    if marker_path.is_file():
        try:
            for line in marker_path.read_text(encoding="utf-8").splitlines():
                parts = line.strip().split("|")
                if parts and parts[0]:
                    existing[parts[0]] = line.strip()
        except OSError:
            existing = {}

    timestamp = time.strftime("%Y-%m-%dT%H:%M:%S")
    for tool in hit_tools:
        existing[tool] = f"{tool}|{timestamp}|{search_path}"
    marker_path.write_text("\n".join(existing.values()) + ("\n" if existing else ""), encoding="utf-8")


def main() -> None:
    project_root = find_project_root()
    if project_root is None:
        sys.exit(0)

    try:
        raw_input = sys.stdin.read()
        input_data = json.loads(raw_input) if raw_input else {}
    except Exception:
        sys.exit(0)

    tool_name = input_data.get("tool_name", "")
    tool_input = input_data.get("tool_input", {})
    search_param = _search_param(tool_name, tool_input)

    if is_valid_search(tool_name, tool_input):
        reset_shared_search_session(project_root, source=tool_name)
        marker_file = write_state_path(project_root, ".search-done")
        marker_file.parent.mkdir(parents=True, exist_ok=True)
        marker_file.write_text(f"tool={tool_name}\ntime={time.time()}\n", encoding="utf-8")

        if any(keyword in search_param for keyword in SKILLS_SEARCH_KEYWORDS):
            subtask_marker = write_state_path(project_root, ".subtask-guard-done")
            subtask_marker.write_text(
                f"tool={tool_name}\ntime={time.time()}\npath={search_param}\n",
                encoding="utf-8",
            )

        if any(keyword in search_param for keyword in WIKI_SEARCH_KEYWORDS):
            wiki_marker = write_state_path(project_root, ".wiki-search-done")
            wiki_marker.write_text(
                f"tool={tool_name}\ntime={time.time()}\npath={search_param}\n",
                encoding="utf-8",
            )

    check_tool_wiki_read(project_root, tool_name, tool_input, load_critical_tools(project_root))
    sys.exit(0)


if __name__ == "__main__":
    main()
