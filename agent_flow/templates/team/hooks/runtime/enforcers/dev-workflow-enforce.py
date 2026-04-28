#!/usr/bin/env python3
"""
AgentFlow Dev Workflow Enforcer — PreToolUse hook
强制执行5条开发铁律（即使 pre-flight 完成后也必须遵守）：
1. 禁止在 main/master/develop 分支上修改代码文件
2. 禁止没有实施计划文档就修改代码文件
3. 特定操作前提醒搜索 Skill（MR、push 等）
4. 遇到错误禁止自行推测（由 error-search-remind.py 处理）
5. 连续 Edit/Write 超过 2 次且无间隔搜索时，强制执行 subtask-guard

仅在有 .agent-flow/ 或 .dev-workflow/ 的项目中生效。
仅在 pre-flight 完成后（current_phase.md 存在）才执行检查。
"""
import json
import os
import subprocess
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from contract_utils import (
    NO_RETRY_LINE,
    UNBLOCK_SUFFIX,
    detect_plan_format,
    find_project_root,
    get_complexity_level,
    read_state_path,
    structured_marker_exists,
)

# ============================================================
# 配置
# ============================================================

PROTECTED_BRANCHES = {"main", "master", "develop"}

# 代码文件扩展名 → 修改这些文件需要检查分支和计划
CODE_EXTENSIONS = {
    ".ts", ".tsx", ".js", ".jsx", ".py", ".rs", ".go", ".java", ".kt",
    ".swift", ".m", ".h", ".c", ".cpp", ".rb", ".php", ".vue", ".svelte",
    ".css", ".scss", ".less", ".html", ".sql", ".graphql",
    ".sh", ".bash", ".zsh",
    ".storyboard", ".xib", ".gradle", ".plist",
}

# 代码文件名（无论扩展名）→ 修改需要检查
CODE_FILENAMES = {
    "package.json", "tsconfig.json", "Makefile", "Dockerfile",
    "Podfile", "Gemfile", "build.gradle", "settings.gradle",
    "app.json", "babel.config.js", "metro.config.js",
}

# 需要先搜索 Skill 的 Bash 命令前缀 → 对应 Skill 名称
SKILL_REQUIRED_COMMANDS = [
    ("glab mr", "gitlab-mr-creation"),
    ("git push origin", "git-workflow + gitlab-mr-creation"),
]

# 实施计划的标记内容 → current_phase.md 中包含任一即视为有计划
PLAN_MARKERS = [
    "## 实施计划", "## Implementation Plan", "## 变更点",
    "## CP", "## 代码修改", "## 代码影响",
]

# 允许写入的路径前缀（不受分支和计划限制）
ALLOWED_PATH_PREFIXES = (".agent-flow", ".dev-workflow", ".claude")

# 深度澄清和设计决策标记文件（v3.0 新增）
REQUIREMENT_CLARIFIED_MARKER = ".agent-flow/state/.requirement-clarified"
DESIGN_CONFIRMED_MARKER = ".agent-flow/state/.design-confirmed"

# 连续 Edit/Write 搜索守卫配置
SUBTASK_GUARD_STATE_FILE = ".agent-flow/state/.subtask-guard-state.json"
SUBTASK_GUARD_CONSECUTIVE_THRESHOLD = 4  # 连续 Edit/Write 次数阈值（v2: 2→4，避免正常编码误触）
SUBTASK_GUARD_WINDOW_SECONDS = 600      # 搜索有效窗口（v2: 5→10分钟，给复杂编辑更多空间）
STATE_STALE_SECONDS = 1800              # 状态过期时间（v2新增：30分钟无活动自动重置）
SEARCH_TOOL_NAMES = {"Grep", "Glob", "WebSearch", "Agent", "Skill"}  # v2: 扩展搜索工具范围
CODE_MODIFY_TOOL_NAMES = {"Edit", "Write"}  # 视为"代码修改"的工具

# 搜索标记文件 — search-tracker.py 创建，可作为搜索证据
SEARCH_MARKER_FILE = ".agent-flow/state/.search-done"
SUBTASK_GUARD_MARKER = ".agent-flow/state/.subtask-guard-done"

# 标记有效期（与 subtask-guard-enforce.py 对齐，v2: 按复杂度分级）
MARKER_MAX_AGE_MAP = {
    "simple": 3600,   # 60 分钟
    "medium": 1800,   # 30 分钟
    "complex": 1200,  # 20 分钟
}
DEFAULT_MARKER_MAX_AGE = 1800


# ============================================================
# 工具函数
# ============================================================

