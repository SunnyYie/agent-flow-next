"""Helpers for Claude-native runtime bridge resolution and execution."""

from __future__ import annotations

import logging
import json
import shutil
import subprocess
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path

from agent_flow.core.config import project_native_executor, project_native_executor_command
from agent_flow.core.pipeline_state import TaskState
from agent_flow.core.task_runner import TaskResult

logger = logging.getLogger(__name__)

_STAGE_TO_AGENT: dict[str, str] = {
    "plan-review": "verifier",
    "plan-eng-review": "verifier",
    "review": "verifier",
    "qa": "verifier",
    "run": "executor",
    "ship": "executor",
}


@dataclass
class NativeAgentDefinition:
    name: str
    path: Path
    content: str
    stages: list[str]
    mode: str = "system-prompt-asset"
    metadata: dict[str, object] | None = None


def discover_native_agents(home_dir: Path | None = None) -> list[NativeAgentDefinition]:
    agents_dir = (home_dir or Path.home()) / ".claude" / "agents"
    if not agents_dir.is_dir():
        return []
    discovered: list[NativeAgentDefinition] = []
    for agent_file in sorted(agents_dir.glob("agent-flow-*.md")):
        try:
            content = agent_file.read_text(encoding="utf-8")
        except Exception:
            continue
        name = agent_file.stem.removeprefix("agent-flow-")
        metadata = _parse_agent_metadata(content)
        stages = _normalize_stage_list(metadata.get("stages"))
        mode = str(metadata.get("mode", "system-prompt-asset") or "system-prompt-asset")
        discovered.append(
            NativeAgentDefinition(
                name=name, path=agent_file, content=content,
                stages=stages, mode=mode, metadata=metadata,
            )
        )
    return discovered


def resolve_agent_definition(stage_name: str) -> str | None:
    agent_name = _STAGE_TO_AGENT.get(stage_name)
    if not agent_name:
        return None
    for definition in discover_native_agents():
        if definition.name == agent_name or stage_name in definition.stages:
            return definition.content
    return None


def resolve_agent_for_stage(stage_name: str) -> NativeAgentDefinition | None:
    preferred_name = _STAGE_TO_AGENT.get(stage_name)
    fallback: NativeAgentDefinition | None = None
    for definition in discover_native_agents():
        if stage_name in definition.stages:
            if preferred_name is None or definition.name == preferred_name:
                return definition
            fallback = fallback or definition
        elif preferred_name is not None and definition.name == preferred_name:
            fallback = fallback or definition
    return fallback


