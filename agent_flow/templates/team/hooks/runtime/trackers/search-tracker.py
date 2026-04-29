#!/usr/bin/env python3
"""
AgentFlow Search Tracker — PostToolUse hook
当 Agent 搜索了 Skills/Wiki/Soul/Web 知识库时，创建搜索标记文件。
subtask-guard-enforce.py 在执行前检查此标记，确保"搜索先行"。

v2.0 新增：当搜索命中 wiki/pitfalls 中的工具相关条目时，
创建 .tool-wiki-read 标记，供 tool-precheck-guard.py 检查。

思维链保障机制：
  搜索了 → 有标记 → 允许执行
  没搜索 → 无标记 → 阻断执行，强制先搜索

工具知识预检机制：
  搜索了 wiki/pitfalls 中的工具条目 → 有 .tool-wiki-read 标记 → 不再提醒
  没搜索 → 无标记 → tool-precheck-guard.py 提醒
"""
import json
import os
import sys
import time

MARKER_FILE = ".agent-flow/state/.search-done"
TOOL_WIKI_READ_MARKER = ".agent-flow/state/.tool-wiki-read"
SUBTASK_GUARD_MARKER = ".agent-flow/state/.subtask-guard-done"
WIKI_SEARCH_MARKER = ".agent-flow/state/.wiki-search-done"

# 默认需要监控的 critical tools
DEFAULT_CRITICAL_TOOLS = ["lark-cli", "glab", "gh", "docker"]

# 搜索路径关键词 — 只有搜索这些路径才算有效知识搜索
VALID_SEARCH_KEYWORDS = [
    "agent-flow/skills",
    "agent-flow/wiki",
    "agent-flow/memory",
    "Soul",
    "soul.md",
]

# Skills 搜索路径关键词 — 搜索 skills 时同时创建 subtask-guard 标记
SKILLS_SEARCH_KEYWORDS = [
    "agent-flow/skills",
]

# Wiki 搜索路径关键词 — 搜索 wiki 时同时创建 wiki-search 标记
WIKI_SEARCH_KEYWORDS = [
    "agent-flow/wiki",
]

# 这些工具总是视为知识搜索
ALWAYS_SEARCH_TOOLS = {"WebSearch", "Agent", "Skill"}


def load_critical_tools() -> list:
    """从 config.yaml 加载 critical_tools 列表"""
    config_file = os.path.expanduser("~/.agent-flow/config.yaml")
    if not os.path.isfile(config_file):
        return DEFAULT_CRITICAL_TOOLS
    try:
        with open(config_file, "r", encoding="utf-8") as f:
            in_critical_tools = False
            tools = []
            for line in f:
                stripped = line.strip()
                if stripped.startswith("critical_tools:"):
                    in_critical_tools = True
                    continue
                if in_critical_tools:
                    if stripped.startswith("- "):
                        tool_name = stripped[2:].strip().strip('"').strip("'")
                        tools.append(tool_name)
                    elif not stripped.startswith("#") and stripped and not stripped.startswith("-"):
                        if not stripped.startswith("  "):
                            break
            return tools if tools else DEFAULT_CRITICAL_TOOLS
    except Exception:
        return DEFAULT_CRITICAL_TOOLS


def is_valid_search(tool_name: str, tool_input: dict) -> bool:
    """判断工具使用是否为有效的知识库搜索"""
    # WebSearch, Agent(Explore), Skill 总是算搜索
    if tool_name in ALWAYS_SEARCH_TOOLS:
        return True

    # 对 Grep/Read/Glob，检查是否搜索知识库路径
    search_param = ""
    if tool_name == "Grep":
        search_param = tool_input.get("path", "")
    elif tool_name == "Read":
        search_param = tool_input.get("file_path", "")
    elif tool_name == "Glob":
        search_param = tool_input.get("path", "")

    return any(kw in search_param for kw in VALID_SEARCH_KEYWORDS)


