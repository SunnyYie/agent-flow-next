#!/usr/bin/env python3
"""
AgentFlow Context Budget Tracker — PostToolUse hook (Read|Grep|Glob matcher)

Track estimated context token usage after each tool call.

Logic:
  - After each Read tool call, estimate tokens from file size (bytes / 3.3)
  - After each Grep/Glob tool call, estimate tokens from tool_output length
  - Accumulate total in .agent-flow/state/flow-context.yaml under context_budget.used
  - When usage exceeds 50%: print warning
  - When usage exceeds 70%: print critical warning recommending sub-agent delegation
  - If flow-context.yaml doesn't exist, create it with context_budget section

Input (via stdin JSON from Claude Code PostToolUse):
  - tool_name: "Read" | "Grep" | "Glob"
  - tool_input: {file_path, path, pattern, ...}
  - tool_output: truncated result string from the tool call

Output: Update flow-context.yaml, print <system-reminder> block when thresholds exceeded.
"""
from __future__ import annotations

import json
import os
import sys
import time
from pathlib import Path

# Conservative estimate: 1 byte ≈ 0.3 token (mixed Chinese/English)
BYTES_PER_TOKEN = 3.3  # 1 / 0.3

# Budget thresholds
THRESHOLD_WARNING = 0.5
THRESHOLD_CRITICAL = 0.7

# Large file threshold (bytes) — warn if reading a single file over this
LARGE_FILE_THRESHOLD_BYTES = 50000  # ~50KB ≈ ~15K tokens

# Default max context budget (tokens)
DEFAULT_MAX_BUDGET = 200000

# Session reset threshold — if used > 3x max budget, likely stale data from
# a previous session; reset to a reasonable starting estimate
STALE_MULTIPLIER = 3


def _find_project_root() -> Path | None:
    cwd = Path.cwd()
    for parent in [cwd, *cwd.parents]:
        if (parent / ".agent-flow").exists():
            return parent
        if parent == Path.home():
            break
    return None


def _find_flow_context_path(project_root: Path) -> Path | None:
    """Find flow-context.yaml path."""
    path = project_root / ".agent-flow" / "state" / "flow-context.yaml"
    if path.is_file():
        return path
    return None


def _default_flow_context_path(project_root: Path) -> Path:
    """Get default flow-context.yaml path (for creating new files)."""
    return project_root / ".agent-flow" / "state" / "flow-context.yaml"


def _estimate_tokens_from_file_size(file_path: str) -> int:
    """Estimate tokens from file size (bytes / 3.3)."""
    try:
        size = os.path.getsize(file_path)
        return int(size / BYTES_PER_TOKEN)
    except OSError:
        return 0


def _estimate_tokens_from_output(output: str) -> int:
    """Estimate tokens from tool output string length.

    Uses a more conservative ratio for tool output since it includes
    line numbers, formatting, and structural overhead.
    """
    if not output:
        return 300  # Default estimate for empty/minimal search results
    # Rough: each character ≈ 0.25 tokens for mixed content
    # But tool output includes line numbers, formatting, etc., so
    # we discount slightly. 100 chars ≈ 25 tokens.
    return max(200, int(len(output) * 0.25))


def _parse_simple_yaml(content: str) -> dict:
    """Minimal YAML parser for flow-context.yaml structure.

    Only handles the subset we need: nested dicts with string/int/float values.
    Does NOT handle: lists of dicts, multiline strings, anchors, etc.
    """
    result: dict = {}
    current_path: list[str] = []

    for line in content.splitlines():
        stripped = line.rstrip()
        if not stripped or stripped.startswith("#"):
            continue

        # Calculate indentation
        indent = len(line) - len(line.lstrip())
        # Determine nesting level (2 spaces per level)
        level = indent // 2

        # Trim current path to match level
        current_path = current_path[:level]

        stripped_val = stripped.strip()

        # Key-value pair
        if ":" in stripped_val:
            key, _, value = stripped_val.partition(":")
            key = key.strip()
            value = value.strip()

            # Remove quotes from value
            if value and len(value) >= 2 and value[0] in ('"', "'") and value[-1] == value[0]:
                value = value[1:-1]

            # Build nested dict
            target = result
            for k in current_path:
                if k not in target or not isinstance(target[k], dict):
                    target[k] = {}
                target = target[k]

            # Parse value type
            if not value:
                # New nesting level
                current_path.append(key)
                target[key] = {}
            else:
                # Try to parse as number
                try:
                    if "." in value:
                        target[key] = float(value)
                    else:
                        target[key] = int(value)
                except ValueError:
                    target[key] = value

    return result