def is_code_file(file_path: str) -> bool:
    """判断文件是否为代码文件（需要实施计划和分支检查）"""
    # 允许 agent-flow 相关路径
    for prefix in ALLOWED_PATH_PREFIXES:
        if prefix in file_path:
            return False

    # 允许 Markdown 和纯文本（文档类）
    _, ext = os.path.splitext(file_path)
    if ext.lower() in (".md", ".txt", ".rst", ".adoc"):
        return False

    # 检查扩展名
    if ext.lower() in CODE_EXTENSIONS:
        return True

    # 检查文件名
    basename = os.path.basename(file_path)
    if basename in CODE_FILENAMES:
        return True

    # 默认放行（宁可漏检不可误阻）
    return False


def get_git_branch() -> str:
    """获取当前 git 分支名"""
    try:
        result = subprocess.run(
            ["git", "branch", "--show-current"],
            capture_output=True, text=True, timeout=5
        )
        return result.stdout.strip()
    except Exception:
        return ""


def has_implementation_plan(project_root) -> tuple[bool, bool]:
    """检查是否存在实施计划文档"""
    state_dir = read_state_path(project_root, "current_phase.md").parent

    # 检查独立的实施计划文件
    plan_files = [
        "requirement-decomposition.md",
        "implementation-plan.md",
        "code-impact-map.md",
    ]
    for pf in plan_files:
        if os.path.isfile(os.path.join(state_dir, pf)):
            return True

    # 检查 current_phase.md 中是否包含计划章节
    # 同时检查两个可能的路径
    phase_file = read_state_path(project_root, "current_phase.md")
    if os.path.isfile(phase_file):
        try:
            with open(phase_file, "r", encoding="utf-8") as f:
                content = f.read()
            plan_format = detect_plan_format(content)
            if plan_format == "canonical":
                return True, False
            if plan_format == "legacy":
                return True, True
        except Exception:
            pass

    return False, False


# ============================================================
# 主逻辑
# ============================================================

