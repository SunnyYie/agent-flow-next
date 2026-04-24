"""CLI command group: agent-flow agent — Manage sub-agents and collaboration."""

import click

from agent_flow.core.agent_scheduler import AgentScheduler, AgentSpec, AgentStatus
from agent_flow.core.event_bus import HybridEventBus
from agent_flow.core.agent_memory_sync import AgentMemorySync
from pathlib import Path


@click.group("agent")
def cli() -> None:
    """Manage sub-agents and collaboration."""
    pass


@cli.command("list")
@click.option("--project-dir", default=".", help="Project root directory")
def list_cmd(project_dir: str) -> None:
    """List all active and recently terminated sub-agents."""
    project_path = Path(project_dir).resolve()
    event_bus = HybridEventBus(project_path)
    scheduler = AgentScheduler(project_path, event_bus)

    # Load existing agent states
    scheduler._load_agent_states()

    agents = scheduler.list_all_agents()
    if not agents:
        click.echo("No sub-agents found.")
        return

    active = [a for a in agents if a.status == AgentStatus.RUNNING]
    inactive = [a for a in agents if a.status != AgentStatus.RUNNING]

    if active:
        click.echo("Active agents:\n")
        for a in active:
            click.echo(f"  [{a.spec.name}] {a.spec.role} — {a.spec.task_description[:60]}")
            click.echo(f"    Started: {a.started_at} | Status: {a.status.value}")
            click.echo()

    if inactive:
        click.echo("Inactive agents:\n")
        for a in inactive:
            click.echo(f"  [{a.spec.name}] {a.spec.role} — {a.status.value}")
            click.echo(f"    Task: {a.spec.task_description[:60]}")
            click.echo()


@cli.command("spawn")
@click.option("--role", type=click.Choice(["executor", "verifier", "researcher", "tech-leader"]), required=True)
@click.option("--task", required=True, help="Task description for the sub-agent")
@click.option("--name", default="", help="Custom name for the agent instance")
@click.option("--project-dir", default=".", help="Project root directory")
def spawn_cmd(role: str, task: str, name: str, project_dir: str) -> None:
    """Spawn a new sub-agent with the specified role and task."""
    project_path = Path(project_dir).resolve()
    event_bus = HybridEventBus(project_path)
    scheduler = AgentScheduler(project_path, event_bus)
    scheduler._load_agent_states()

    if not scheduler.can_spawn_more():
        click.echo("Maximum parallel agents reached. Terminate an agent first.")
        return

    spec = AgentSpec(
        name=name,
        role=role,
        task_description=task,
    )

    record = scheduler.spawn_agent(spec)

    click.echo(f"Agent spawned: {record.spec.name}")
    click.echo(f"  Role: {record.spec.role}")
    click.echo(f"  Task: {record.spec.task_description}")
    click.echo(f"  Memory: {record.memory_dir}")

    # Generate and show the spawn prompt
    prompt = scheduler.get_agent_spawn_prompt(record.spec)
    click.echo("\n--- Agent Spawn Prompt ---\n")
    click.echo(prompt)


@cli.command("terminate")
@click.argument("agent_name")
@click.option("--result", default="", help="Result summary")
@click.option("--project-dir", default=".", help="Project root directory")
def terminate_cmd(agent_name: str, result: str, project_dir: str) -> None:
    """Terminate a running sub-agent and sync its memory."""
    project_path = Path(project_dir).resolve()
    event_bus = HybridEventBus(project_path)
    scheduler = AgentScheduler(project_path, event_bus)
    scheduler._load_agent_states()

    record = scheduler.get_agent(agent_name)
    if record is None:
        click.echo(f"Agent '{agent_name}' not found.")
        raise SystemExit(1)

    if record.status != AgentStatus.RUNNING:
        click.echo(f"Agent '{agent_name}' is not running (status: {record.status.value}).")
        return

    scheduler.terminate_agent(agent_name, result_summary=result)

    # Auto-sync memory
    sync = AgentMemorySync(project_path)
    try:
        experiences = sync.pull_experiences(agent_name)
        if experiences:
            sync.push_to_main(experiences, agent_name)
            click.echo(f"Synced {len(experiences)} experiences to main agent.")
    except Exception as e:
        click.echo(f"Warning: Memory sync failed: {e}")

    click.echo(f"Agent '{agent_name}' terminated.")


@cli.command("sync")
@click.option("--agent-name", default="", help="Sync a specific agent's memory. Empty = sync all.")
@click.option("--project-dir", default=".", help="Project root directory")
def sync_cmd(agent_name: str, project_dir: str) -> None:
    """Sync sub-agent memories back to main agent."""
    project_path = Path(project_dir).resolve()
    sync = AgentMemorySync(project_path)

    if agent_name:
        try:
            experiences = sync.pull_experiences(agent_name)
            if not experiences:
                click.echo(f"No new experiences to sync from '{agent_name}'.")
                return

            sync.push_to_main(experiences, agent_name)
            click.echo(f"Synced {len(experiences)} experiences from '{agent_name}' to main agent.")
        except FileNotFoundError as e:
            click.echo(str(e))
    else:
        report = sync.full_sync()
        if report["synced_agents"]:
            click.echo(f"Synced {report['total_experiences']} experiences from {len(report['synced_agents'])} agents:")
            for name in report["synced_agents"]:
                click.echo(f"  - {name}")
        else:
            click.echo("No unsynced agents found.")

        if report["errors"]:
            click.echo("\nErrors:")
            for err in report["errors"]:
                click.echo(f"  - {err}")
