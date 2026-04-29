#!/usr/bin/env python3
"""
AgentFlow Project Structure Enforce — PreToolUse hook.
在搜索项目源码前，强制先读取 project-structure 索引。
"""

from __future__ import annotations

import json
import sys

from contract_utils import find_project_root, read_state_path

SOURCE_INDICATORS = [
    "src/",
    "rn/",
    "lib/",
    "app/",
    "pages/",
    "components/",
    "views/",
    "routes/",
    "modules/",
]

ALLOWED_SEARCH_KEYWORDS = [
    "/.agent-flow/",
    "/.claude/",
    ".agent-flow/skills/",
    ".agent-flow/wiki/",
    ".agent-flow/memory/",
    "~/.agent-flow/",
    "~/.claude/",
]


def is_source_code_search(search_path: str) -> bool:
    if not search_path:
        return True

    normalized = search_path.replace("\\", "/")
    if any(keyword in normalized for keyword in ALLOWED_SEARCH_KEYWORDS):
        return False

    if any(indicator in normalized for indicator in SOURCE_INDICATORS):
        return True

    first_part = normalized.split("/")[0] if "/" in normalized else normalized
    return bool(first_part and not first_part.startswith("."))


def main() -> None:
    project_root = find_project_root()
    if project_root is None:
        sys.exit(0)

    structure_file = project_root / ".agent-flow" / "wiki" / "project-structure.md"
    if not structure_file.is_file():
        sys.exit(0)

    read_marker = read_state_path(project_root, ".project-structure-read")
    if read_marker.is_file():
        sys.exit(0)

    try:
        input_data = json.loads(sys.stdin.read())
    except Exception:
        sys.exit(0)

    if input_data.get("tool_name", "") != "Grep":
        sys.exit(0)

    search_path = input_data.get("tool_input", {}).get("path", "")
    if not is_source_code_search(search_path):
        sys.exit(0)

    print(
        "[AgentFlow BLOCKED] 你正在搜索项目源码，但还未读取项目结构索引！\n"
        "\n"
        "⛔ 不要重试当前操作！重复同样的操作只会再次被拦截。\n"
        "\n"
        "✅ 解除方法：\n"
        "  Read .agent-flow/wiki/project-structure.md\n"
        "  → 找到需求关键词对应的 Tag → 定位到代码目录\n"
        "  → 再在目标目录内搜索具体组件\n"
        "  读取后标记自动创建，后续搜索不再拦截。\n"
        "  完成后，当前操作会自动放行。"
    )
    sys.exit(2)


if __name__ == "__main__":
    main()
