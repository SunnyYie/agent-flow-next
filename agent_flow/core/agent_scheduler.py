"""Agent scheduler — spawning, lifecycle, and task management.

Manages sub-agent creation, state tracking, memory isolation,
and result collection for multi-agent collaboration.
"""

import uuid
from datetime import datetime
from enum import Enum
from pathlib import Path

import yaml
from pydantic import BaseModel, Field

from agent_flow.core.event_bus import HybridEventBus, AgentEvent, EventTopic


class AgentSpec(BaseModel):
    """Specification for spawning a sub-agent."""

    name: str = ""  # Unique instance name (e.g., "executor-1")
    role: str = "executor"  # executor, verifier, researcher, tech-leader, orchestrator
    task_description: str = ""
    task_type: str = ""  # For orchestrator workers: the specific subtask type
    task_context: dict = Field(default_factory=dict)  # Structured state context
    memory_scope: str = "isolated"  # isolated|shared|read-only-shared
    skills_paths: list[str] = Field(default_factory=list)
    soul_template: str = ""
    parent_agent: str = "main"
    timeout_minutes: int = 30
    recursion_depth: int = 0  # 0=can spawn sub-agents, 1=cannot (max 1 level)


class AgentStatus(str, Enum):
    SPAWNING = "spawning"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    TERMINATED = "terminated"


class AgentRecord(BaseModel):
    """Runtime record of a spawned agent."""

    spec: AgentSpec
    status: AgentStatus = AgentStatus.SPAWNING
    started_at: str = ""
    completed_at: str = ""
    result_summary: str = ""
    memory_dir: str = ""


