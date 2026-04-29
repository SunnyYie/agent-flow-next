#!/usr/bin/env python3
"""Trigger requirement-mode workflow for requirement-doc execution prompts.

UserPromptSubmit hook:
- Detect prompts like "阅读xxx需求文档，并执行/完成/开发xxx任务"
- Require reading project fewshots + CLAUDE.md
- Auto-init agent-flow when the current project is not initialized
- Remind the agent to execute by fewshots + agent-flow workflow
"""

from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

for candidate in (Path(__file__).resolve().parents[3], Path(__file__).resolve().parents[4]):
    if (candidate / "agent_flow").is_dir():
        sys.path.insert(0, str(candidate))
        break

from agent_flow.core.request_context import ensure_request_scaffolds, parse_request_prompt, write_request_context

STATE_FILE = ".claude/.requirement-entry-state.json"
REQUIREMENT_HINTS = (
    "需求文档",
    "prd",
    "需求",
    "feishu.cn/wiki",
    "feishu.cn/docx",
)

READ_HINTS = (
    "阅读",
    "查看",
    "分析",
    "理解",
)

TASK_HINTS = (
    "执行",
    "完成",
    "开发",
    "实现",
    "任务",
    "流程",
)

DESIGN_HINTS = (
    "设计图",
    "设计稿",
    "效果图",
    "原型",
    "ui 图",
    "下载图片",
    "download image",
)


def _extract_prompt_text(raw: str) -> str:
    if not raw.strip():
        return ""
    try:
        payload = json.loads(raw)
    except Exception:
        return raw

    parts: list[str] = []
    for key in ("prompt", "user_prompt", "message", "text", "input"):
        value = payload.get(key)
        if isinstance(value, str):
            parts.append(value)
    session = payload.get("session")
    if isinstance(session, dict):
        for key in ("prompt", "message", "last_user_message"):
            value = session.get(key)
            if isinstance(value, str):
                parts.append(value)
    return "\n".join(parts) if parts else raw


def _should_trigger(prompt: str) -> bool:
    text = prompt.lower()
    has_requirement = any(hint in text for hint in REQUIREMENT_HINTS)
    has_read = any(hint in prompt for hint in READ_HINTS)
    has_task = any(hint in prompt for hint in TASK_HINTS)
    return has_requirement and (has_read or "阅读" in prompt) and has_task


def _find_repo_root() -> Path:
    cwd = Path.cwd().resolve()
    for parent in [cwd, *cwd.parents]:
        if (parent / ".git").exists():
            return parent
    return cwd


def _find_fewshots_file(repo_root: Path) -> Path | None:
    preferred = repo_root / "fewshots" / "intern.md"
    if preferred.is_file():
        return preferred
    fewshots_dir = repo_root / "fewshots"
    if fewshots_dir.is_dir():
        for candidate in sorted(fewshots_dir.glob("*.md")):
            if candidate.is_file():
                return candidate
    return None


def _run_init(repo_root: Path) -> tuple[bool, str]:
    try:
        result = subprocess.run(
            ["agent-flow", "init", "--project"],
            cwd=str(repo_root),
            capture_output=True,
            text=True,
            timeout=120,
        )
    except FileNotFoundError:
        return False, "agent-flow CLI 不在 PATH 中"
    except subprocess.TimeoutExpired:
        return False, "agent-flow init 超时"
    except Exception as exc:
        return False, str(exc)

    if result.returncode == 0:
        return True, "initialized with agent-flow init --project"
    stderr = (result.stderr or result.stdout or "").strip()
    return False, stderr or f"exit {result.returncode}"


def _write_state(
    repo_root: Path,
    prompt: str,
    claude_md: Path,
    fewshots_file: Path | None,
    has_agent_flow: bool,
    init_status: str,
    request_context_path: Path,
    claude_project_rules_ready: bool,
) -> Path:
    state_path = repo_root / STATE_FILE
    state_path.parent.mkdir(parents=True, exist_ok=True)
    payload = {
        "status": "pending",
        "prompt": prompt[:1000],
        "repo_root": str(repo_root),
        "claude_md": str(claude_md),
        "claude_md_exists": claude_md.is_file(),
        "claude_md_read": False,
        "fewshots": str(fewshots_file) if fewshots_file is not None else "",
        "fewshots_exists": bool(fewshots_file and fewshots_file.is_file()),
        "fewshots_read": False,
        "agent_flow_ready": has_agent_flow,
        "init_status": init_status.strip(),
        "allow_design_assets": any(hint in prompt.lower() for hint in DESIGN_HINTS),
        "request_context": str(request_context_path),
        "claude_project_rules_ready": claude_project_rules_ready,
    }
    try:
        request_context = json.loads(request_context_path.read_text(encoding="utf-8"))
    except Exception:
        request_context = {}
    payload["has_ui_input"] = bool(request_context.get("has_ui_input"))
    payload["project"] = str(request_context.get("project", ""))
    state_path.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    return state_path


