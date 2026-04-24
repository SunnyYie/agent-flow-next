"""TeamSync — Git-native knowledge synchronization for teams.

Manages pull/push of team knowledge repositories:
  - ``pull()``: Fast-forward then rebase fallback
  - ``push()``: Add + commit + push with user-provided message
  - ``status()``: Report ahead/behind/dirty state

All operations are local-first. No server-side coordination required.
The team knowledge repo is a standard Git repository containing skills,
wiki, hooks, and policies under ``~/.agent-flow/teams/{team-id}/knowledge/``.
"""

from __future__ import annotations

import subprocess
from dataclasses import dataclass, field
from pathlib import Path

from agent_flow.core.team import TEAMS_DIR, TeamConfig


# ── Data models ────────────────────────────────────────────────


@dataclass
class SyncResult:
    """Result of a sync operation."""

    success: bool
    message: str
    changed_files: list[str] = field(default_factory=list)


@dataclass
class SyncStatus:
    """Current sync status of a team knowledge repo."""

    is_repo: bool
    has_remote: bool
    ahead: int = 0
    behind: int = 0
    dirty: bool = False
    branch: str = ""
    remote_url: str = ""


# ── Manager ────────────────────────────────────────────────────


class TeamSyncManager:
    """Git-based team knowledge synchronization."""

    def __init__(self, team_id: str) -> None:
        self.team_id = team_id
        self.team_dir = TEAMS_DIR / team_id
        self.knowledge_dir = self.team_dir / "knowledge"

    # ── Pull ───────────────────────────────────────────────────

    def pull(self) -> SyncResult:
        """Pull latest team knowledge from remote.

        Strategy: ff-only first, then rebase fallback.
        """
        if not self._is_git_repo():
            return SyncResult(success=False, message="Knowledge directory is not a Git repo")

        if not self._has_remote():
            return SyncResult(success=False, message="No remote configured")

        # Try fast-forward first
        result = self._run_git(["pull", "--ff-only"])
        if result.returncode == 0:
            return SyncResult(
                success=True,
                message="Pulled (fast-forward)",
                changed_files=self._changed_files_after_pull(),
            )

        # Fallback to rebase
        result = self._run_git(["pull", "--rebase"])
        if result.returncode == 0:
            return SyncResult(
                success=True,
                message="Pulled (rebase)",
                changed_files=self._changed_files_after_pull(),
            )

        return SyncResult(
            success=False,
            message=f"Pull failed: {result.stderr.strip()}",
        )

    # ── Push ───────────────────────────────────────────────────

    def push(self, message: str) -> SyncResult:
        """Stage all changes, commit, and push to remote."""
        if not self._is_git_repo():
            return SyncResult(success=False, message="Knowledge directory is not a Git repo")

        if not self._has_remote():
            return SyncResult(success=False, message="No remote configured")

        # Check for changes
        status = self.status()
        if not status.dirty and status.ahead == 0:
            return SyncResult(success=True, message="Nothing to push")

        # Stage and commit if dirty
        if status.dirty:
            add_result = self._run_git(["add", "-A"])
            if add_result.returncode != 0:
                return SyncResult(success=False, message=f"git add failed: {add_result.stderr.strip()}")

            commit_result = self._run_git(["commit", "-m", message])
            if commit_result.returncode != 0:
                return SyncResult(success=False, message=f"git commit failed: {commit_result.stderr.strip()}")

        # Push
        push_result = self._run_git(["push"])
        if push_result.returncode != 0:
            return SyncResult(success=False, message=f"Push failed: {push_result.stderr.strip()}")

        return SyncResult(success=True, message="Pushed successfully")

    # ── Status ─────────────────────────────────────────────────

    def status(self) -> SyncStatus:
        """Report current sync status."""
        if not self._is_git_repo():
            return SyncStatus(is_repo=False, has_remote=False)

        has_remote = self._has_remote()
        branch = self._current_branch()
        remote_url = self._remote_url()
        dirty = self._is_dirty()
        ahead, behind = self._ahead_behind()

        return SyncStatus(
            is_repo=True,
            has_remote=has_remote,
            ahead=ahead,
            behind=behind,
            dirty=dirty,
            branch=branch,
            remote_url=remote_url,
        )

    # ── Clone / Init ───────────────────────────────────────────

    def clone(self, url: str, branch: str = "main") -> SyncResult:
        """Clone a remote knowledge repo into the team's knowledge directory."""
        if self.knowledge_dir.exists() and any(self.knowledge_dir.iterdir()):
            return SyncResult(success=False, message="Knowledge directory not empty, cannot clone")

        self.knowledge_dir.mkdir(parents=True, exist_ok=True)
        result = self._run_git(
            ["clone", "-b", branch, url, "."],
            cwd=self.knowledge_dir,
        )
        if result.returncode != 0:
            return SyncResult(success=False, message=f"Clone failed: {result.stderr.strip()}")

        return SyncResult(success=True, message=f"Cloned from {url}")

    def init_repo(self) -> SyncResult:
        """Initialize a new Git repo in the knowledge directory."""
        self.knowledge_dir.mkdir(parents=True, exist_ok=True)
        result = self._run_git(["init"], cwd=self.knowledge_dir)
        if result.returncode != 0:
            return SyncResult(success=False, message=f"Init failed: {result.stderr.strip()}")

        # Create initial commit so branch exists
        readme = self.knowledge_dir / "README.md"
        readme.write_text(f"# {self.team_id} Team Knowledge\n", encoding="utf-8")
        self._run_git(["add", "README.md"], cwd=self.knowledge_dir)
        self._run_git(["commit", "-m", "Initial team knowledge repo"], cwd=self.knowledge_dir)

        return SyncResult(success=True, message="Initialized team knowledge repo")

    # ── Git helpers ────────────────────────────────────────────

    def _run_git(self, args: list[str], cwd: Path | None = None) -> subprocess.CompletedProcess[str]:
        return subprocess.run(
            ["git"] + args,
            cwd=str(cwd or self.knowledge_dir),
            capture_output=True,
            text=True,
            timeout=30,
        )

    def _is_git_repo(self) -> bool:
        return (self.knowledge_dir / ".git").is_dir()

    def _has_remote(self) -> bool:
        if not self._is_git_repo():
            return False
        result = self._run_git(["remote"])
        return bool(result.stdout.strip())

    def _current_branch(self) -> str:
        result = self._run_git(["branch", "--show-current"])
        return result.stdout.strip()

    def _remote_url(self) -> str:
        result = self._run_git(["remote", "get-url", "origin"])
        return result.stdout.strip() if result.returncode == 0 else ""

    def _is_dirty(self) -> bool:
        result = self._run_git(["status", "--porcelain"])
        return bool(result.stdout.strip())

    def _ahead_behind(self) -> tuple[int, int]:
        branch = self._current_branch()
        if not branch:
            return 0, 0
        result = self._run_git(["rev-list", "--left-right", "--count", f"origin/{branch}...HEAD"])
        if result.returncode != 0:
            return 0, 0
        parts = result.stdout.strip().split()
        if len(parts) != 2:
            return 0, 0
        try:
            return int(parts[1]), int(parts[0])  # ahead, behind
        except ValueError:
            return 0, 0

    def _changed_files_after_pull(self) -> list[str]:
        result = self._run_git(["diff", "--name-only", "HEAD@{1}", "HEAD"])
        if result.returncode != 0:
            return []
        return [f for f in result.stdout.strip().split("\n") if f]
