"""Git utilities for extracting repo identity, branch, and commit info."""

from __future__ import annotations

import re
import subprocess
from pathlib import Path
from typing import Optional


def is_git_repo(path: Path) -> bool:
    """Check if path is inside a git repository."""
    try:
        subprocess.run(
            ["git", "-C", str(path), "rev-parse", "--git-dir"],
            capture_output=True, check=True, timeout=5,
        )
        return True
    except (subprocess.CalledProcessError, FileNotFoundError, subprocess.TimeoutExpired):
        return False


def parse_remote_url(url: str) -> tuple[str, str]:
    """Extract (org, repo) from a git remote URL.

    Handles:
        https://github.com/org/repo.git
        git@github.com:org/repo.git
        ssh://git@github.com/org/repo.git
    """
    # SSH: git@host:org/repo.git
    m = re.match(r"git@[^:]+:(.+?)(?:\.git)?$", url)
    if m:
        parts = m.group(1).split("/")
        if len(parts) >= 2:
            return parts[-2], parts[-1]

    # HTTPS or SSH with path: https://host/org/repo.git
    m = re.match(r"(?:https?|ssh)://[^/]+/(.+?)(?:\.git)?$", url)
    if m:
        parts = m.group(1).split("/")
        if len(parts) >= 2:
            return parts[-2], parts[-1]

    return "", url.rstrip("/").rsplit("/", 1)[-1].replace(".git", "")


def _git_cmd(path: Path, *args: str) -> Optional[str]:
    """Run a git command and return stdout, or None on failure."""
    try:
        result = subprocess.run(
            ["git", "-C", str(path)] + list(args),
            capture_output=True, text=True, check=True, timeout=5,
        )
        return result.stdout.strip()
    except (subprocess.CalledProcessError, FileNotFoundError, subprocess.TimeoutExpired):
        return None


def get_git_info(path: Path) -> dict:
    """Extract git metadata from a local repository.

    Returns:
        {
            "name": "org/repo" or directory name,
            "branch": "main" or None,
            "commit": "abc123..." or None,
            "remote_url": "https://..." or None,
        }
    """
    path = Path(path).resolve()

    if not is_git_repo(path):
        return {
            "name": path.name,
            "branch": None,
            "commit": None,
            "remote_url": None,
        }

    remote_url = _git_cmd(path, "remote", "get-url", "origin")
    branch = _git_cmd(path, "rev-parse", "--abbrev-ref", "HEAD")
    commit = _git_cmd(path, "rev-parse", "HEAD")

    if remote_url:
        org, repo = parse_remote_url(remote_url)
        name = f"{org}/{repo}" if org else repo
    else:
        name = path.name

    return {
        "name": name,
        "branch": branch,
        "commit": commit,
        "remote_url": remote_url,
    }


def has_new_commits(path: Path, known_commit: str) -> bool:
    """Check if HEAD has moved past the known commit."""
    current = _git_cmd(path, "rev-parse", "HEAD")
    if current is None:
        return False
    return current != known_commit
