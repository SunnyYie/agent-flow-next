"""Layered event bus — in-process asyncio pubsub + file-based fallback.

Provides inter-agent communication for the multi-agent collaboration system.
In-process events are delivered instantly via asyncio queues.
Cross-process events use JSONL files in .agent-flow/events/.
"""

import asyncio
import json
import uuid
from datetime import datetime
from enum import Enum
from pathlib import Path

from pydantic import BaseModel, Field


class EventTopic(str, Enum):
    """Standard event topics for inter-agent communication."""

    TASK_ASSIGNED = "task.assigned"
    TASK_COMPLETED = "task.completed"
    TASK_FAILED = "task.failed"
    VERIFICATION_REQUEST = "verification.request"
    VERIFICATION_RESULT = "verification.result"
    EXPERIENCE_SYNC = "experience.sync"
    MEMORY_UPDATE = "memory.update"
    AGENT_SPAWNED = "agent.spawned"
    AGENT_TERMINATED = "agent.terminated"
    USER_INPUT_REQUIRED = "user.input_required"
    PHASE_TRANSITION = "phase.transition"
    ORCHESTRATOR_ANALYSIS = "orchestrator.analysis"


class AgentEvent(BaseModel):
    """An event in the agent communication system."""

    topic: EventTopic
    sender: str  # Agent name (e.g., "main", "executor-1")
    payload: dict = Field(default_factory=dict)
    timestamp: str = Field(default_factory=lambda: datetime.now().isoformat())
    event_id: str = Field(default_factory=lambda: str(uuid.uuid4())[:8])
    target: str = ""  # Empty = broadcast, specific agent name = targeted


class InProcessEventBus:
    """In-process asyncio pubsub for same-process agents (Claude Code sub-agents)."""

    def __init__(self) -> None:
        self._subscribers: dict[EventTopic, list[asyncio.Queue[AgentEvent]]] = {}
        self._event_log: list[AgentEvent] = []

    async def publish(self, event: AgentEvent) -> None:
        """Publish an event to all subscribers of the topic."""
        self._event_log.append(event)
        queues = self._subscribers.get(event.topic, [])
        for queue in queues:
            await queue.put(event)

    async def subscribe(self, topic: EventTopic) -> asyncio.Queue[AgentEvent]:
        """Subscribe to a topic. Returns a queue that receives events."""
        queue: asyncio.Queue[AgentEvent] = asyncio.Queue()
        if topic not in self._subscribers:
            self._subscribers[topic] = []
        self._subscribers[topic].append(queue)
        return queue

    def get_event_log(self) -> list[AgentEvent]:
        """Return all events published in this session."""
        return list(self._event_log)

    def clear_log(self) -> None:
        """Clear the event log."""
        self._event_log.clear()


class FileEventBus:
    """File-based event bus for cross-process communication.

    Uses .agent-flow/events/ directory with JSONL event files.
    Each process writes to its own file, reads all files for incoming events.
    """

    def __init__(self, project_dir: Path) -> None:
        self.events_dir = project_dir / ".agent-flow" / "events"
        self._process_id = str(uuid.uuid4())[:8]

    def _ensure_dir(self) -> None:
        self.events_dir.mkdir(parents=True, exist_ok=True)

    @property
    def _event_file(self) -> Path:
        return self.events_dir / f"{self._process_id}.jsonl"

    def publish(self, event: AgentEvent) -> None:
        """Append event to the process's event file as JSONL."""
        self._ensure_dir()
        line = event.model_dump_json() + "\n"
        with open(self._event_file, "a", encoding="utf-8") as f:
            f.write(line)

    def read_pending(self, last_read_timestamp: str = "") -> list[AgentEvent]:
        """Read all events from all process files since the given timestamp."""
        if not self.events_dir.is_dir():
            return []

        events: list[AgentEvent] = []
        for jsonl_file in self.events_dir.glob("*.jsonl"):
            try:
                for line in jsonl_file.read_text(encoding="utf-8").splitlines():
                    line = line.strip()
                    if not line:
                        continue
                    data = json.loads(line)
                    event = AgentEvent(**data)
                    if not last_read_timestamp or event.timestamp > last_read_timestamp:
                        events.append(event)
            except (json.JSONDecodeError, Exception):
                continue

        # Sort by timestamp
        events.sort(key=lambda e: e.timestamp)
        return events

    def cleanup_old_events(self, max_age_hours: int = 24) -> int:
        """Remove event files older than max_age_hours."""
        if not self.events_dir.is_dir():
            return 0

        now = datetime.now()
        removed = 0

        for jsonl_file in self.events_dir.glob("*.jsonl"):
            try:
                mtime = datetime.fromtimestamp(jsonl_file.stat().st_mtime)
                if (now - mtime).total_seconds() > max_age_hours * 3600:
                    jsonl_file.unlink()
                    removed += 1
            except OSError:
                continue

        return removed


class HybridEventBus:
    """Combines InProcessEventBus and FileEventBus.

    In-process events are delivered instantly via asyncio.
    Cross-process events are picked up from files on poll.
    For the current use case (Claude Code), only InProcessEventBus is active.
    FileEventBus is used when agents run as separate processes.
    """

    def __init__(self, project_dir: Path) -> None:
        self.in_process = InProcessEventBus()
        self.file_bus = FileEventBus(project_dir)
        self._poll_task: asyncio.Task | None = None  # type: ignore[type-arg]
        self._running = False

    async def publish(self, event: AgentEvent) -> None:
        """Publish to both in-process and file bus."""
        await self.in_process.publish(event)
        self.file_bus.publish(event)

    async def subscribe(self, topic: EventTopic) -> asyncio.Queue[AgentEvent]:
        """Subscribe via in-process bus."""
        return await self.in_process.subscribe(topic)

    async def start_polling(self, interval_seconds: float = 1.0) -> None:
        """Start polling file bus for cross-process events."""
        if self._running:
            return

        self._running = True

        async def _poll_loop() -> None:
            last_ts = ""
            while self._running:
                pending = self.file_bus.read_pending(last_ts)
                for event in pending:
                    await self.in_process.publish(event)
                    last_ts = event.timestamp
                await asyncio.sleep(interval_seconds)

        self._poll_task = asyncio.create_task(_poll_loop())

    async def stop_polling(self) -> None:
        """Stop the file bus polling task."""
        self._running = False
        if self._poll_task is not None:
            self._poll_task.cancel()
            try:
                await self._poll_task
            except asyncio.CancelledError:
                pass
            self._poll_task = None