def check_tool_wiki_read(tool_name: str, tool_input: dict, critical_tools: list):
    """检查搜索是否涉及 critical tools 的 wiki 条目，创建 .tool-wiki-read 标记"""
    # 获取搜索路径和内容
    search_path = ""
    search_pattern = ""
    if tool_name == "Grep":
        search_path = tool_input.get("path", "")
        search_pattern = tool_input.get("pattern", "")
    elif tool_name == "Read":
        search_path = tool_input.get("file_path", "")
    elif tool_name == "Glob":
        search_path = tool_input.get("path", "")

    # 检查是否搜索了 pitfalls 目录
    if "pitfalls" not in search_path and "pitfalls" not in search_pattern:
        return

    # 检查搜索内容是否涉及 critical tools
    combined = f"{search_path} {search_pattern}".lower()
    for tool in critical_tools:
        if tool.lower() in combined:
            # 创建 .tool-wiki-read 标记
            os.makedirs(os.path.dirname(TOOL_WIKI_READ_MARKER), exist_ok=True)
            timestamp = time.strftime("%Y-%m-%dT%H:%M:%S")

            # 读取现有标记，避免重复
            existing_entries = {}
            if os.path.isfile(TOOL_WIKI_READ_MARKER):
                try:
                    with open(TOOL_WIKI_READ_MARKER, "r", encoding="utf-8") as f:
                        for line in f:
                            parts = line.strip().split("|")
                            if len(parts) >= 1:
                                existing_entries[parts[0]] = line.strip()
                except Exception:
                    pass

            # 更新或添加条目
            existing_entries[tool] = f"{tool}|{timestamp}|{search_path}"

            with open(TOOL_WIKI_READ_MARKER, "w", encoding="utf-8") as f:
                for entry in existing_entries.values():
                    f.write(entry + "\n")


def main():
    # 只在 agent-flow 项目中生效
    if not os.path.isdir(".agent-flow"):
        sys.exit(0)

    # 读取 hook 输入
    try:
        input_data = json.loads(sys.stdin.read())
    except Exception:
        sys.exit(0)

    tool_name = input_data.get("tool_name", "")
    tool_input = input_data.get("tool_input", {})

    if is_valid_search(tool_name, tool_input):
        # 创建/更新搜索标记
        os.makedirs(os.path.dirname(MARKER_FILE), exist_ok=True)
        with open(MARKER_FILE, "w") as f:
            f.write(f"tool={tool_name}\ntime={time.time()}\n")

        # 检查是否搜索了 skills/ 目录 → 自动创建 subtask-guard 标记
        search_param = ""
        if tool_name == "Grep":
            search_param = tool_input.get("path", "")
        elif tool_name == "Read":
            search_param = tool_input.get("file_path", "")
        elif tool_name == "Glob":
            search_param = tool_input.get("path", "")

        if any(kw in search_param for kw in SKILLS_SEARCH_KEYWORDS):
            os.makedirs(os.path.dirname(SUBTASK_GUARD_MARKER), exist_ok=True)
            with open(SUBTASK_GUARD_MARKER, "w") as f:
                f.write(f"tool={tool_name}\ntime={time.time()}\npath={search_param}\n")

        # 检查是否搜索了 wiki/ 目录 → 创建 wiki-search 标记
        if any(kw in search_param for kw in WIKI_SEARCH_KEYWORDS):
            os.makedirs(os.path.dirname(WIKI_SEARCH_MARKER), exist_ok=True)
            with open(WIKI_SEARCH_MARKER, "w") as f:
                f.write(f"tool={tool_name}\ntime={time.time()}\npath={search_param}\n")

    # 检查是否需要创建 .tool-wiki-read 标记
    critical_tools = load_critical_tools()
    check_tool_wiki_read(tool_name, tool_input, critical_tools)

    sys.exit(0)


if __name__ == "__main__":
    main()