def main():
    project_root = find_project_root()
    if project_root is None:
        sys.exit(0)

    # 只在 pre-flight 完成后执行（preflight-enforce.py 处理 pre-flight 前的阶段）
    # 同时检查两个路径
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

    # ----------------------------------------------------------
    # 检查 1 & 2: Write/Edit → 分支 + 实施计划
    # ----------------------------------------------------------
    if tool_name in ("Write", "Edit"):
        file_path = tool_input.get("file_path", "")

        if not is_code_file(file_path):
            sys.exit(0)  # 非代码文件，放行

        # 检查 1: Git 分支
        branch = get_git_branch()
        if branch in PROTECTED_BRANCHES:
            print(
                f"[AgentFlow BLOCKED] 当前在 {branch} 分支，禁止直接修改代码文件！\n"
                f"{NO_RETRY_LINE}\n\n"
                f"✅ 解除方法：\n"
                f"  git pull --rebase\n"
                f"  git checkout -b feat/xxx\n"
                f"  {UNBLOCK_SUFFIX}\n"
                f"目标文件: {file_path}"
            )
            sys.exit(2)

        # 检查 2: 实施计划文档
        has_plan, is_legacy_plan = has_implementation_plan(project_root)
        if not has_plan:
            print(
                f"[AgentFlow BLOCKED] 没有实施计划文档，禁止修改代码文件！\n"
                f"{NO_RETRY_LINE}\n\n"
                f"✅ 解除方法：\n"
                f"  1. 搜索并执行 requirement-decomposition 技能\n"
                f"  2. 创建 .agent-flow/state/requirement-decomposition.md\n"
                f"  3. 或在 current_phase.md 中添加 ## 实施计划 章节\n"
                f"  4. 获得用户确认\n"
                f"  {UNBLOCK_SUFFIX}\n"
                f"目标文件: {file_path}"
            )
            sys.exit(2)
        if is_legacy_plan:
            print(
                "[AgentFlow REMINDER] 当前计划文档为 legacy 格式，已兼容放行。\n"
                "建议迁移到 canonical 章节：# 任务 / ## 复杂度 / ## RPI 阶段规划 / ## 实施计划 / ## 变更点 / ## 验收标准"
            )

        # 检查 3: 需求澄清标记（v3.0 新增，软提醒）
        requirement_marker = read_state_path(project_root, ".requirement-clarified")
        if not structured_marker_exists(requirement_marker, ("timestamp", "task", "confirmed_by", "summary")):
            # 检查是否有 requirement-decomposition.md（旧版兼容）
            req_decomp = ".agent-flow/state/requirement-decomposition.md"
            if os.path.isfile(req_decomp):
                # 有拆解文档但没有澄清标记 → 可能是旧版流程创建的，软提醒
                print(
                    f"[AgentFlow REMINDER] 需求澄清标记(.requirement-clarified)不存在！\n"
                    f"建议：执行 requirement-decomposition 技能的 Phase 3.5 深度澄清，\n"
                    f"确保所有假设和不确定项已与用户确认后再修改代码。\n"
                    f"目标文件: {file_path}"
                )
            else:
                # 没有拆解文档也没有澄清标记 → 强烈建议
                print(
                    f"[AgentFlow REMINDER] 需求澄清标记(.requirement-clarified)不存在！\n"
                    f"强烈建议：执行 requirement-decomposition 技能（含 Phase 3.5 深度澄清），\n"
                    f"确保所有假设和不确定项已与用户确认后再修改代码。\n"
                    f"目标文件: {file_path}"
                )
            # v1: 软提醒不阻断，渐进引入后可升级为硬阻断

        # 检查 4: 设计决策确认标记（v3.0 新增，软提醒）
        design_marker = read_state_path(project_root, ".design-confirmed")
        if not structured_marker_exists(design_marker, ("timestamp", "task", "confirmed_by", "summary")):
            print(
                f"[AgentFlow REMINDER] 设计决策确认标记(.design-confirmed)不存在！\n"
                f"建议：执行 requirement-decomposition 技能的 Phase 5.5 设计决策检查点，\n"
                f"确认修改方式、影响范围、实施策略和回滚方案后再修改代码。\n"
                f"目标文件: {file_path}"
            )
            # v1: 软提醒不阻断，渐进引入后可升级为硬阻断

    # ----------------------------------------------------------
    # 检查 3: Bash → Skill 搜索提醒
    # ----------------------------------------------------------
    elif tool_name == "Bash":
        command = tool_input.get("command", "").strip()

        for cmd_prefix, skill_name in SKILL_REQUIRED_COMMANDS:
            if command.startswith(cmd_prefix):
                # 软提醒（不是阻断，但会显示在 Agent 上下文中）
                print(
                    f"[AgentFlow REMINDER] 检测到 '{cmd_prefix}' 命令！\n"
                    f"请先搜索并读取相关 Skill 再执行:\n"
                    f"  Grep '{skill_name.split()[0]}' ~/.agent-flow/skills/ 和 .agent-flow/skills/\n"
                    f"  找到后严格按 Skill 的 Procedure 执行。\n"
                    f"⚠️ 禁止凭经验猜测操作方式！Wiki 已记录先试错再读 Skill 的 pitfall。"
                )
                sys.exit(0)

    # ----------------------------------------------------------
    # 检查 5: 连续 Edit/Write 搜索守卫（subtask-guard 强制执行）
    # v2: 自动过期 + 标记证据 + 扩展搜索工具 + 宽松阈值
    # ----------------------------------------------------------

    def load_guard_state():
        """加载搜索守卫状态，自动过期陈旧状态"""
        default_state = {
            "consecutive_edits": 0,
            "last_search_ts": 0,
            "last_edit_ts": 0,
            "warned": False,
        }
        if not os.path.isfile(SUBTASK_GUARD_STATE_FILE):
            return default_state
        try:
            with open(SUBTASK_GUARD_STATE_FILE, "r", encoding="utf-8") as f:
                state = json.load(f)
            # v2 自动过期：如果最后编辑时间超过 STATE_STALE_SECONDS，重置状态
            last_edit = state.get("last_edit_ts", 0)
            if last_edit > 0 and (time.time() - last_edit) > STATE_STALE_SECONDS:
                return default_state
            # v2 安全重置：如果 warned=true 但 last_edit 已过期，清除 warned
            if state.get("warned", False):
                if last_edit == 0 or (time.time() - last_edit) > SUBTASK_GUARD_WINDOW_SECONDS:
                    state["warned"] = False
            return state
        except Exception:
            return default_state

    def save_guard_state(state):
        """保存搜索守卫状态"""
        state_dir = os.path.dirname(SUBTASK_GUARD_STATE_FILE)
        if not os.path.isdir(state_dir):
            os.makedirs(state_dir, exist_ok=True)
        try:
            with open(SUBTASK_GUARD_STATE_FILE, "w", encoding="utf-8") as f:
                json.dump(state, f)
        except Exception:
            pass

    def has_marker_evidence():
        """v2新增：检查 search-tracker.py 创建的标记文件作为搜索证据（按复杂度分级有效期）"""
        # 读取复杂度级别
        complexity = "medium"
        complexity_file = ".agent-flow/state/.complexity-level"
        if os.path.isfile(complexity_file):
            try:
                with open(complexity_file, "r", encoding="utf-8") as f:
                    for line in f:
                        line = line.strip()
                        if line.startswith("level="):
                            complexity = line.split("=", 1)[1].strip().lower()
                            break
            except Exception:
                pass
        max_age = MARKER_MAX_AGE_MAP.get(complexity, DEFAULT_MARKER_MAX_AGE)

        now = time.time()
        for marker_file in [SEARCH_MARKER_FILE, SUBTASK_GUARD_MARKER]:
            if os.path.isfile(marker_file):
                try:
                    mtime = os.path.getmtime(marker_file)
                    if (now - mtime) < max_age:
                        return True
                except Exception:
                    pass
        return False

    def is_knowledge_search(tool_name, tool_input):
        """v2新增：判断搜索工具是否搜索了知识库路径（与 search-tracker.py 逻辑对齐）"""
        if tool_name in {"WebSearch", "Agent", "Skill"}:
            return True
        # Grep/Glob/Read 搜索知识库路径也算
        search_param = ""
        if tool_name == "Grep":
            search_param = tool_input.get("path", "")
        elif tool_name == "Glob":
            search_param = tool_input.get("path", "")
        elif tool_name == "Read":
            search_param = tool_input.get("file_path", "")
        valid_keywords = [
            "agent-flow/skills", "agent-flow/wiki", "agent-flow/memory",
            "dev-workflow/skills", "dev-workflow/wiki", "Soul", "soul.md",
        ]
        return any(kw in search_param for kw in valid_keywords)

    # 只对代码修改工具和搜索工具做追踪
    if tool_name in CODE_MODIFY_TOOL_NAMES:
        file_path = tool_input.get("file_path", "")
        if is_code_file(file_path):
            state = load_guard_state()
            now = time.time()

            # v2: 检查搜索证据（标记文件 或 窗口内搜索时间戳）
            marker_evidence = has_marker_evidence()
            last_search = state.get("last_search_ts", 0)
            has_recent_search = marker_evidence or (now - last_search) < SUBTASK_GUARD_WINDOW_SECONDS

            if has_recent_search:
                # 有近期搜索证据，重置并允许编辑
                state["consecutive_edits"] = 0
                state["last_search_ts"] = now if marker_evidence else last_search
                state["last_edit_ts"] = now
                state["warned"] = False
                save_guard_state(state)
            else:
                # 无搜索证据，递增计数
                state["consecutive_edits"] = state.get("consecutive_edits", 0) + 1
                state["last_edit_ts"] = now

                if state["consecutive_edits"] > SUBTASK_GUARD_CONSECUTIVE_THRESHOLD:
                    # 连续超过阈值次代码修改且无搜索
                    if not state.get("warned", False):
                        # 首次：软提醒
                        state["warned"] = True
                        save_guard_state(state)
                        print(
                            f"[AgentFlow WARNING] 连续 {state['consecutive_edits']} 次代码修改但未执行搜索！\n"
                            f"铁律：每个子任务执行前必须搜索 Skill/Wiki/Soul。\n"
                            f"请执行 subtask-guard 技能的 4 步搜索后再继续。\n"
                            f"下次将硬阻断。目标文件: {file_path}"
                        )
                        sys.exit(0)
                    else:
                        # 已警告过：硬阻断
                        count = state["consecutive_edits"]  # S1 fix: 保存计数后再重置
                        state["warned"] = False
                        state["consecutive_edits"] = 0
                        save_guard_state(state)
                        print(
                            f"[AgentFlow BLOCKED] 连续 {count} 次代码修改且未执行搜索！\n"
                            f"{NO_RETRY_LINE}\n\n"
                            f"✅ 解除方法：执行 subtask-guard 搜索知识库：\n"
                            f"  1. Grep '{{子任务关键词}}' .agent-flow/skills/\n"
                            f"  2. Grep '{{子任务关键词}}' ~/.agent-flow/skills/\n"
                            f"  3. Grep '{{子任务关键词}}' .agent-flow/memory/main/Soul.md\n"
                            f"  4. Grep '{{子任务关键词}}' ~/.agent-flow/wiki/ + .agent-flow/wiki/\n"
                            f"  {UNBLOCK_SUFFIX}\n\n"
                            f"参考: ~/.agent-flow/skills/workflow/subtask-guard/handler.md"
                        )
                        sys.exit(2)

                save_guard_state(state)

    elif tool_name in SEARCH_TOOL_NAMES:
        # v2: 知识库搜索工具调用，更新搜索时间戳并重置连续计数
        if is_knowledge_search(tool_name, tool_input):
            state = load_guard_state()
            state["last_search_ts"] = time.time()
            state["consecutive_edits"] = 0  # 搜索后重置连续计数
            state["warned"] = False
            save_guard_state(state)

    sys.exit(0)


if __name__ == "__main__":
    main()
