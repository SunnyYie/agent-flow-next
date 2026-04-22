from __future__ import annotations

import json
from pathlib import Path


PROJECT_HOOK_COMMANDS: dict[str, list[str]] = {
    "PreToolUse": [
        "python3 .agent-flow/hooks/global/promotion-guard.py",
        "python3 .agent-flow/hooks/global/pre-compress-guard.py",
    ],
    "PostToolUse": [
        "python3 .agent-flow/hooks/global/context-guard.py",
    ],
}


def _load_settings(path: Path) -> dict:
    if not path.exists():
        return {}
    raw = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(raw, dict):
        raise ValueError(f"invalid Claude settings format: {path}")
    return raw


def _find_or_create_matcher_entry(entries: list, matcher: str) -> dict:
    for entry in entries:
        if isinstance(entry, dict) and entry.get("matcher") == matcher:
            hooks = entry.get("hooks")
            if hooks is None:
                entry["hooks"] = []
            elif not isinstance(hooks, list):
                raise ValueError("invalid hooks entry: 'hooks' must be a list")
            return entry
    created = {"matcher": matcher, "hooks": []}
    entries.append(created)
    return created


def _event_has_command(entries: list, command: str) -> bool:
    for entry in entries:
        if not isinstance(entry, dict):
            continue
        hooks = entry.get("hooks", [])
        if not isinstance(hooks, list):
            continue
        for hook in hooks:
            if not isinstance(hook, dict):
                continue
            if hook.get("type") == "command" and hook.get("command") == command:
                return True
    return False


def ensure_project_claude_hooks(project_dir: Path) -> tuple[Path, int]:
    settings_path = project_dir / ".claude" / "settings.json"
    settings_path.parent.mkdir(parents=True, exist_ok=True)

    settings = _load_settings(settings_path)
    hooks = settings.setdefault("hooks", {})
    if not isinstance(hooks, dict):
        raise ValueError("invalid Claude settings format: 'hooks' must be an object")

    added = 0
    for event_name, commands in PROJECT_HOOK_COMMANDS.items():
        event_entries = hooks.setdefault(event_name, [])
        if not isinstance(event_entries, list):
            raise ValueError(f"invalid Claude settings format: '{event_name}' must be a list")
        default_matcher = _find_or_create_matcher_entry(event_entries, matcher="*")
        matcher_hooks = default_matcher["hooks"]
        for command in commands:
            if _event_has_command(event_entries, command):
                continue
            matcher_hooks.append({"type": "command", "command": command})
            added += 1

    settings_path.write_text(json.dumps(settings, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return settings_path, added
