#!/usr/bin/env python3
"""
AgentFlow Dev Workflow Enforcer — PreToolUse hook.
强制执行开发流程铁律（pre-flight 之后也持续生效）。
"""

from __future__ import annotations

import json
import os
import subprocess
import sys
import time
from pathlib import Path

from contract_utils import (
    NO_RETRY_LINE,
    UNBLOCK_SUFFIX,
    detect_plan_format,
    find_project_root,
    get_complexity_level,
    read_state_path,
    structured_marker_exists,
    write_state_path,
)

PROTECTED_BRANCHES = {"main", "master", "develop"}

CODE_EXTENSIONS = {
    ".ts",
    ".tsx",
    ".js",
    ".jsx",
    ".py",
    ".rs",
    ".go",
    ".java",
    ".kt",
    ".swift",
    ".m",
    ".h",
    ".c",
    ".cpp",
    ".rb",
    ".php",
    ".vue",
    ".svelte",
    ".css",
    ".scss",
    ".less",
    ".html",
    ".sql",
    ".graphql",
    ".sh",
    ".bash",
    ".zsh",
    ".storyboard",
    ".xib",
    ".gradle",
    ".plist",
}

CODE_FILENAMES = {
    "package.json",
    "tsconfig.json",
    "Makefile",
    "Dockerfile",
    "Podfile",
    "Gemfile",
    "build.gradle",
    "settings.gradle",
    "app.json",
    "babel.config.js",
    "metro.config.js",
}

SKILL_REQUIRED_COMMANDS = [
    ("glab mr", "gitlab-mr-creation"),
    ("git push origin", "git-workflow + gitlab-mr-creation"),
]

SUBTASK_GUARD_CONSECUTIVE_THRESHOLD = 4
SUBTASK_GUARD_WINDOW_SECONDS = 600
STATE_STALE_SECONDS = 1800
SEARCH_TOOL_NAMES = {"Grep", "Glob", "WebSearch", "Agent", "Skill"}
CODE_MODIFY_TOOL_NAMES = {"Edit", "Write"}

MARKER_MAX_AGE_MAP = {
    "simple": 3600,
    "medium": 1800,
    "complex": 1200,
}
DEFAULT_MARKER_MAX_AGE = 1800


def _is_allowed_path(file_path: str) -> bool:
    normalized = file_path.replace("\\", "/")
    return (
        normalized.startswith(".agent-flow/")
        or normalized.startswith(".dev-workflow/")
        or normalized.startswith(".claude/")
        or "/.agent-flow/" in normalized
        or "/.dev-workflow/" in normalized
        or "/.claude/" in normalized
    )


def is_code_file(file_path: str) -> bool:
    if _is_allowed_path(file_path):
        return False

    suffix = os.path.splitext(file_path)[1].lower()
    if suffix in {".md", ".txt", ".rst", ".adoc"}:
        return False
    if suffix in CODE_EXTENSIONS:
        return True
    return os.path.basename(file_path) in CODE_FILENAMES


def get_git_branch(project_root: Path) -> str:
    try:
        result = subprocess.run(
            ["git", "-C", str(project_root), "branch", "--show-current"],
            capture_output=True,
            text=True,
            timeout=5,
            check=False,
        )
        return result.stdout.strip()
    except Exception:
        return ""


def has_implementation_plan(project_root: Path) -> tuple[bool, bool]:
    state_dir = read_state_path(project_root, "current_phase.md").parent

    for filename in ("requirement-decomposition.md", "implementation-plan.md", "code-impact-map.md"):
        if (state_dir / filename).is_file():
            return True, False

    phase_file = read_state_path(project_root, "current_phase.md")
    if phase_file.is_file():
        try:
            content = phase_file.read_text(encoding="utf-8")
            plan_format = detect_plan_format(content)
            if plan_format == "canonical":
                return True, False
            if plan_format == "legacy":
                return True, True
        except OSError:
            pass
    return False, False


def _guard_state_path(project_root: Path) -> Path:
    return write_state_path(project_root, ".subtask-guard-state.json")


def load_guard_state(project_root: Path) -> dict[str, float | int | bool]:
    default_state: dict[str, float | int | bool] = {
        "consecutive_edits": 0,
        "last_search_ts": 0.0,
        "last_edit_ts": 0.0,
        "warned": False,
    }
    state_file = _guard_state_path(project_root)
    if not state_file.is_file():
        return default_state
    try:
        state = json.loads(state_file.read_text(encoding="utf-8"))
    except Exception:
        return default_state

    last_edit = float(state.get("last_edit_ts", 0) or 0)
    if last_edit > 0 and (time.time() - last_edit) > STATE_STALE_SECONDS:
        return default_state
    if state.get("warned", False) and (last_edit == 0 or (time.time() - last_edit) > SUBTASK_GUARD_WINDOW_SECONDS):
        state["warned"] = False
    return state


