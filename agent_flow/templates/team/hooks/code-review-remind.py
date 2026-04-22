#!/usr/bin/env python3
"""
AgentFlow Code Review Reminder — PostToolUse hook
在代码文件修改（Write/Edit）后，提醒 Agent 启动 code-reviewer Agent。

按改动量分级：
- 小改动（1-2 文件，<50 行变更）：软提醒（不阻断）
- 大改动（3+ 文件或 50+ 行变更）：强烈提醒（附 code-review skill 关键步骤）
- Complex 任务：强制提醒

仅在 pre-flight 完成后生效。
"""
import json
import os
import sys


CODE_EXTENSIONS = {
    ".ts", ".tsx", ".js", ".jsx", ".py", ".rs", ".go", ".java", ".kt",
    ".swift", ".m", ".h", ".c", ".cpp", ".rb", ".php", ".vue", ".svelte",
    ".css", ".scss", ".less", ".html", ".sql", ".graphql",
    ".sh", ".bash", ".zsh",
}

CODE_FILENAMES = {
    "package.json", "tsconfig.json", "Makefile", "Dockerfile",
    "Podfile", "Gemfile", "build.gradle", "settings.gradle",
}

ALLOWED_PATH_PREFIXES = (".agent-flow", ".dev-workflow", ".claude")

# 代码修改计数文件
CODE_CHANGE_COUNTER = ".agent-flow/state/.code-change-count"

# code-review 已执行标记
CODE_REVIEW_MARKER = ".agent-flow/state/.code-review-done"


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


def get_complexity_level() -> str:
    complexity_file = ".agent-flow/state/.complexity-level"
    if not os.path.isfile(complexity_file):
        return "medium"
    try:
        with open(complexity_file, "r", encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if line.startswith("level="):
                    level = line.split("=", 1)[1].strip().lower()
                    if level in ("simple", "medium", "complex"):
                        return level
    except Exception:
        pass
    return "medium"


def increment_code_change_count():
    """记录代码修改次数"""
    count = 0
    if os.path.isfile(CODE_CHANGE_COUNTER):
        try:
            with open(CODE_CHANGE_COUNTER, "r") as f:
                count = int(f.read().strip())
        except Exception:
            count = 0
    count += 1
    os.makedirs(os.path.dirname(CODE_CHANGE_COUNTER), exist_ok=True)
    with open(CODE_CHANGE_COUNTER, "w") as f:
        f.write(str(count))
    return count


def has_code_review_marker() -> bool:
    return os.path.isfile(CODE_REVIEW_MARKER)


def main():
    # 只在 agent-flow 项目中生效
    if not os.path.isdir(".agent-flow") and not os.path.isdir(".dev-workflow"):
        sys.exit(0)

    # 读取 hook 输入
    try:
        input_data = json.loads(sys.stdin.read())
    except Exception:
        sys.exit(0)

    tool_name = input_data.get("tool_name", "")
    tool_input = input_data.get("tool_input", {})

    # 只处理 Write 和 Edit
    if tool_name not in ("Write", "Edit"):
        sys.exit(0)

    file_path = tool_input.get("file_path", "")
    if not file_path or not is_code_file(file_path):
        sys.exit(0)

    # 已执行 code-review，跳过
    if has_code_review_marker():
        sys.exit(0)

    # 记录代码修改次数
    change_count = increment_code_change_count()
    complexity = get_complexity_level()

    # 判断改动级别
    is_large_change = change_count >= 3  # 3+ 次代码修改视为大改动
    is_complex = complexity == "complex"

    if is_complex and is_large_change:
        # Complex + 大改动：强烈提醒
        print(
            f"[AgentFlow CODE-REVIEW] 代码已修改 {change_count} 次，必须启动 code-reviewer Agent！\n"
            f"当前复杂度: Complex\n\n"
            f"执行方式:\n"
            f"  Agent({{\n"
            f"    description: '代码审查',\n"
            f"    subagent_type: 'general-purpose',\n"
            f"    prompt: '按 code-review skill 四柱框架(Correctness/Security/Maintainability/Performance)\\n"
            f"             审查最近的代码变更。git diff 查看变更内容。'\n"
            f"  }})\n\n"
            f"审查完成后创建标记: .agent-flow/state/.code-review-done"
        )
    elif is_large_change:
        # 大改动：标准提醒
        print(
            f"[AgentFlow CODE-REVIEW] 代码已修改 {change_count} 次，建议启动 code-reviewer Agent。\n"
            f"agents.md 规定: 代码刚写完/修改后 → 使用 code-reviewer agent\n"
            f"执行方式: Agent({{description: '代码审查', subagent_type: 'general-purpose', ...}})"
        )
    elif change_count == 1:
        # 首次修改：轻提醒
        print(
            f"[AgentFlow CODE-REVIEW] 代码已修改。修改完成后记得启动 code-reviewer Agent 审查。"
        )

    sys.exit(0)


if __name__ == "__main__":
    main()
