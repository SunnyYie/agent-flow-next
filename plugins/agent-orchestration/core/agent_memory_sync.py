"""Agent memory synchronization — merge sub-agent memories back to main.

After a sub-agent completes its task, its experiences and skills
need to be synced to the main agent's memory for cross-agent learning.
Supports both Soul.md format and StructuredState format.
"""

from pathlib import Path
from typing import Any
from datetime import date

import yaml

from agent_flow.core.config import project_primary_skills_dir
from agent_flow.core.memory import MemoryManager


class AgentMemorySync:
    """Handles synchronization of memories between sub-agents and the main agent."""

    SYNC_STATE_FILENAME = ".sync_state"

    def __init__(self, project_dir: Path) -> None:
        self.project_dir = project_dir
        self.main_memory = MemoryManager(project_dir, "main")

    def pull_experiences(self, agent_name: str) -> list[dict]:
        """Read a sub-agent's Soul.md and extract new experiences that haven't been synced to main yet.

        Tracks sync state in .agent-flow/memory/{agent_name}/.sync_state
        """
        agent_memory = MemoryManager(self.project_dir, agent_name)
        soul = agent_memory.read_soul()
        entries = soul.get("dynamic", [])

        # Load sync state
        sync_state = self._load_sync_state(agent_name)
        last_sync_count = sync_state.get("synced_experience_count", 0)

        # Only return new experiences
        new_entries = entries[last_sync_count:]
        return new_entries

    def push_to_main(self, experiences: list[dict], source_agent: str) -> None:
        """Append synced experiences to main agent's Soul.md with source attribution."""
        for exp in experiences:
            description = exp.get("description", "")
            # Add source attribution
            source_tag = f" | source:{source_agent}" if source_agent else ""

            self.main_memory.add_experience(
                date=exp.get("date", ""),
                module=exp.get("module", ""),
                exp_type=exp.get("exp_type", ""),
                description=description + source_tag,
                confidence=exp.get("confidence", 0.5),
                abstraction=exp.get("abstraction", ""),
            )

    def push_structured_results(self, worker_results: list[dict[str, Any]], source_agent: str) -> int:
        """Sync StructuredState WorkerResultState entries to main agent's Soul.md.

        Converts structured worker results into experience entries, enabling
        cross-agent learning from orchestrator-worker workflows.

        Args:
            worker_results: List of WorkerResultState dicts (from structured_state).
            source_agent: Name of the source agent/orchestrator.

        Returns:
            Number of experiences synced.
        """
        synced = 0
        for result in worker_results:
            if result.get("status") != "success":
                continue

            task_type = result.get("task_type", "unknown")
            description = result.get("result", "")[:500]  # Truncate long results
            source_tag = f" | source:{source_agent}" if source_agent else ""

            self.main_memory.add_experience(
                date=date.today().isoformat(),
                module="orchestrator-worker",
                exp_type=f"worker-result:{task_type}",
                description=description + source_tag,
                confidence=0.6,  # Auto-synced results start at moderate confidence
                abstraction="project",
            )
            synced += 1

        return synced

    def push_skill_to_shared(self, agent_name: str, skill_name: str) -> Path:
        """Move a skill from an agent's personal skills/ to the project skills root.

        Returns the new path of the promoted skill.
        """
        # Source: agent's personal skills directory
        agent_skill_dir = (
            self.project_dir / ".agent-flow" / "memory" / agent_name / "skills" / skill_name
        )
        # Also check .dev-workflow/{agent}/skills/
        dw_skill_dir = (
            self.project_dir / ".dev-workflow" / agent_name / "skills" / skill_name
        )

        # Determine source
        source_dir = None
        if agent_skill_dir.is_dir():
            source_dir = agent_skill_dir
        elif dw_skill_dir.is_dir():
            source_dir = dw_skill_dir

        if source_dir is None:
            raise FileNotFoundError(
                f"Skill '{skill_name}' not found for agent '{agent_name}'"
            )

        # Destination: project-level skills
        dest_dir = project_primary_skills_dir(self.project_dir) / skill_name
        dest_dir.mkdir(parents=True, exist_ok=True)

        # Copy handler.md
        handler_src = source_dir / "handler.md"
        if handler_src.is_file():
            handler_dest = dest_dir / "handler.md"
            handler_dest.write_text(handler_src.read_text(encoding="utf-8"), encoding="utf-8")

        return dest_dir

    def get_unsynced_agents(self) -> list[str]:
        """Find sub-agents with unsynced memories.

        Scans .agent-flow/agents/ for agent state files.
        """
        agents_dir = self.project_dir / ".agent-flow" / "agents"
        if not agents_dir.is_dir():
            return []

        unsynced: list[str] = []
        for yaml_file in agents_dir.glob("*.yaml"):
            try:
                data = yaml.safe_load(yaml_file.read_text(encoding="utf-8"))
                if not isinstance(data, dict):
                    continue
                name = data.get("name", "")
                status = data.get("status", "")

                # Only check completed/terminated agents
                if status in ("completed", "terminated"):
                    sync_state = self._load_sync_state(name)
                    agent_memory = MemoryManager(self.project_dir, name)
                    soul = agent_memory.read_soul()
                    total = len(soul.get("dynamic", []))
                    synced = sync_state.get("synced_experience_count", 0)

                    if total > synced:
                        unsynced.append(name)
            except Exception:
                continue

        return unsynced

    def full_sync(self) -> dict:
        """Sync all sub-agent memories to main. Returns sync report."""
        unsynced = self.get_unsynced_agents()
        report: dict = {"synced_agents": [], "total_experiences": 0, "errors": []}

        for agent_name in unsynced:
            try:
                experiences = self.pull_experiences(agent_name)
                if experiences:
                    self.push_to_main(experiences, agent_name)

                    # Update sync state
                    agent_memory = MemoryManager(self.project_dir, agent_name)
                    soul = agent_memory.read_soul()
                    total = len(soul.get("dynamic", []))
                    self._save_sync_state(agent_name, total)

                    report["synced_agents"].append(agent_name)
                    report["total_experiences"] += len(experiences)
            except Exception as e:
                report["errors"].append(f"{agent_name}: {str(e)}")

        return report

    # -- Internal helpers -------------------------------------------------------

    def _load_sync_state(self, agent_name: str) -> dict:
        """Load sync state for an agent."""
        state_path = (
            self.project_dir
            / ".agent-flow"
            / "memory"
            / agent_name
            / self.SYNC_STATE_FILENAME
        )
        if not state_path.is_file():
            return {"synced_experience_count": 0}

        try:
            data = yaml.safe_load(state_path.read_text(encoding="utf-8"))
            return data if isinstance(data, dict) else {}
        except Exception:
            return {}

    def _save_sync_state(self, agent_name: str, synced_count: int) -> None:
        """Save sync state for an agent."""
        from datetime import datetime

        state_path = (
            self.project_dir
            / ".agent-flow"
            / "memory"
            / agent_name
            / self.SYNC_STATE_FILENAME
        )
        state_path.parent.mkdir(parents=True, exist_ok=True)

        state_data = {
            "last_sync": datetime.now().isoformat(),
            "synced_experience_count": synced_count,
        }
        state_path.write_text(
            yaml.dump(state_data, default_flow_style=False, sort_keys=False),
            encoding="utf-8",
        )
