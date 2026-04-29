# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

AgentFlow Next is a "minimal core + plugin extension" multi-layer workflow CLI for AI agent orchestration. The core only handles initialization, plugin system, and dynamic command loading. All business capabilities come from plugins.

## Build & Test Commands

```bash
# Install in editable mode
pip install -e .

# Run all tests
pytest

# Run a single test file
pytest tests/test_plugin_registry.py

# Run a specific test function
pytest tests/test_plugin_registry.py::test_load_scope_roundtrip

# Run with verbose output
pytest -v tests/test_plugin_hooks.py

# Lint
ruff check .

# Format
ruff format .

# CLI entry point
agent-flow --help
```

## Architecture

### Three-Layer Scope Model

All resources (skills, wiki, hooks, souls, tools, references) live in one of three scopes, resolved in **project > team > global** precedence:

| Scope | Path | Purpose |
|-------|------|---------|
| Global | `~/.agent-flow/` | Machine-wide defaults, bundled skills/wiki/souls |
| Team | `$AGENT_FLOW_TEAM_ROOT/{team_id}/.agent-flow/` | Shared team assets, governance hooks |
| Project | `{project}/.agent-flow/` | Project-specific assets, state, logs |

Key constraint: **governance hooks cannot be overridden by project layer** (enforced in `ResourceResolver._resolve_overlay` with `governance_guard=True`).

### Plugin System

Plugins are the primary extension mechanism. Each plugin has a `manifest.yaml` defining commands and hooks:

```yaml
api_version: 1
name: workflow-pipeline
version: 0.1.0
namespace: pipeline
commands:
  - path: commands/pipeline.py
    name: pipeline
    group: true
hooks:
  - path: hooks/some-guard.py
    event: PreToolUse
    matcher: ""
```

**Plugin loading flow:**
1. `PluginRegistry.load_effective()` merges plugins from all three scopes (global → team → project, last write wins)
2. `load_enabled_plugin_commands()` reads each enabled plugin's manifest, dynamically imports command modules via `importlib`, and extracts click Commands
3. `PluginAwareGroup` (a click.Group subclass) makes plugin commands available alongside built-in CLI commands

**Hook injection:** `sync_plugin_hook_registrations()` writes plugin hooks into `.claude/settings.local.json` as `{"type": "command", "command": "python3 <path>"}` entries. Plugin hooks are identified by containing `/.agent-flow/plugins/` in their command path and are cleanly separated from non-plugin hooks.

### Core Modules (agent_flow/core/)

- **types.py**: Pydantic models — `AssetKind`, `ResourceLayer`, `AssetMetadata`, `ResolvedAsset`, `PromotionProposal`, review records
- **config.py**: Three-layer init (`init_global`, `init_team`, `init_project`), path resolution, template hook syncing, index generation
- **plugin_registry.py**: `PluginRecord`, `PluginScope` enum, YAML-based registry CRUD per scope
- **plugin_manifest.py**: `PluginManifest`, `CommandSpec`, `HookSpec` — manifest parsing
- **plugin_loader.py**: Dynamic command loading from plugin manifests
- **claude_settings.py**: Claude Code settings.json hook management, plugin hook sync/migration
- **resources/resolver.py**: `ResourceResolver` — overlays skills/wiki/hooks/souls across three layers

### Plugin Directory (plugins/)

11 built-in plugins, each self-contained with `manifest.yaml`, `commands/`, and optionally `hooks/` and `core/`:

| Plugin | Purpose |
|--------|---------|
| workflow-pipeline | Plan/review/run/qa/ship pipeline stages |
| workflow-guards | Runtime enforcers (search-before-execute, phase reminders, parallel enforcement) |
| agent-orchestration | Multi-agent dispatch, structured state, event bus |
| memory-recall | Memory indexing, compression, recall, lifecycle |
| user-profile | User model and autonomy settings |
| hermes-skillops | Skill management and evolution |
| runtime-adapters | Platform-specific runtime (Claude Code, etc.) |
| team-collaboration | Team binding and sync |
| organization-evolution | Asset promotion, decay, reflection |
| mcp-factory | MCP tool factory guard and commands |
| ops-doctor | Health diagnostics |

### Template System (agent_flow/templates/)

Hooks templates are organized by layer (`global/`, `team/`, `project/`) under `hooks/runtime/` and `hooks/governance/`. During init, templates are synced to the target scope but **never overwrite existing files**.

### Promotion System

Assets (skill, wiki, hook) can be promoted across layers:
- project → team: requires 1 human + 1 AI review
- team → global: requires 2 human + 2 different AI profile reviews

Governed by `PROMOTABLE_KINDS_V1` and `VALID_PROMOTION_PATHS_V1` in `types.py`.

## Key Patterns

- **Click CLI with dynamic commands**: `PluginAwareGroup` extends `click.Group` to merge static and plugin-provided commands
- **YAML registries**: Plugin state stored as `registry.yaml` per scope, not in Python
- **File-first governance**: Promotion proposals stored as directory trees (`proposal.yaml`, `snapshot/`, `human-reviews/`, `ai-reviews/`, `decision.yaml`)
- **Bundled fallback**: When global resources aren't found on disk, the system falls back to `agent_flow/resources/` bundled with the package
- **Settings migration**: Plugin hooks moved from `settings.json` to `settings.local.json`; old entries cleaned automatically

## Test Conventions

- Tests use `pytest` with `click.testing.CliRunner` for CLI testing
- `conftest.py` provides shared fixtures
- Test files are organized by feature area (plugin system, governance, pipeline, individual plugins)
- Tests typically create temp directories and validate file-system state after CLI operations