def _serialize_simple_yaml(data: dict, indent: int = 0) -> str:
    """Simple YAML serializer for dict data."""
    lines = []
    prefix = "  " * indent
    for key, value in data.items():
        if isinstance(value, dict):
            lines.append(f"{prefix}{key}:")
            lines.append(_serialize_simple_yaml(value, indent + 1))
        elif isinstance(value, str):
            # Quote strings that might be interpreted as other types
            if value in ("true", "false", "null", "") or value.replace(".", "", 1).replace("-", "", 1).isdigit():
                lines.append(f'{prefix}{key}: "{value}"')
            else:
                lines.append(f"{prefix}{key}: {value}")
        elif isinstance(value, bool):
            lines.append(f"{prefix}{key}: {'true' if value else 'false'}")
        elif isinstance(value, (int, float)):
            lines.append(f"{prefix}{key}: {value}")
        elif isinstance(value, list):
            lines.append(f"{prefix}{key}:")
            for item in value:
                if isinstance(item, dict):
                    lines.append(f"{prefix}  -")
                    lines.append(_serialize_simple_yaml(item, indent + 2))
                else:
                    lines.append(f"{prefix}  - {item}")
        else:
            lines.append(f"{prefix}{key}: {value}")
    return "\n".join(lines)


def _read_flow_context(path: Path) -> dict:
    """Read flow-context.yaml using simple YAML parsing (no dependency)."""
    try:
        content = path.read_text(encoding="utf-8")
        return _parse_simple_yaml(content)
    except OSError:
        return {}


def _write_flow_context(path: Path, context: dict) -> None:
    """Write flow-context.yaml with atomic write pattern."""
    # Ensure parent directory exists
    path.parent.mkdir(parents=True, exist_ok=True)

    try:
        content = _serialize_simple_yaml(context)
        tmp_path = path.with_suffix(".yaml.tmp")
        tmp_path.write_text(content, encoding="utf-8")
        tmp_path.replace(path)
    except OSError:
        # Fallback: try direct write
        try:
            path.write_text(_serialize_simple_yaml(context), encoding="utf-8")
        except OSError:
            pass


def _init_flow_context(path: Path) -> dict:
    """Create a new flow-context.yaml with the context_budget section.

    Called when flow-context.yaml doesn't exist yet.
    """
    context = {
        "context_budget": {
            "used": 0,
            "max": DEFAULT_MAX_BUDGET,
            "status": "healthy",
            "files_read": 0,
            "last_updated": time.strftime("%Y-%m-%dT%H:%M:%S"),
        },
    }
    _write_flow_context(path, context)
    return context


def _reset_stale_budget(budget: dict, max_budget: int) -> dict:
    """Reset budget if used value is unrealistically large (stale from previous session).

    If used > 3x max_budget, the counter has accumulated across sessions without
    reset. We can't know the actual current usage, so estimate conservatively
    at 30% (assuming we're mid-conversation if the hook is firing).
    """
    current_used = budget.get("used", 0)
    if current_used > max_budget * STALE_MULTIPLIER:
        budget["used"] = int(max_budget * 0.3)
        budget["status"] = "warning"
    return budget


def _compute_status(used: int, max_budget: int) -> str:
    """Compute budget status based on usage ratio."""
    if max_budget <= 0:
        return "healthy"
    ratio = used / max_budget
    if ratio >= THRESHOLD_CRITICAL:
        return "critical"
    elif ratio >= THRESHOLD_WARNING:
        return "warning"
    return "healthy"