def save_guard_state(project_root: Path, state: dict[str, float | int | bool]) -> None:
    state_file = _guard_state_path(project_root)
    state_file.parent.mkdir(parents=True, exist_ok=True)
    try:
        state_file.write_text(json.dumps(state), encoding="utf-8")
    except OSError:
        pass


def _is_recent(path: Path, max_age: int) -> bool:
    if not path.is_file():
        return False
    try:
        age = time.time() - path.stat().st_mtime
    except OSError:
        return False
    return age < max_age


def has_marker_evidence(project_root: Path) -> bool:
    max_age = MARKER_MAX_AGE_MAP.get(get_complexity_level(project_root), DEFAULT_MARKER_MAX_AGE)
    return _is_recent(read_state_path(project_root, ".search-done"), max_age) or _is_recent(
        read_state_path(project_root, ".subtask-guard-done"),
        max_age,
    )


def is_knowledge_search(tool_name: str, tool_input: dict) -> bool:
    if tool_name in {"WebSearch", "Agent", "Skill"}:
        return True

    if tool_name == "Grep":
        search_param = str(tool_input.get("path", ""))
    elif tool_name == "Glob":
        search_param = str(tool_input.get("path", ""))
    elif tool_name == "Read":
        search_param = str(tool_input.get("file_path", ""))
    else:
        search_param = ""

    valid_keywords = [
        "agent-flow/skills",
        "agent-flow/wiki",
        "agent-flow/memory",
        "dev-workflow/skills",
        "dev-workflow/wiki",
        "Soul",
        "soul.md",
    ]
    return any(keyword in search_param for keyword in valid_keywords)


