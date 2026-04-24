from __future__ import annotations

import sys

from agent_flow.core.plugin import discover_builtin_plugins
from agent_flow.core.plugin_manifest import load_plugin_manifest


def _available_plugins() -> dict[str, str]:
    plugins = discover_builtin_plugins()
    result: dict[str, str] = {}
    for name, path in sorted(plugins.items(), key=lambda item: item[0].lower()):
        manifest = load_plugin_manifest(path / "manifest.yaml")
        result[name] = manifest.description
    return result


def _validate_plugin_names(plugin_names: list[str], available: dict[str, str]) -> list[str]:
    unknown = [name for name in plugin_names if name not in available]
    if unknown:
        raise ValueError(f"unknown builtin plugin(s): {', '.join(unknown)}")
    return plugin_names


def select_plugins_interactive(plugin_names: list[str] | None = None) -> list[str]:
    available = _available_plugins()
    if not available:
        return []

    if plugin_names is not None:
        normalized = [name.strip() for name in plugin_names if name.strip()]
        return _validate_plugin_names(normalized, available)

    if not sys.stdin.isatty() or not sys.stdout.isatty():
        return list(available.keys())

    import questionary

    choices = [
        questionary.Choice(title=f"{name} - {description}", value=name, checked=True)
        for name, description in available.items()
    ]
    selected = questionary.checkbox("Select plugins to install", choices=choices).ask()
    if not selected:
        return list(available.keys())
    return _validate_plugin_names(selected, available)