class NativeAgentLifecycleManager:
    def __init__(self, project_dir: Path) -> None:
        self.project_dir = project_dir
        self.path = project_dir / ".agent-flow" / "state" / "native-agent-lifecycle.json"

    def record_assignment(
        self, *, stage_name: str, agent_name: str, task_id: str,
        status: str, details: dict[str, str] | None = None,
    ) -> None:
        state = self._load()
        agent_state = state.setdefault("agents", {}).setdefault(
            agent_name, {"stages": [], "tasks": [], "statuses": [], "events": []},
        )
        if stage_name not in agent_state["stages"]:
            agent_state["stages"].append(stage_name)
        if task_id not in agent_state["tasks"]:
            agent_state["tasks"].append(task_id)
        agent_state["statuses"].append(status)
        agent_state["events"].append({
            "timestamp": datetime.now().isoformat(timespec="seconds"),
            "stage_name": stage_name, "task_id": task_id,
            "status": status, "details": details or {},
        })
        self._save(state)

    def _load(self) -> dict:
        if not self.path.is_file():
            return {"agents": {}}
        try:
            return json.loads(self.path.read_text(encoding="utf-8"))
        except Exception:
            return {"agents": {}}

    def _save(self, state: dict) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.path.write_text(json.dumps(state, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")


@dataclass
class NativeExecutorResolution:
    mode: str
    command: list[str]
    source: str


def summarize_native_agent_adoption(project_dir: Path) -> str:
    telemetry_path = project_dir / ".agent-flow" / "logs" / "hook_telemetry.jsonl"
    if telemetry_path.is_file():
        try:
            for line in telemetry_path.read_text(encoding="utf-8").splitlines():
                if not line.strip():
                    continue
                entry = json.loads(line)
                if entry.get("hook") == "startup-context" and entry.get("status") == "success":
                    if entry.get("source") == "doctor-self-check":
                        return "observed-via-runtime-self-check"
                    return "observed-via-hooks"
        except Exception:
            pass
    lifecycle_path = project_dir / ".agent-flow" / "state" / "native-agent-lifecycle.json"
    if lifecycle_path.is_file():
        try:
            state = json.loads(lifecycle_path.read_text(encoding="utf-8"))
            agents = state.get("agents", {})
            if isinstance(agents, dict) and agents:
                return "observed-via-native-agent-lifecycle"
        except Exception:
            pass
    return "installed-unverified"


def summarize_bridge_health(project_dir: Path, native_executor: "NativeExecutorResolution | None") -> str:
    if native_executor is None:
        return "not configured"
    lifecycle_path = project_dir / ".agent-flow" / "state" / "native-agent-lifecycle.json"
    if lifecycle_path.is_file():
        try:
            state = json.loads(lifecycle_path.read_text(encoding="utf-8"))
            agents = state.get("agents", {})
            events = []
            if isinstance(agents, dict):
                for agent_state in agents.values():
                    agent_events = agent_state.get("events", [])
                    if isinstance(agent_events, list):
                        events.extend(agent_events)
            run_events = [event for event in events if event.get("stage_name") == "run"]
            if run_events:
                failures = sum(1 for event in run_events if event.get("status") == "failed")
                if failures:
                    return f"degraded ({failures}/{len(run_events)} failed)"
                return f"healthy ({len(run_events)} observed)"
        except Exception:
            pass
    return "configured-unverified"


def resolve_native_executor(project_dir: Path) -> NativeExecutorResolution | None:
    configured = project_native_executor_command(project_dir)
    if configured:
        return NativeExecutorResolution(
            mode="command", command=configured,
            source="project execution.native_executor_command",
        )
    shortcut = project_native_executor(project_dir)
    if shortcut == "claude-cli":
        claude_path = shutil.which("claude")
        if claude_path:
            return NativeExecutorResolution(
                mode="claude-cli", command=[claude_path],
                source="built-in claude-cli bridge",
            )
    return None


def _parse_agent_metadata(content: str) -> dict[str, object]:
    if not content.startswith("---"):
        return {}
    try:
        end = content.index("\n---", 3)
    except ValueError:
        return {}
    frontmatter = content[3:end].strip()
    try:
        import yaml
        data = yaml.safe_load(frontmatter) or {}
    except Exception:
        return {}
    return data if isinstance(data, dict) else {}


def _normalize_stage_list(raw_value: object) -> list[str]:
    if isinstance(raw_value, list):
        return [str(item).strip() for item in raw_value if str(item).strip()]
    if isinstance(raw_value, str) and raw_value.strip():
        return [raw_value.strip()]
    return []


def execute_native_stage(
    project_dir: Path, stage_name: str, output_path: Path,
    metadata: list[str] | None, native_executor: NativeExecutorResolution,
) -> tuple[bool, str]:
    if native_executor.mode == "command":
        args = [*native_executor.command, str(project_dir), stage_name, str(output_path), *(metadata or [])]
    elif native_executor.mode == "claude-cli":
        prompt = output_path.read_text(encoding="utf-8")
        args = [*native_executor.command, "-p", prompt, "--output-format", "text"]
        agent_def = resolve_agent_definition(stage_name)
        if agent_def:
            args.extend(["--system-prompt", agent_def])
    else:
        return False, f"Unsupported native executor mode: {native_executor.mode}"
    try:
        result = subprocess.run(args, cwd=str(project_dir), capture_output=True, text=True, check=False)
    except OSError as exc:
        return False, str(exc)
    output = "\n".join(part for part in [result.stdout.strip(), result.stderr.strip()] if part).strip()
    if result.returncode != 0:
        return False, output or "native stage executor failed"
    if native_executor.mode == "claude-cli":
        output_path.write_text((output + "\n") if output else "", encoding="utf-8")
    return True, output


def execute_native_task(
    project_dir: Path, task: TaskState, packet_path: Path,
    results_dir: Path, native_executor: NativeExecutorResolution,
) -> TaskResult:
    result_path = results_dir / f"task-{task.id}-result.md"
    if native_executor.mode == "command":
        args = [
            *native_executor.command, str(project_dir), str(packet_path),
            str(task.id), task.title, task.description or "",
        ]
    elif native_executor.mode == "claude-cli":
        prompt = packet_path.read_text(encoding="utf-8")
        args = [*native_executor.command, "-p", prompt, "--output-format", "text"]
        agent_def = resolve_agent_definition("run")
        if agent_def:
            args.extend(["--system-prompt", agent_def])
    else:
        return TaskResult(task.id, success=False, error=f"Unsupported native executor mode: {native_executor.mode}")
    try:
        process = subprocess.run(args, cwd=str(project_dir), capture_output=True, text=True, check=False)
    except OSError as exc:
        return TaskResult(task.id, success=False, error=str(exc))
    output = "\n".join(part for part in [process.stdout.strip(), process.stderr.strip()] if part).strip()
    if output:
        result_path.write_text(output + "\n", encoding="utf-8")
    if process.returncode != 0:
        return TaskResult(
            task.id, success=False, files_modified=task.files,
            test_results=output, verification_passed=False,
            error=output or "native executor failed",
        )
    return TaskResult(
        task.id, success=True, files_modified=task.files,
        test_results=output, verification_passed=True,
    )
