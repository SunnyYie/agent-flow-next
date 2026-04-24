from __future__ import annotations

import shutil
from pathlib import Path

from agent_flow.core.claude_settings import add_plugin_hook_registrations, remove_plugin_hook_registrations
from agent_flow.core.plugin_manifest import load_plugin_manifest
from agent_flow.core.plugin_registry import HookRegistration, PluginRecord, PluginRegistry, PluginScope


def _builtin_plugins_roots() -> list[Path]:
    repo_root = Path(__file__).resolve().parents[2]
    package_root = Path(__file__).resolve().parents[1]
    candidates = [
        repo_root / "plugins",
        package_root / "plugins",
    ]

    roots: list[Path] = []
    for root in candidates:
        if root.exists() and root.is_dir() and root not in roots:
            roots.append(root)
    return roots


def discover_builtin_plugins() -> dict[str, Path]:
    discovered: dict[str, Path] = {}
    for root in _builtin_plugins_roots():
        for entry in sorted((p for p in root.iterdir() if p.is_dir()), key=lambda p: p.name.lower()):
            manifest_path = entry / "manifest.yaml"
            if not manifest_path.is_file():
                continue
            try:
                manifest = load_plugin_manifest(manifest_path)
            except Exception:
                continue
            # First root has priority (repo-level over package-level).
            discovered.setdefault(manifest.name, entry)
    return discovered


def _install_root(scope: PluginScope, *, project_dir: Path, team_id: str = "") -> Path:
    return PluginRegistry.registry_path(scope, project_dir=project_dir, team_id=team_id).parent


def _parse_source_spec(source: str, plugin_name: str, *, project_dir: Path) -> tuple[str, str, Path]:
    if ":" in source:
        source_type, location = source.split(":", 1)
    else:
        source_type, location = "builtin", source

    source_type = source_type.strip()
    location = (location or plugin_name).strip()

    if source_type == "local":
        source_path = Path(location).expanduser()
        if not source_path.is_absolute():
            source_path = (project_dir / source_path).resolve()
    elif source_type == "builtin":
        source_path: Path | None = None
        for root in _builtin_plugins_roots():
            candidate = root / location
            if candidate.exists():
                source_path = candidate
                break
    else:
        raise ValueError(f"unsupported source type: {source_type}")

    if source_path is None or not source_path.exists():
        raise FileNotFoundError(f"plugin source not found: {source_path}")

    return source_type, location, source_path


def install_plugin(
    plugin_name: str,
    *,
    scope: PluginScope,
    source: str,
    project_dir: Path,
    team_id: str = "",
) -> PluginRecord:
    source_type, source_location, source_path = _parse_source_spec(source, plugin_name, project_dir=project_dir)

    install_root = _install_root(scope, project_dir=project_dir, team_id=team_id)
    install_root.mkdir(parents=True, exist_ok=True)
    plugin_dir = install_root / plugin_name

    if plugin_dir.exists():
        shutil.rmtree(plugin_dir)
    shutil.copytree(source_path, plugin_dir)

    manifest = load_plugin_manifest(plugin_dir / "manifest.yaml")
    if manifest.name != plugin_name:
        raise ValueError(
            f"plugin name mismatch: expected '{plugin_name}', got '{manifest.name}' from {plugin_dir / 'manifest.yaml'}"
        )

    hook_registrations = [
        HookRegistration(
            event=hook.event,
            matcher=hook.matcher,
            command=f"python3 {plugin_dir / hook.path}",
        )
        for hook in manifest.hooks
    ]

    if hook_registrations:
        add_plugin_hook_registrations(project_dir, hook_registrations)

    record = PluginRecord(
        name=plugin_name,
        version=manifest.version,
        enabled=True,
        install_path=str(plugin_dir),
        source={"type": source_type, "location": source_location, "ref": ""},
        hook_registrations=hook_registrations,
        scope=scope,
    )
    PluginRegistry.upsert_record(scope, record, project_dir=project_dir, team_id=team_id)
    return record


def set_plugin_enabled(
    plugin_name: str,
    *,
    scope: PluginScope,
    enabled: bool,
    project_dir: Path,
    team_id: str = "",
) -> PluginRecord:
    records = PluginRegistry.load_scope(scope, project_dir=project_dir, team_id=team_id)
    record = records.get(plugin_name)
    if record is None:
        raise KeyError(f"plugin not found in {scope.value} scope: {plugin_name}")

    if enabled:
        if record.hook_registrations:
            add_plugin_hook_registrations(project_dir, record.hook_registrations)
    else:
        if record.hook_registrations:
            remove_plugin_hook_registrations(project_dir, record.hook_registrations)

    record.enabled = enabled
    records[plugin_name] = record
    PluginRegistry.save_scope(scope, records, project_dir=project_dir, team_id=team_id)
    return record


def uninstall_plugin(
    plugin_name: str,
    *,
    scope: PluginScope,
    project_dir: Path,
    team_id: str = "",
) -> None:
    records = PluginRegistry.load_scope(scope, project_dir=project_dir, team_id=team_id)
    record = records.get(plugin_name)
    if record is None:
        raise KeyError(f"plugin not found in {scope.value} scope: {plugin_name}")

    if record.hook_registrations:
        remove_plugin_hook_registrations(project_dir, record.hook_registrations)

    plugin_dir = Path(record.install_path)
    if plugin_dir.exists():
        shutil.rmtree(plugin_dir)

    PluginRegistry.delete_record(scope, plugin_name, project_dir=project_dir, team_id=team_id)


def list_plugins(
    *,
    project_dir: Path,
    team_id: str = "",
    scope: PluginScope | None = None,
    enabled_only: bool = False,
) -> dict[str, PluginRecord]:
    if scope is None:
        return PluginRegistry.load_effective(project_dir=project_dir, team_id=team_id, enabled_only=enabled_only)
    return PluginRegistry.load_scope(scope, project_dir=project_dir, team_id=team_id)


def ensure_default_builtin_plugins(
    *,
    scope: PluginScope,
    project_dir: Path,
    team_id: str = "",
    selected_plugins: list[str] | None = None,
) -> list[str]:
    builtin_plugins = discover_builtin_plugins()
    if not builtin_plugins:
        return []

    selected_set = set(selected_plugins) if selected_plugins is not None else None

    installed = PluginRegistry.load_scope(scope, project_dir=project_dir, team_id=team_id)
    added: list[str] = []
    for plugin_name, source_dir in sorted(builtin_plugins.items(), key=lambda item: item[0].lower()):
        if selected_set is not None and plugin_name not in selected_set:
            continue
        if plugin_name in installed:
            continue
        install_plugin(
            plugin_name,
            scope=scope,
            source=f"builtin:{source_dir.name}",
            project_dir=project_dir,
            team_id=team_id,
        )
        added.append(plugin_name)
    return added