def _format_system_reminder(level: str, used: int, max_budget: int) -> str:
    """Format a <system-reminder> block for budget alerts."""
    pct = used * 100 // max_budget if max_budget > 0 else 0

    if level == "warning":
        return (
            "<system-reminder>\n"
            f"[AgentFlow BUDGET WARNING] Context budget at {pct}% "
            f"({used // 1000}K / {max_budget // 1000}K tokens)\n\n"
            "Recommendations:\n"
            "  1. Prioritize delegating remaining tasks to sub-agents\n"
            "  2. Avoid reading large files; use L2 summaries only\n"
            "  3. Limit simultaneous L2 summary reads to 3 or fewer\n"
            "</system-reminder>"
        )
    elif level == "critical":
        return (
            "<system-reminder>\n"
            f"[AgentFlow BUDGET CRITICAL] Context budget at {pct}%! "
            f"({used // 1000}K / {max_budget // 1000}K tokens)\n\n"
            "MANDATORY actions:\n"
            "  1. ALL remaining work MUST be delegated to sub-agents\n"
            "  2. Main agent must only do state management — do NOT read any non-summary files\n"
            "  3. Immediately prune L1 summary cache, keeping only task IDs and artifact paths\n"
            "  4. Reference: ~/.agent-flow/skills/agent-orchestration/context-budget/handler.md\n"
            "</system-reminder>"
        )
    return ""


def main() -> None:
    project_root = _find_project_root()
    if project_root is None:
        return

    # Read hook input from stdin
    try:
        raw_input = sys.stdin.read()
        input_data = json.loads(raw_input or "{}")
    except Exception:
        return

    tool_name = input_data.get("tool_name", "")
    tool_input = input_data.get("tool_input", {})
    tool_output = input_data.get("tool_output", "")

    # Only track Read, Grep, Glob tools
    if tool_name not in ("Read", "Grep", "Glob"):
        return

    # Estimate tokens consumed
    estimated_tokens = 0
    if tool_name == "Read":
        file_path = tool_input.get("file_path", "")
        if file_path and os.path.isfile(file_path):
            estimated_tokens = _estimate_tokens_from_file_size(file_path)
            # Large file warning
            file_size = os.path.getsize(file_path)
            if file_size > LARGE_FILE_THRESHOLD_BYTES:
                print(
                    "<system-reminder>\n"
                    f"[AgentFlow BUDGET WARNING] Reading large file: "
                    f"{os.path.basename(file_path)} "
                    f"({file_size // 1024}KB ≈ {estimated_tokens} tokens)\n\n"
                    "If this is a sub-agent's L3 result, use the deep context "
                    "analyst pattern instead of reading it directly.\n"
                    "</system-reminder>"
                )
        else:
            # File path not available or file doesn't exist on disk
            # Try to estimate from tool_output if available
            if tool_output:
                estimated_tokens = _estimate_tokens_from_output(tool_output)
            else:
                estimated_tokens = 800  # Default estimate for Read without known file

    elif tool_name in ("Grep", "Glob"):
        # Use tool_output for better estimation when available
        if tool_output:
            estimated_tokens = _estimate_tokens_from_output(tool_output)
        else:
            # Fallback default estimates
            estimated_tokens = 500 if tool_name == "Grep" else 300

    # Find or create flow-context.yaml
    fc_path = _find_flow_context_path(project_root)
    if fc_path is None:
        # Create flow-context.yaml with context_budget section
        default_path = _default_flow_context_path(project_root)
        context = _init_flow_context(default_path)
        fc_path = default_path
    else:
        context = _read_flow_context(fc_path)
        if not context:
            context = _init_flow_context(fc_path)

    # Get current budget values
    budget = context.get("context_budget", {})
    max_budget = budget.get("max", DEFAULT_MAX_BUDGET)

    # Reset stale budget values (from previous sessions)
    budget = _reset_stale_budget(budget, max_budget)

    current_used = budget.get("used", 0)
    old_status = budget.get("status", "healthy")

    # Update budget
    new_used = current_used + estimated_tokens
    new_status = _compute_status(new_used, max_budget)

    budget["used"] = new_used
    budget["status"] = new_status
    budget["files_read"] = budget.get("files_read", 0) + 1
    budget["last_updated"] = time.strftime("%Y-%m-%dT%H:%M:%S")
    context["context_budget"] = budget

    # Write updated flow-context
    _write_flow_context(fc_path, context)

    # Output system-reminder on status change or when already in warning/critical
    # Also emit on status change to catch the moment we cross a threshold
    if new_status != old_status:
        reminder = _format_system_reminder(new_status, new_used, max_budget)
        if reminder:
            print(reminder)


if __name__ == "__main__":
    main()
