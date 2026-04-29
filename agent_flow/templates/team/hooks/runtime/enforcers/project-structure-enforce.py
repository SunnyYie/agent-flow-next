#!/usr/bin/env python3
"""
AgentFlow Project Structure Enforce — PreToolUse hook
强制 agent 在搜索项目源码前，先读取 project-structure.md 获取 Tag→Directory 索引。
避免 agent 不了解项目结构就盲目搜索代码，浪费上下文。

核心机制：
- 拦截 Grep 搜索源码目录的操作
- 检查 .agent-flow/state/.project-structure-read 标记
- 无标记 = 没读索引 = 阻断，要求先读
- 有标记 = 已读索引 = 放行

标记由 context-guard.py (PostToolUse) 在读取 project-structure.md 时自动创建。
"""
import json
import os
import sys


STRUCTURE_READ_MARKER = ".agent-flow/state/.project-structure-read"

# 源码目录特征（搜索这些路径时需要先读索引）
SOURCE_INDICATORS = [
    "src/", "rn/", "lib/", "app/", "pages/",
    "components/", "views/", "routes/", "modules/",
]

# 搜索工具允许的非源码路径（不触发拦截）
ALLOWED_SEARCH_PREFIXES = [
    "~/.agent-flow/",
    ".agent-flow/skills/",
    ".agent-flow/wiki/",
    "~/.claude/",
]


def is_source_code_search(search_path: str) -> bool:
    """判断搜索路径是否针对项目源码目录"""
    if not search_path:
        # 无路径 = 全局搜索，需要拦截
        return True

    # 排除知识库路径
    for prefix in ALLOWED_SEARCH_PREFIXES:
        if search_path.startswith(prefix) or search_path.startswith(prefix.replace("~/", "")):
            return False

    # 检查是否包含源码目录特征
    for indicator in SOURCE_INDICATORS:
        if indicator in search_path:
            return True

    # 如果搜索路径就是项目根目录的子目录（不是 . 开头的配置目录）
    # 也视为源码搜索
    first_part = search_path.split("/")[0] if "/" in search_path else search_path
    if first_part and not first_part.startswith("."):
        return True

    return False


def main():
    # 只在 agent-flow 项目中生效
    if not os.path.isdir(".agent-flow"):
        sys.exit(0)

    # 如果 project-structure.md 不存在，不强制（项目可能没初始化）
    if not os.path.isfile(".agent-flow/wiki/project-structure.md"):
        sys.exit(0)

    # 已读过标记，放行
    if os.path.isfile(STRUCTURE_READ_MARKER):
        sys.exit(0)

    # 读取 hook 输入
    try:
        input_data = json.loads(sys.stdin.read())
    except Exception:
        sys.exit(0)

    tool_name = input_data.get("tool_name", "")
    tool_input = input_data.get("tool_input", {})

    # 只拦截 Grep 工具（代码搜索）
    if tool_name != "Grep":
        sys.exit(0)

    # 检查搜索路径
    search_path = tool_input.get("path", "")

    if is_source_code_search(search_path):
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

    sys.exit(0)


if __name__ == "__main__":
    main()
