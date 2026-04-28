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
    if not fewshots_dir.is_dir():
        return None
    for candidate in sorted(fewshots_dir.glob("*.md")):
        if candidate.is_file():
            return candidate
    return None


def _run_init(repo_root: Path) -> tuple[bool, str]:
    try:
        result = subprocess.run(
            ["agent-flow", "init", "--dev-workflow"],
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
        return True, "initialized"
    stderr = (result.stderr or result.stdout or "").strip()
    return False, stderr or f"exit {result.returncode}"


def _write_state(
    repo_root: Path,
    prompt: str,
    claude_md: Path,
    fewshots_file: Path | None,
    has_agent_flow: bool,
    init_status: str,
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
    }
    state_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return state_path


def main() -> None:
    raw = sys.stdin.read()
    prompt = _extract_prompt_text(raw)
    if not _should_trigger(prompt):
        return

    repo_root = _find_repo_root()
    claude_md = repo_root / "CLAUDE.md"
    fewshots_file = _find_fewshots_file(repo_root)

    has_agent_flow = (repo_root / ".agent-flow").exists() or (repo_root / ".dev-workflow").exists()
    init_status = ""
    if not has_agent_flow:
        ok, detail = _run_init(repo_root)
        has_agent_flow = ok and ((repo_root / ".agent-flow").exists() or (repo_root / ".dev-workflow").exists())
        if ok:
            init_status = (
                "\n[AgentFlow] 当前项目原先未初始化，已自动执行 `agent-flow init --dev-workflow`。"
            )
        else:
            init_status = (
                "\n[AgentFlow WARNING] 当前项目未初始化，尝试自动执行 `agent-flow init --dev-workflow` 失败："
                f"\n{detail}"
            )
    state_path = _write_state(repo_root, prompt, claude_md, fewshots_file, has_agent_flow, init_status)

    read_lines = []
    if claude_md.is_file():
        read_lines.append(f"1. 必须先阅读 `{claude_md}`")
    else:
        read_lines.append(f"1. 当前项目缺少 `{claude_md}`，需要先补齐或确认替代协议文件")
    if fewshots_file is not None:
        read_lines.append(f"2. 必须先阅读 `{fewshots_file}`")
    else:
        read_lines.append(f"2. 当前项目未找到 `fewshots/*.md`，需要先补齐 fewshots")

    workflow_line = (
        "3. 若项目已包含 `.agent-flow`/`.dev-workflow`，后续必须参考 fewshots 和 agent-flow 流程执行，"
        "不能直接跳到开发"
    )
    if not has_agent_flow:
        workflow_line = (
            "3. 当前项目尚未形成可用的 agent-flow 工作流，需先完成初始化问题后再继续任务"
        )

    print(
        "<system-reminder>\n"
        "[AgentFlow REQUIREMENT ENTRY] 检测到“阅读需求文档并执行任务”类输入，已启用强制流程。\n"
        f"项目目录: {repo_root}\n"
        f"{init_status}\n\n"
        f"状态文件: {state_path}\n\n"
        "接下来必须按顺序执行：\n"
        f"{read_lines[0]}\n"
        f"{read_lines[1]}\n"
        f"{workflow_line}\n"
        "4. 完成文档阅读后，再开始 pre-flight、需求拆解、实现与验证\n"
        "</system-reminder>"
    )


if __name__ == "__main__":
    main()
