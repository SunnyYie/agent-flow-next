#!/usr/bin/env python3
"""
AgentFlow Subtask Guard Enforcer — PreToolUse hook
强制执行 subtask-guard：每次代码修改前检查是否执行了子任务搜索守卫。

核心机制：
  Agent 执行 subtask-guard → search-tracker.py 创建 .subtask-guard-done 标记
  Agent 执行代码修改 → 本 hook 检查标记 → 无标记 = 没搜索 = 阻断

按复杂度分级调整行为（v3.0）：
  Simple:  跳过检查（简单任务无需搜索先行）
  Medium:  标记有效期 30 分钟
  Complex: 标记有效期 20 分钟

仅对代码文件修改生效，不影响 agent-flow 文档、README 等。
"""
import json
import os
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from contract_utils import (
    NO_RETRY_LINE,
    UNBLOCK_SUFFIX,
    find_project_root,
    get_complexity_level,
    read_state_path,
)

# 各复杂度的标记有效期（秒）
MAX_AGE_MAP = {
    "medium": 1800,   # 30 分钟
    "complex": 1200,  # 20 分钟
}
DEFAULT_MAX_AGE = 1800

# 代码文件扩展名
CODE_EXTENSIONS = {
    ".ts", ".tsx", ".js", ".jsx", ".py", ".rs", ".go", ".java", ".kt",
    ".swift", ".m", ".h", ".c", ".cpp", ".rb", ".php", ".vue", ".svelte",
    ".css", ".scss", ".less", ".html", ".sql", ".graphql",
    ".sh", ".bash", ".zsh",
}

CODE_FILENAMES = {
    "package.json", "tsconfig.json", "Makefile", "Dockerfile",
    "Podfile", "Gemfile", "build.gradle", "settings.gradle",
    "app.json", "babel.config.js", "metro.config.js",
}

# 允许的路径前缀（不受 subtask-guard 检查限制）
ALLOWED_PATH_PREFIXES = (".agent-flow", ".dev-workflow", ".claude")

GUARD_PROMPT = f"""[AgentFlow BLOCKED] Subtask-guard 未执行 — 你没有在修改代码前搜索知识库！

{NO_RETRY_LINE}

✅ 解除方法：完成以下任一方案后，当前操作会自动放行：

  方案 A: 快速搜索（推荐，1步即可解除）
    Grep "{{关键词}}" .agent-flow/skills/ 或 ~/.agent-flow/skills/
    搜索后标记自动创建

  方案 B: 完整 subtask-guard 流程（新子任务时使用）
    1. Grep "{{关键词}}" .agent-flow/skills/
    2. Grep "{{关键词}}" ~/.agent-flow/skills/
    3. Grep "{{关键词}}" .agent-flow/memory/main/Soul.md
    4. Grep "{{关键词}}" .agent-flow/wiki/ + 全局wiki

  方案 C: 跨会话误触，执行任意搜索即可重置
    Grep "subtask" .agent-flow/

  {UNBLOCK_SUFFIX}
  标记有效期：Medium 30min / Complex 20min"""


def get_max_age(project_root) -> int:
    level = get_complexity_level(project_root)
    return MAX_AGE_MAP.get(level, DEFAULT_MAX_AGE)


def is_code_file(file_path: str) -> bool:
    for prefix in ALLOWED_PATH_PREFIXES:
        if prefix in file_path:
            return False
    _, ext = os.path.splitext(file_path)
    if ext.lower() in (".md", ".txt", ".rst", ".adoc"):
        return False
    if ext.lower() in CODE_EXTENSIONS:
        return True
    if os.path.basename(file_path) in CODE_FILENAMES:
        return True
    return False


def has_valid_guard(project_root) -> bool:
    """检查是否有有效的搜索守卫标记（v2: 同时检查 .subtask-guard-done 和 .search-done）"""
    max_age = get_max_age(project_root)
    for marker in [
        read_state_path(project_root, ".subtask-guard-done"),
        read_state_path(project_root, ".search-done"),
    ]:
        if os.path.isfile(marker):
            try:
                mtime = os.path.getmtime(marker)
                age = time.time() - mtime
                if age < max_age:
                    return True
            except Exception:
                pass
    return False


def main():
    project_root = find_project_root()
    if project_root is None:
        sys.exit(0)

    # 低复杂度任务不需要搜索先行检查
    complexity = get_complexity_level(project_root)
    if complexity == "simple":
        sys.exit(0)

    phase_file = read_state_path(project_root, "current_phase.md")
    phase_found = os.path.isfile(phase_file) and os.path.getsize(phase_file) > 10
    if not phase_found:
        sys.exit(0)

    # 读取 hook 输入
    try:
        input_data = json.loads(sys.stdin.read())
    except Exception:
        sys.exit(0)

    tool_name = input_data.get("tool_name", "")
    tool_input = input_data.get("tool_input", {})

    # 只拦截 Write 和 Edit
    if tool_name not in ("Write", "Edit"):
        sys.exit(0)

    file_path = tool_input.get("file_path", "")
    if not file_path:
        sys.exit(0)

    # 只拦截代码文件
    if not is_code_file(file_path):
        sys.exit(0)

    # 检查 subtask-guard 标记
    if has_valid_guard(project_root):
        sys.exit(0)  # 已执行，放行

    # 无标记 → 阻断
    print(f"{GUARD_PROMPT}\n目标文件: {file_path}")
    sys.exit(2)


if __name__ == "__main__":
    main()