class AgentScheduler:
    """Manages sub-agent lifecycle: spawning, tracking, memory isolation, and result collection."""

    MAX_PARALLEL_AGENTS = 3

    def __init__(self, project_dir: Path, event_bus: HybridEventBus) -> None:
        self.project_dir = project_dir
        self.event_bus = event_bus
        self._agents: dict[str, AgentRecord] = {}
        self._agents_dir = project_dir / ".agent-flow" / "agents"

    def spawn_agent(self, spec: AgentSpec) -> AgentRecord:
        """Create a new agent record, set up its memory directory.

        Memory isolation: each agent gets .agent-flow/memory/{name}/
        with its own Memory.md and Soul.md.

        Raises:
            ValueError: If recursion_depth > 1.
        """
        # Validate recursion depth
        if spec.recursion_depth > 1:
            raise ValueError(
                f"Recursion depth {spec.recursion_depth} exceeds maximum of 1. "
                f"Sub-agents cannot spawn further sub-agents."
            )

        # Generate unique name if not provided
        if not spec.name:
            spec.name = f"{spec.role}-{uuid.uuid4().hex[:6]}"

        # Set up memory directory
        memory_dir = self.project_dir / ".agent-flow" / "memory" / spec.name
        memory_dir.mkdir(parents=True, exist_ok=True)

        # Create minimal Memory.md and Soul.md for the agent
        (memory_dir / "Memory.md").write_text(
            f"# 工作记忆 — {spec.name}\n\n", encoding="utf-8"
        )

        soul_fixed_lines = (
            f"# Soul: {spec.name} ({spec.role})\n\n"
            f"## 固定区\n\n"
            f"- 角色: {spec.role}\n"
            f"- 任务: {spec.task_description}\n"
            f"- 父Agent: {spec.parent_agent}\n"
        )
        if spec.recursion_depth == 1:
            soul_fixed_lines += f"- 递归深度限制: 你不能再派发子Agent\n"

        (memory_dir / "Soul.md").write_text(
            soul_fixed_lines + f"\n## 动态区\n\n",
            encoding="utf-8",
        )

        # Create agent record
        record = AgentRecord(
            spec=spec,
            status=AgentStatus.RUNNING,
            started_at=datetime.now().isoformat(),
            memory_dir=str(memory_dir.relative_to(self.project_dir)),
        )
        self._agents[spec.name] = record

        # Save state to YAML
        self._save_agent_state(record)

        # Emit event
        import asyncio

        event = AgentEvent(
            topic=EventTopic.AGENT_SPAWNED,
            sender=spec.parent_agent,
            payload={
                "name": spec.name,
                "role": spec.role,
                "task": spec.task_description,
            },
        )
        try:
            loop = asyncio.get_running_loop()
            loop.create_task(self.event_bus.publish(event))
        except RuntimeError:
            # No running loop, publish to file bus only
            self.event_bus.file_bus.publish(event)

        return record

    def terminate_agent(self, name: str, result_summary: str = "") -> None:
        """Mark agent as terminated, sync its memory back to main agent."""
        if name not in self._agents:
            return

        record = self._agents[name]
        record.status = AgentStatus.TERMINATED
        record.completed_at = datetime.now().isoformat()
        record.result_summary = result_summary

        # Update state file
        self._save_agent_state(record)

        # Emit event
        import asyncio

        event = AgentEvent(
            topic=EventTopic.AGENT_TERMINATED,
            sender=name,
            payload={"result_summary": result_summary},
        )
        try:
            loop = asyncio.get_running_loop()
            loop.create_task(self.event_bus.publish(event))
        except RuntimeError:
            self.event_bus.file_bus.publish(event)

    def get_agent(self, name: str) -> AgentRecord | None:
        """Look up an agent by name."""
        return self._agents.get(name)

    def list_active_agents(self) -> list[AgentRecord]:
        """Return all currently running agents."""
        return [r for r in self._agents.values() if r.status == AgentStatus.RUNNING]

    def list_all_agents(self) -> list[AgentRecord]:
        """Return all agent records."""
        return list(self._agents.values())

    def can_spawn_more(self) -> bool:
        """Check if we're under the parallel agent limit."""
        return len(self.list_active_agents()) < self.MAX_PARALLEL_AGENTS

    def can_spawn_sub_agent(self, parent_name: str) -> bool:
        """Check if a parent agent can spawn a sub-agent.

        A parent can spawn a sub-agent only if:
        - Its recursion_depth is 0 (has not already spawned a sub-agent)
        - The active agent count is still under MAX_PARALLEL_AGENTS

        Args:
            parent_name: Name of the parent agent.

        Returns:
            True if the parent can spawn a sub-agent, False otherwise.
        """
        parent = self._agents.get(parent_name)
        if not parent or parent.spec.recursion_depth >= 1:
            return False
        return self.can_spawn_more()

    def spawn_sub_agent(self, parent_name: str, spec: AgentSpec) -> AgentRecord:
        """Spawn a sub-agent from a parent agent, with recursion depth check.

        The sub-agent's recursion_depth is set to parent's depth + 1.
        Maximum recursion depth is 1 (sub-agents cannot spawn further agents).

        Args:
            parent_name: Name of the parent agent.
            spec: Agent specification for the sub-agent.

        Returns:
            The newly created AgentRecord.

        Raises:
            ValueError: If the parent cannot spawn sub-agents.
        """
        parent = self._agents.get(parent_name)
        if not parent:
            raise ValueError(f"Parent agent '{parent_name}' not found")
        if parent.spec.recursion_depth >= 1:
            raise ValueError(
                f"Parent agent '{parent_name}' has recursion_depth={parent.spec.recursion_depth}. "
                f"Cannot spawn sub-agents beyond depth 1."
            )
        if not self.can_spawn_more():
            raise ValueError(
                f"Cannot spawn sub-agent: active agent limit ({self.MAX_PARALLEL_AGENTS}) reached"
            )

        # Set up sub-agent spec
        spec.recursion_depth = parent.spec.recursion_depth + 1
        spec.parent_agent = parent_name
        if not spec.name:
            spec.name = f"{parent_name}-sub-{uuid.uuid4().hex[:4]}"

        return self.spawn_agent(spec)

    def spawn_tech_leader_review(
        self, content_path: Path, review_criteria: list[str]
    ) -> AgentRecord:
        """Special method: spawn a tech-leader agent for architecture review."""
        spec = AgentSpec(
            role="tech-leader",
            task_description=f"Review {content_path} against criteria: {', '.join(review_criteria)}",
            memory_scope="read-only-shared",
            parent_agent="main",
        )
        return self.spawn_agent(spec)

    def get_agent_spawn_prompt(self, spec: AgentSpec) -> str:
        """Generate the prompt text for spawning a sub-agent via the Agent tool.

        Incorporates user model preferences into the prompt.
        """
        role_descriptions = {
            "executor": "Executor Agent（执行者）",
            "verifier": "Verifier Agent（验证者）",
            "researcher": "Researcher Agent（研究者）",
            "searcher": "Searcher Agent（知识检索者）",
            "tech-leader": "Tech Leader Agent（技术负责人）",
            "orchestrator": "Orchestrator Agent（编排者）",
        }

        role_desc = role_descriptions.get(spec.role, spec.role)

        # Build structured context section for orchestrator workers
        context_section = ""
        if spec.task_type:
            context_section += f"\n## 子任务类型\n{spec.task_type}\n"
        if spec.task_context:
            import json
            context_section += f"\n## 结构化上下文\n```json\n{json.dumps(spec.task_context, ensure_ascii=False, indent=2)}\n```\n"

        # Orchestrator-specific instructions
        orchestrator_section = ""
        if spec.role == "orchestrator":
            orchestrator_section = """
## 编排者专属规则
1. 分析任务后，使用 XML 格式输出: <analysis> + <tasks>
2. 每个 task 必须包含 <type> 和 <description>
3. 工作者必须收到完整上下文（原始任务 + 子任务类型 + 描述）
4. 收集工作者结果时，检测空值和错误输出并兜底处理
5. 参考技能: ~/.agent-flow/skills/orchestrator-worker/handler.md
"""

        # Recursion depth instructions
        recursion_section = ""
        if spec.recursion_depth == 0:
            recursion_section = "如果自身上下文即将溢出，你可以再派发1层子Agent（设 recursion_depth=1）"
        elif spec.recursion_depth == 1:
            recursion_section = "递归深度限制: 你不能派发子Agent，必须在自身上下文中完成任务"

        prompt = f"""你是 {role_desc}。

## 身份
- 角色: {spec.role}
- 任务: {spec.task_description}
- 父Agent: {spec.parent_agent}

## 核心规则
1. 严格按照任务描述执行，不做超出任务范围的事
2. 完成后报告完成情况，列出所有创建/修改的文件
3. 遇到问题时，先搜索 .agent-flow/skills/ 和 ~/.agent-flow/skills/ 查找相关技能
4. 将执行过程记录到你的 Memory.md 中
5. 完成前必须在你的 Memory.md 中输出一段结构化总结，至少覆盖：搜索复盘、业务/代码定位复盘、执行流程复盘、最佳实践复盘
6. 完成后将关键经验记录到你的 Soul.md 动态区
{orchestrator_section}
## 递归深度
{recursion_section}

## 记忆路径
- 工作记忆: {spec.memory_scope == 'isolated' and f'.agent-flow/memory/{spec.name}/Memory.md' or '.agent-flow/memory/main/Memory.md'}
- 角色经验: {spec.memory_scope == 'isolated' and f'.agent-flow/memory/{spec.name}/Soul.md' or '.agent-flow/memory/main/Soul.md'}
{context_section}
## 当前任务
{spec.task_description}

## 报告格式
### 完成情况
列出所有创建/修改的文件，测试结果

### 经验提取
学到的模式、遇到的问题、建议

### 结构化总结
- 搜索复盘：
- 业务与代码定位复盘：
- 任务执行流程复盘：
- 最佳实践复盘：
"""
        return prompt

    def _save_agent_state(self, record: AgentRecord) -> None:
        """Save agent state to .agent-flow/agents/{name}.yaml."""
        self._agents_dir.mkdir(parents=True, exist_ok=True)
        state_path = self._agents_dir / f"{record.spec.name}.yaml"

        state_data = {
            "name": record.spec.name,
            "role": record.spec.role,
            "status": record.status.value,
            "started_at": record.started_at,
            "completed_at": record.completed_at,
            "task": record.spec.task_description,
            "parent": record.spec.parent_agent,
            "memory_dir": record.memory_dir,
        }

        state_path.write_text(
            yaml.dump(state_data, default_flow_style=False, sort_keys=False),
            encoding="utf-8",
        )

    def _load_agent_states(self) -> None:
        """Load all agent state files from .agent-flow/agents/."""
        if not self._agents_dir.is_dir():
            return

        for yaml_file in self._agents_dir.glob("*.yaml"):
            try:
                data = yaml.safe_load(yaml_file.read_text(encoding="utf-8"))
                if not isinstance(data, dict):
                    continue

                spec = AgentSpec(
                    name=data.get("name", yaml_file.stem),
                    role=data.get("role", "executor"),
                    task_description=data.get("task", ""),
                    parent_agent=data.get("parent", "main"),
                )
                record = AgentRecord(
                    spec=spec,
                    status=AgentStatus(data.get("status", "terminated")),
                    started_at=data.get("started_at", ""),
                    completed_at=data.get("completed_at", ""),
                    memory_dir=data.get("memory_dir", ""),
                )
                self._agents[spec.name] = record
            except Exception:
                continue
