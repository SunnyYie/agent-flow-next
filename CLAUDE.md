# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

AgentFlow Next is a "minimal core + plugin extension" multi-layer workflow CLI for AI agent orchestration. The core only handles initialization, plugin system, and dynamic command loading. All business capabilities come from plugins.

- **Package**: `agent-flow-next` v0.1.0
- **Entry point**: `agent-flow = "agent_flow.cli.main:cli"`
- **Python**: >=3.10
- **Dependencies**: click, pydantic, pyyaml, questionary

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

**Foundation & types:**
- **types.py**: Pydantic models — `AssetKind` (skill, wiki, reference, tool, hook, soul), `ResourceLayer`, `AssetMetadata`, `ResolvedAsset`, `PromotionProposal`, review records
- **config.py**: Three-layer init (`init_global`, `init_team`, `init_project`), path resolution, template hook syncing, index generation, team hooks profiles (`minimal`/`full`)
- **plugin_registry.py**: `PluginRecord`, `PluginScope` enum, YAML-based registry CRUD per scope
- **plugin_manifest.py**: `PluginManifest`, `CommandSpec`, `HookSpec` — manifest parsing
- **plugin_loader.py**: Dynamic command loading from plugin manifests
- **claude_settings.py**: Claude Code settings.json hook management, plugin hook sync/migration
- **plugin.py**: Plugin installation logic (builtin source, local source)
- **plugin_selection.py**: Interactive plugin selection during init
- **request_context.py**: Requirement-entry prompt structuring, task-gate defaults, project workflow scaffold generation (`request-context.json`, `task-list.md`, `phase-review.md`, `agent-team-config.yaml`)

**Resource resolution:**
- **resources/resolver.py**: `ResourceResolver` — overlays skills/wiki/hooks/souls across three layers

**Agent orchestration:**
- **orchestrator.py**: Agent lifecycle management
- **agent_team.py**: Agent team composition
- **agent_scheduler.py**: Agent scheduling
- **agent_memory_sync.py**: Agent memory synchronization
- **event_bus.py**: Event-driven communication between agents
- **structured_state.py**: Structured state management
- **state_contract.py**: State contract definitions

**Memory & recall:**
- **memory.py**: Core memory operations
- **memory_hooks.py**: Memory system hooks
- **memory_index.py**: Memory indexing
- **recall.py**: Recall query execution
- **recall_index_builder.py**: Recall index construction
- **recall_models.py**: Recall data models
- **frozen_memory.py**: Memory persistence/recovery
- **flow_context.py**: Flow context management

**Workflow & pipeline:**
- **pipeline_state.py**: Pipeline stage tracking
- **stage_runtime.py**: Stage execution runtime
- **task_runner.py**: Task execution runner
- **analyzer.py**: Task analysis

**Skill & user management:**
- **skill_manager.py**: Skill CRUD and evolution
- **user_model.py**: User profile and autonomy model
- **user_observer.py**: User behavior observation

**Organization & governance:**
- **organizer.py**: Asset organization and cleanup
- **evolution.py**: Asset evolution tracking
- **decay.py**: Asset decay computation
- **lifecycle.py**: Asset lifecycle management
- **reflection.py**: Reflection and experience extraction
- **compression.py**: Memory/context compression

**Runtime & diagnostics:**
- **runtime.py**: Runtime abstraction
- **native_runtime.py**: Native runtime implementation
- **runtime_context.py**: Runtime context management
- **startup_context.py**: Startup context injection
- **doctor.py**: Health diagnostics
- **recovery.py**: Error recovery
- **hook_telemetry.py**: Hook execution telemetry

**Team:**
- **team.py**: Team management core
- **team_sync.py**: Team synchronization

### Governance Module (agent_flow/governance/)

- **promotions.py**: Promotion system — proposals, human/AI reviews, decisions. Governed by `PROMOTABLE_KINDS_V1` (skill, wiki, hook) and `VALID_PROMOTION_PATHS_V1` in `types.py`.

### Plugin Directory (plugins/)

12 built-in plugins, each self-contained with `manifest.yaml`, `commands/`, and optionally `hooks/` and `core/`:

| Plugin | Namespace | Commands | Hooks | Purpose |
|--------|-----------|----------|-------|---------|
| workflow-pipeline | pipeline | pipeline, plan-review, plan-eng-review, add-feature, run, review, qa, ship | — | Pipeline workflow stages |
| workflow-guards | workflow-guards | — | 18 hooks (guards, enforcers, reminders, trackers) | Runtime enforcers (requirement-entry gating, UI guard, multi-agent routing, reflection enforcement) |
| agent-orchestration | agent-orchestration | agent | — | Multi-agent dispatch, structured state, event bus |
| memory-recall | memory-recall | memory, recall | — | Memory indexing, compression, recall, lifecycle |
| user-profile | user-profile | user | — | User model and autonomy settings |
| hermes-skillops | hermes-skillops | hermes, skill | — | Skill management and evolution |
| runtime-adapters | runtime-adapters | hooks, adapt | — | Platform-specific runtime (Claude Code, etc.) |
| team-collaboration | team-collaboration | team, bind-team, init-team-flow | — | Team binding and sync |
| organization-evolution | organization-evolution | asset, promote, organize | — | Asset promotion, decay, reflection |
| mcp-factory | mcp-factory | mcp-factory | 2 guards | MCP tool factory guard and commands |
| ops-doctor | ops-doctor | doctor | — | Health diagnostics |
| builtin-demo | builtin-demo | demo | 1 hook | Minimal built-in plugin for bootstrap/registry smoke checks |