def _claude_has_project_rules(claude_md: Path) -> bool:
    if not claude_md.is_file():
        return False
    try:
        content = claude_md.read_text(encoding="utf-8").lower()
    except OSError:
        return False
    required_keywords = ("project-structure", "项目结构", "任务清单", "agent")
    return all(keyword in content for keyword in required_keywords)


def main() -> None:
    raw = sys.stdin.read()
    prompt = _extract_prompt_text(raw)
    if not _should_trigger(prompt):
        return

    repo_root = _find_repo_root()
    claude_md = repo_root / "CLAUDE.md"
    fewshots_file = _find_fewshots_file(repo_root)

    has_agent_flow = (repo_root / ".agent-flow").exists()
    init_status = ""
    if not has_agent_flow:
        ok, detail = _run_init(repo_root)
        has_agent_flow = ok and (repo_root / ".agent-flow").exists()
        if ok:
            init_status = (
                "\n[AgentFlow] 当前项目原先未初始化，已自动执行 `agent-flow init --project`。"
            )
        else:
            init_status = (
                "\n[AgentFlow WARNING] 当前项目未初始化，尝试自动执行 `agent-flow init --project` 失败："
                f"\n{detail}"
            )
    request_context = parse_request_prompt(prompt)
    ensure_request_scaffolds(repo_root, request_context.project or repo_root.name, request_context)
    request_context_path = write_request_context(repo_root, request_context)
    claude_project_rules_ready = _claude_has_project_rules(claude_md)
    state_path = _write_state(
        repo_root,
        prompt,
        claude_md,
        fewshots_file,
        has_agent_flow,
        init_status,
        request_context_path,
        claude_project_rules_ready,
    )

    read_lines = []
    if claude_md.is_file():
        read_lines.append(f"1. 必须先阅读 `{claude_md}`")
    else:
        read_lines.append(
            f"1. 当前项目缺少 `{claude_md}`，需要先补齐或确认替代协议文件"
        )
    if fewshots_file is not None:
        if fewshots_file.is_relative_to(repo_root):
            read_lines.append(f"2. 必须先阅读 `{fewshots_file}`")
        else:
            read_lines.append(
                f"2. 当前项目未提供 fewshots，必须先阅读 fallback fewshot `{fewshots_file}`"
            )
    else:
        read_lines.append(f"2. 当前项目未找到 `fewshots/*.md`，需要先补齐 fewshots")

    workflow_line = (
        "3. 若项目已包含 `.agent-flow`，后续必须参考 fewshots 和 agent-flow 流程执行，"
        "不能直接跳到开发"
    )
    if not has_agent_flow:
        workflow_line = "3. 当前项目尚未形成可用的 agent-flow 工作流，需先完成初始化问题后再继续任务"

    claude_rule_line = ""
    if not claude_project_rules_ready:
        claude_rule_line = (
            "\n[AgentFlow WARNING] 当前项目的 CLAUDE.md 缺少项目结构/任务清单/Agent 分工等开发规范，"
            "需要先补充后再进入开发。"
        )

    print(
        "<system-reminder>\n"
        "[AgentFlow REQUIREMENT ENTRY] 检测到“阅读需求文档并执行任务”类输入，已启用强制流程。\n"
        f"项目目录: {repo_root}\n"
        f"{init_status}\n\n"
        f"状态文件: {state_path}\n\n"
        f"结构化请求: {request_context_path}\n"
        f"{claude_rule_line}\n\n"
        "接下来必须按顺序执行：\n"
        f"{read_lines[0]}\n"
        f"{read_lines[1]}\n"
        f"{workflow_line}\n"
        "4. 完成文档阅读后，先补齐 requirements-initial / task-list / project-structure，再开始 pre-flight、需求拆解、实现与验证\n"
        "</system-reminder>"
    )


if __name__ == "__main__":
    main()
