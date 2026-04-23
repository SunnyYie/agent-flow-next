"""Git platform detection — auto-detect GitHub/GitLab/generic from remote URL and CLI availability."""

import shutil
import subprocess
from enum import Enum
from pathlib import Path


class GitPlatform(str, Enum):
    """Supported git hosting platforms."""

    GITHUB = "github"
    GITLAB = "gitlab"
    GENERIC = "generic"


def detect_git_platform(project_dir: Path | None = None) -> GitPlatform:
    """Detect the git hosting platform from remote URL and available CLIs.

    Priority:
    1. Check remote URL for github.com / gitlab patterns
    2. Check CLI availability (gh / glab)
    3. Fall back to generic
    """
    cwd = project_dir or Path.cwd()

    # Check remote URL first
    try:
        result = subprocess.run(
            ["git", "remote", "get-url", "origin"],
            capture_output=True,
            text=True,
            cwd=cwd,
        )
        if result.returncode == 0:
            url = result.stdout.strip().lower()
            if "github.com" in url or "github.enterprise" in url:
                return GitPlatform.GITHUB
            if "gitlab" in url:
                return GitPlatform.GITLAB
    except Exception:
        pass

    # Check CLI availability as fallback
    if shutil.which("gh"):
        # Verify gh is authenticated
        try:
            result = subprocess.run(
                ["gh", "auth", "status"],
                capture_output=True,
                text=True,
            )
            if result.returncode == 0:
                return GitPlatform.GITHUB
        except Exception:
            pass

    if shutil.which("glab"):
        try:
            result = subprocess.run(
                ["glab", "auth", "status"],
                capture_output=True,
                text=True,
            )
            if result.returncode == 0:
                return GitPlatform.GITLAB
        except Exception:
            pass

    return GitPlatform.GENERIC


def detect_base_branch(project_dir: Path | None = None) -> str:
    """Detect the default/base branch for the repository.

    Tries multiple methods:
    1. gh/glab API for default branch
    2. git symbolic-ref for remote HEAD
    3. Check for origin/main or origin/master
    4. Fall back to 'main'
    """
    cwd = project_dir or Path.cwd()
    platform = detect_git_platform(cwd)

    # Platform-specific detection
    if platform == GitPlatform.GITHUB:
        try:
            result = subprocess.run(
                ["gh", "repo", "view", "--json", "defaultBranchRef", "-q", ".defaultBranchRef.name"],
                capture_output=True,
                text=True,
                cwd=cwd,
            )
            if result.returncode == 0 and result.stdout.strip():
                return result.stdout.strip()
        except Exception:
            pass

    elif platform == GitPlatform.GITLAB:
        try:
            result = subprocess.run(
                ["glab", "repo", "view", "-F", "json"],
                capture_output=True,
                text=True,
                cwd=cwd,
            )
            if result.returncode == 0:
                import json

                data = json.loads(result.stdout)
                if "default_branch" in data:
                    return data["default_branch"]
        except Exception:
            pass

    # Git-native fallback
    try:
        result = subprocess.run(
            ["git", "symbolic-ref", "refs/remotes/origin/HEAD"],
            capture_output=True,
            text=True,
            cwd=cwd,
        )
        if result.returncode == 0:
            ref = result.stdout.strip()
            return ref.replace("refs/remotes/origin/", "")
    except Exception:
        pass

    # Check for main or master
    try:
        result = subprocess.run(
            ["git", "rev-parse", "--verify", "origin/main"],
            capture_output=True,
            text=True,
            cwd=cwd,
        )
        if result.returncode == 0:
            return "main"
    except Exception:
        pass

    try:
        result = subprocess.run(
            ["git", "rev-parse", "--verify", "origin/master"],
            capture_output=True,
            text=True,
            cwd=cwd,
        )
        if result.returncode == 0:
            return "master"
    except Exception:
        pass

    return "main"