### Requirement-Entry Workflow (project scope)

Key runtime artifacts created/maintained under `.agent-flow/state/`:

- `request-context.json`: structured user prompt context (documents/project/UI flags/gates)
- `requirements-initial.md`: initial requirement extraction template
- `task-list.md`: task decomposition + task-type/agent routing table
- `phase-review.md`: stage-by-stage reflection template (G1~G4)
- `agent-team-config.yaml`: main/supervisor/coder/verifier role config and gate policy
- `flow-context.yaml`: workflow phase + context budget + task/agent state

Key guards in `workflow-guards`:

- `requirement-entry-guard.py`: auto-parse requirement prompts and scaffold state/docs
- `requirement-entry-enforce.py`: block code edits until requirement-entry prerequisites are met
- `workflow-enforce.py`: enforce implementation plan, task list completeness, UI constraints (only when `ui_constraints_required=true`), and multi-agent routing by task type
- `reflection-summary-guard.py` / `reflection-summary-enforce.py`: complexity-based reflection summary reminders and push/MR blocking until `.task-reflection-done` exists
- `thinking-chain-enforce.py` / `subtask-guard-enforce.py`: enforce search-before-change with two optimizations:
  - simple string replacement whitelist (e.g., CDN URL host swaps) can bypass heavy search flow
  - shared search session for continuous same-type operations (`code_edit` / `bash_exec`) with configurable TTL

### Template System (agent_flow/templates/)

Hooks templates are organized by layer under `hooks/runtime/` and `hooks/governance/`:

- **global/**: 2 templates — `promotion-guard.py`, `context-guard.py`
- **team/**: Sub-organized into `guards/` (10), `enforcers/` (6), `reminders/` (3), `trackers/` (3). Supports `minimal` and `full` hook profiles (`TEAM_HOOKS_PROFILE_MINIMAL` / `TEAM_HOOKS_PROFILE_FULL`).
- **project/**: 6 templates — context guards, agent dispatch, observation recorder, session starter, promotion guard

During init, templates are synced to the target scope but **never overwrite existing files**.

### Promotion System

Assets can be promoted across layers:
- project → team: requires 1 human + 1 AI review
- team → global: requires 2 human + 2 different AI profile reviews

Only `skill`, `wiki`, and `hook` kinds are promotable (`PROMOTABLE_KINDS_V1`). Full `AssetKind` includes: skill, wiki, reference, tool, hook, soul.

Governed by `PROMOTABLE_KINDS_V1` and `VALID_PROMOTION_PATHS_V1` in `types.py`.

### Bundled Resources (agent_flow/resources/)

Fallback resources shipped with the package:
- `config.yaml` — default configuration
- `tools/whitelist.yaml` — tool installation whitelist
- `references/` — 6 reference markdown files
- `skills/`, `wiki/`, `souls/` — bundled knowledge assets

When global resources aren't found on disk, the system falls back to these bundled resources.

## Key Patterns

- **Click CLI with dynamic commands**: `PluginAwareGroup` extends `click.Group` to merge static and plugin-provided commands
- **YAML registries**: Plugin state stored as `registry.yaml` per scope, not in Python
- **File-first governance**: Promotion proposals stored as directory trees (`proposal.yaml`, `snapshot/`, `human-reviews/`, `ai-reviews/`, `decision.yaml`)
- **Bundled fallback**: When global resources aren't found on disk, the system falls back to `agent_flow/resources/` bundled with the package
- **Settings migration**: Plugin hooks moved from `settings.json` to `settings.local.json`; old entries cleaned automatically
- **Team hooks profiles**: Team initialization supports `minimal` (essential guards only) and `full` (all guards + enforcers + reminders + trackers) profiles

## Test Conventions

- 27 test files covering all major subsystems
- Tests use `pytest` with `click.testing.CliRunner` for CLI testing
- `conftest.py` provides shared fixtures
- Test files organized by feature area: plugin system, governance, pipeline, individual plugins, resource resolution
- Tests typically create temp directories and validate file-system state after CLI operations
- Key test files: `test_plugin_*.py` (plugin system), `test_governance.py` (promotion), `test_resource_resolver.py` (resource resolution), `test_phase*.py` (integration phases)
