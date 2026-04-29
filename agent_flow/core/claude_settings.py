from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path

from agent_flow.core.plugin_registry import HookRegistration


PROJECT_HOOK_COMMANDS: dict[str, list[str]] = {
    "PreToolUse": [
        "python3 .agent-flow/hooks/governance/promotion-guard.py",
    ],
    "PostToolUse": [
        "python3 .agent-flow/hooks/runtime/context-guard.py",
    ],
}


def _load_settings(path: Path) -> dict:
    if not path.exists():
        return {}
    raw = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(raw, dict):
        raise ValueError(f"invalid Claude settings format: {path}")
    return raw


@dataclass(frozen=True)
class _ManagedPluginHook:
    event: str
    matcher: str
    command: str


def _normalize_command(text: str) -> str:
    return text.replace("\\", "/").strip()


def is_plugin_managed_command(command: str) -> bool:
    # Plugin install path is always nested under `.agent-flow/plugins/`.
    normalized = _normalize_command(command).lower()
    return "/.agent-flow/plugins/" in normalized


def plugin_settings_path(project_dir: Path) -> Path:
    claude_dir = project_dir / ".claude"
    claude_dir.mkdir(parents=True, exist_ok=True)
    # Keep plugin-managed hooks in settings.local.json to align with project-local behavior.
    return claude_dir / "settings.local.json"


def _legacy_plugin_settings_path(project_dir: Path) -> Path:
    claude_dir = project_dir / ".claude"
    claude_dir.mkdir(parents=True, exist_ok=True)
    return claude_dir / "settings.json"


def _plugin_settings_candidates(project_dir: Path) -> list[Path]:
    # local first (active managed location), then legacy path for migration cleanup.
    return [plugin_settings_path(project_dir), _legacy_plugin_settings_path(project_dir)]


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


def _collect_plugin_commands_from_settings(settings: dict) -> set[str]:
    hooks = settings.get("hooks")
    if not isinstance(hooks, dict):
        return set()
    commands: set[str] = set()
    for event_entries in hooks.values():
        if not isinstance(event_entries, list):
            continue
        for entry in event_entries:
            if not isinstance(entry, dict):
                continue
            for hook in entry.get("hooks", []):
                if not isinstance(hook, dict):
                    continue
                if hook.get("type") != "command":
                    continue
                command = hook.get("command", "")
                if isinstance(command, str) and is_plugin_managed_command(command):
                    commands.add(command)
    return commands


def collect_registered_plugin_commands(project_dir: Path) -> set[str]:
    """Return plugin-managed hook commands from project local + legacy settings."""
    commands: set[str] = set()
    for settings_path in _plugin_settings_candidates(project_dir):
        if not settings_path.exists():
            continue
        settings = _load_settings(settings_path)
        commands.update(_collect_plugin_commands_from_settings(settings))
    return commands


def _strip_plugin_managed_hooks(settings: dict) -> dict:
    hooks = settings.get("hooks")
    if not isinstance(hooks, dict):
        return settings

    for event_name, event_entries in list(hooks.items()):
        if not isinstance(event_entries, list):
            continue
        new_entries: list[dict] = []
        for entry in event_entries:
            if not isinstance(entry, dict):
                continue
            matcher = entry.get("matcher")
            entry_hooks = entry.get("hooks", [])
            if not isinstance(entry_hooks, list):
                continue

            kept_hooks: list[dict] = []
            for hook in entry_hooks:
                if not isinstance(hook, dict):
                    continue
                if hook.get("type") != "command":
                    kept_hooks.append(hook)
                    continue
                command = hook.get("command", "")
                if is_plugin_managed_command(command):
                    continue
                kept_hooks.append(hook)

            if kept_hooks:
                entry["hooks"] = kept_hooks
                entry["matcher"] = matcher if isinstance(matcher, str) else "*"
                new_entries.append(entry)

        if new_entries:
            hooks[event_name] = new_entries
        else:
            hooks.pop(event_name, None)
    return settings


def sync_plugin_hook_registrations(project_dir: Path, registrations: list[HookRegistration]) -> tuple[Path, int]:
    """Synchronize project-local plugin hooks to the exact desired set.

    This keeps plugin hooks bound to project `.claude/settings.local.json`
    and avoids stale/duplicated hooks when plugin scope precedence changes.
    """
    settings_path = plugin_settings_path(project_dir)
    settings = _load_settings(settings_path)

    hooks = settings.setdefault("hooks", {})
    if not isinstance(hooks, dict):
        raise ValueError("invalid Claude settings format: 'hooks' must be an object")

    desired = {
        _ManagedPluginHook(event=item.event, matcher=item.matcher, command=item.command)
        for item in registrations
    }

    # 1) Remove plugin-managed commands in active settings.
    settings = _strip_plugin_managed_hooks(settings)
    hooks = settings.setdefault("hooks", {})
    if not isinstance(hooks, dict):
        raise ValueError("invalid Claude settings format: 'hooks' must be an object")

    # 2) Add desired plugin hooks.
    for item in sorted(desired, key=lambda i: (i.event, i.matcher, i.command)):
        event_entries = hooks.setdefault(item.event, [])
        if not isinstance(event_entries, list):
            raise ValueError(f"invalid Claude settings format: '{item.event}' must be a list")
        entry = _find_or_create_matcher_entry(event_entries, matcher=item.matcher)
        matcher_hooks = entry["hooks"]
        matcher_hooks.append({"type": "command", "command": item.command})

    settings_path.write_text(json.dumps(settings, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

    # 3) Migration cleanup + backward-compatible mirror for tools/tests still reading settings.json.
    legacy_path = _legacy_plugin_settings_path(project_dir)
    legacy_settings = _load_settings(legacy_path) if legacy_path.exists() else {}
    legacy_settings = _strip_plugin_managed_hooks(legacy_settings)
    legacy_hooks = legacy_settings.setdefault("hooks", {})
    if not isinstance(legacy_hooks, dict):
        raise ValueError("invalid Claude settings format: 'hooks' must be an object")

    active_hooks = settings.get("hooks", {})
    if isinstance(active_hooks, dict):
        for event_name, event_entries in active_hooks.items():
            if not isinstance(event_entries, list):
                continue
            legacy_event_entries = legacy_hooks.setdefault(event_name, [])
            if not isinstance(legacy_event_entries, list):
                raise ValueError(f"invalid Claude settings format: '{event_name}' must be a list")
            for entry in event_entries:
                if not isinstance(entry, dict):
                    continue
                matcher = entry.get("matcher", "*")
                if not isinstance(matcher, str):
                    matcher = "*"
                target_entry = _find_or_create_matcher_entry(legacy_event_entries, matcher)
                target_hooks = target_entry["hooks"]
                for hook in entry.get("hooks", []):
                    if not isinstance(hook, dict):
                        continue
                    if hook.get("type") != "command":
                        continue
                    command = hook.get("command", "")
                    if not isinstance(command, str) or not command.strip():
                        continue
                    if _event_has_command(legacy_event_entries, command):
                        continue
                    target_hooks.append({"type": "command", "command": command})

    legacy_path.write_text(json.dumps(legacy_settings, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

    return settings_path, len(desired)