def create_branch(
    branch_name: str,
    base_branch: str = "main",
    project_dir: Path | None = None,
) -> tuple[bool, str]:
    """Create a new git branch from the base branch.

    Returns (success, message).
    """
    cwd = project_dir or Path.cwd()

    # Fetch latest
    try:
        subprocess.run(
            ["git", "fetch", "origin", base_branch, "--quiet"],
            capture_output=True,
            text=True,
            cwd=cwd,
            check=True,
        )
    except subprocess.CalledProcessError as e:
        return False, f"Failed to fetch origin/{base_branch}: {e.stderr}"

    # Checkout base branch and pull
    try:
        subprocess.run(
            ["git", "checkout", base_branch],
            capture_output=True,
            text=True,
            cwd=cwd,
            check=True,
        )
        subprocess.run(
            ["git", "pull", "origin", base_branch, "--quiet"],
            capture_output=True,
            text=True,
            cwd=cwd,
            check=True,
        )
    except subprocess.CalledProcessError as e:
        return False, f"Failed to update {base_branch}: {e.stderr}"

    # Create new branch
    try:
        subprocess.run(
            ["git", "checkout", "-b", branch_name],
            capture_output=True,
            text=True,
            cwd=cwd,
            check=True,
        )
    except subprocess.CalledProcessError as e:
        return False, f"Failed to create branch {branch_name}: {e.stderr}"

    return True, f"Created and checked out branch {branch_name}"


def get_current_branch(project_dir: Path | None = None) -> str:
    """Get the current git branch name."""
    cwd = project_dir or Path.cwd()
    try:
        result = subprocess.run(
            ["git", "branch", "--show-current"],
            capture_output=True,
            text=True,
            cwd=cwd,
        )
        return result.stdout.strip() if result.returncode == 0 else ""
    except Exception:
        return ""


# Branches where direct development is prohibited — must create a feature branch
PROTECTED_BRANCH_PATTERNS = ("main", "master", "beta")


def is_protected_branch(branch_name: str) -> bool:
    """Check if a branch is protected (main/master/beta).

    Protected branches require creating a new feature branch before development.
    Any branch whose name contains a protected pattern is considered protected,
    e.g. 'main', 'beta/v2', 'master-hotfix' are all protected.
    """
    if not branch_name:
        return True  # detached HEAD or unknown → treat as protected
    return any(pattern in branch_name for pattern in PROTECTED_BRANCH_PATTERNS)


def get_branch_diff_stat(base_branch: str, project_dir: Path | None = None) -> str:
    """Get diff stats for the current branch vs base branch."""
    cwd = project_dir or Path.cwd()
    try:
        subprocess.run(
            ["git", "fetch", "origin", base_branch, "--quiet"],
            capture_output=True,
            text=True,
            cwd=cwd,
        )
        result = subprocess.run(
            ["git", "diff", f"origin/{base_branch}", "--stat"],
            capture_output=True,
            text=True,
            cwd=cwd,
        )
        return result.stdout if result.returncode == 0 else ""
    except Exception:
        return ""


def create_pull_request(
    title: str,
    body: str,
    base_branch: str = "main",
    project_dir: Path | None = None,
) -> tuple[bool, str]:
    """Create a pull request using the platform CLI.

    Returns (success, pr_url_or_error).
    """
    cwd = project_dir or Path.cwd()
    platform = detect_git_platform(cwd)

    if platform == GitPlatform.GITHUB:
        try:
            result = subprocess.run(
                [
                    "gh", "pr", "create",
                    "--title", title,
                    "--body", body,
                    "--base", base_branch,
                ],
                capture_output=True,
                text=True,
                cwd=cwd,
            )
            if result.returncode == 0:
                # Output contains the PR URL
                url = result.stdout.strip().split("\n")[-1]
                return True, url
            return False, f"gh pr create failed: {result.stderr}"
        except Exception as e:
            return False, f"gh not available: {e}"

    elif platform == GitPlatform.GITLAB:
        try:
            result = subprocess.run(
                [
                    "glab", "mr", "create",
                    "--title", title,
                    "--description", body,
                    "--target-branch", base_branch,
                    "--yes",
                ],
                capture_output=True,
                text=True,
                cwd=cwd,
            )
            if result.returncode == 0:
                url = result.stdout.strip().split("\n")[-1]
                return True, url
            return False, f"glab mr create failed: {result.stderr}"
        except Exception as e:
            return False, f"glab not available: {e}"

    else:
        return False, (
            "No git platform CLI detected. Install gh (GitHub) or glab (GitLab), "
            "or create the PR manually."
        )