def main() -> None:
    project_root = find_project_root()
    if project_root is None:
        sys.exit(0)

    phase_file = read_state_path(project_root, "current_phase.md")
    if not phase_file.is_file() or phase_file.stat().st_size <= 10:
        sys.exit(0)

    try:
        input_data = json.loads(sys.stdin.read())
    except Exception:
        sys.exit(0)

    tool_name = str(input_data.get("tool_name", ""))
    tool_input = input_data.get("tool_input", {}) or {}

    if tool_name in ("Write", "Edit"):
        file_path = str(tool_input.get("file_path", ""))
        if not is_code_file(file_path):
            sys.exit(0)

        branch = get_git_branch(project_root)
        if branch in PROTECTED_BRANCHES:
            print(
                f"[AgentFlow BLOCKED] 当前在 {branch} 分支，禁止直接修改代码文件！\n"
                f"{NO_RETRY_LINE}\n\n"
                "✅ 解除方法：\n"
                "  git pull --rebase\n"
                "  git checkout -b feat/xxx\n"
                f"  {UNBLOCK_SUFFIX}\n"
                f"目标文件: {file_path}"
            )
            sys.exit(2)

        has_plan, is_legacy_plan = has_implementation_plan(project_root)
        if not has_plan:
            print(
                "[AgentFlow BLOCKED] 没有实施计划文档，禁止修改代码文件！\n"
                f"{NO_RETRY_LINE}\n\n"
                "✅ 解除方法：\n"
                "  1. 搜索并执行 requirement-decomposition 技能\n"
                "  2. 创建 .agent-flow/state/requirement-decomposition.md\n"
                "  3. 或在 current_phase.md 中添加 ## 实施计划 章节\n"
                "  4. 获得用户确认\n"
                f"  {UNBLOCK_SUFFIX}\n"
                f"目标文件: {file_path}"
            )
            sys.exit(2)
        if is_legacy_plan:
            print(
                "[AgentFlow REMINDER] 当前计划文档为 legacy 格式，已兼容放行。\n"
                "建议迁移到 canonical 章节：# 任务 / ## 复杂度 / ## RPI 阶段规划 / ## 实施计划 / ## 变更点 / ## 验收标准"
            )

        requirement_marker = read_state_path(project_root, ".requirement-clarified")
        if not structured_marker_exists(requirement_marker, ("timestamp", "task", "confirmed_by", "summary")):
            req_decomp = read_state_path(project_root, "requirement-decomposition.md")
            if req_decomp.is_file():
                print(
                    "[AgentFlow REMINDER] 需求澄清标记(.requirement-clarified)不存在！\n"
                    "建议：执行 requirement-decomposition 技能的 Phase 3.5 深度澄清，\n"
                    "确保所有假设和不确定项已与用户确认后再修改代码。\n"
                    f"目标文件: {file_path}"
                )
            else:
                print(
                    "[AgentFlow REMINDER] 需求澄清标记(.requirement-clarified)不存在！\n"
                    "强烈建议：执行 requirement-decomposition 技能（含 Phase 3.5 深度澄清），\n"
                    "确保所有假设和不确定项已与用户确认后再修改代码。\n"
                    f"目标文件: {file_path}"
                )

        design_marker = read_state_path(project_root, ".design-confirmed")
        if not structured_marker_exists(design_marker, ("timestamp", "task", "confirmed_by", "summary")):
            print(
                "[AgentFlow REMINDER] 设计决策确认标记(.design-confirmed)不存在！\n"
                "建议：执行 requirement-decomposition 技能的 Phase 5.5 设计决策检查点，\n"
                "确认修改方式、影响范围、实施策略和回滚方案后再修改代码。\n"
                f"目标文件: {file_path}"
            )

    elif tool_name == "Bash":
        command = str(tool_input.get("command", "")).strip()
        for cmd_prefix, skill_name in SKILL_REQUIRED_COMMANDS:
            if command.startswith(cmd_prefix):
                print(
                    f"[AgentFlow REMINDER] 检测到 '{cmd_prefix}' 命令！\n"
                    "请先搜索并读取相关 Skill 再执行:\n"
                    f"  Grep '{skill_name.split()[0]}' ~/.agent-flow/skills/ 和 .agent-flow/skills/\n"
                    "  找到后严格按 Skill 的 Procedure 执行。\n"
                    "⚠️ 禁止凭经验猜测操作方式！Wiki 已记录先试错再读 Skill 的 pitfall。"
                )
                sys.exit(0)

    if tool_name in CODE_MODIFY_TOOL_NAMES:
        file_path = str(tool_input.get("file_path", ""))
        if is_code_file(file_path):
            state = load_guard_state(project_root)
            now = time.time()
            marker_evidence = has_marker_evidence(project_root)
            last_search = float(state.get("last_search_ts", 0) or 0)
            has_recent_search = marker_evidence or (now - last_search) < SUBTASK_GUARD_WINDOW_SECONDS

            if has_recent_search:
                state["consecutive_edits"] = 0
                state["last_search_ts"] = now if marker_evidence else last_search
                state["last_edit_ts"] = now
                state["warned"] = False
                save_guard_state(project_root, state)
            else:
                state["consecutive_edits"] = int(state.get("consecutive_edits", 0) or 0) + 1
                state["last_edit_ts"] = now

                if int(state["consecutive_edits"]) > SUBTASK_GUARD_CONSECUTIVE_THRESHOLD:
                    if not bool(state.get("warned", False)):
                        state["warned"] = True
                        save_guard_state(project_root, state)
                        print(
                            f"[AgentFlow WARNING] 连续 {state['consecutive_edits']} 次代码修改但未执行搜索！\n"
                            "铁律：每个子任务执行前必须搜索 Skill/Wiki/Soul。\n"
                            "请执行 subtask-guard 技能的 4 步搜索后再继续。\n"
                            f"下次将硬阻断。目标文件: {file_path}"
                        )
                        sys.exit(0)

                    count = int(state["consecutive_edits"])
                    state["warned"] = False
                    state["consecutive_edits"] = 0
                    save_guard_state(project_root, state)
                    print(
                        f"[AgentFlow BLOCKED] 连续 {count} 次代码修改且未执行搜索！\n"
                        f"{NO_RETRY_LINE}\n\n"
                        "✅ 解除方法：执行 subtask-guard 搜索知识库：\n"
                        "  1. Grep '{子任务关键词}' .agent-flow/skills/\n"
                        "  2. Grep '{子任务关键词}' ~/.agent-flow/skills/\n"
                        "  3. Grep '{子任务关键词}' .agent-flow/memory/main/Soul.md\n"
                        "  4. Grep '{子任务关键词}' ~/.agent-flow/wiki/ + .agent-flow/wiki/\n"
                        f"  {UNBLOCK_SUFFIX}\n\n"
                        "参考: ~/.agent-flow/skills/workflow/subtask-guard/handler.md"
                    )
                    sys.exit(2)

                save_guard_state(project_root, state)

    elif tool_name in SEARCH_TOOL_NAMES and is_knowledge_search(tool_name, tool_input):
        state = load_guard_state(project_root)
        state["last_search_ts"] = time.time()
        state["consecutive_edits"] = 0
        state["warned"] = False
        save_guard_state(project_root, state)

    sys.exit(0)


if __name__ == "__main__":
    main()
