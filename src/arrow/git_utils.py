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


def resolve_commit(path: Path, ref: str) -> Optional[str]:
    """Resolve a ref (branch, tag, short SHA) to a full commit SHA."""
    return _git_cmd(path, "rev-parse", ref)


def list_files_at_commit(path: Path, commit: str) -> list[str]:
    """List all files in the repo at a given commit.

    Returns list of relative file paths.
    """
    output = _git_cmd(path, "ls-tree", "-r", "--name-only", commit)
    if output is None:
        return []
    return [line for line in output.splitlines() if line]


def get_file_at_commit(path: Path, commit: str, file_path: str) -> Optional[str]:
    """Get the content of a file at a specific commit.

    Returns file content as string, or None if the file doesn't exist
    at that commit or isn't valid text.
    """
    try:
        result = subprocess.run(
            ["git", "-C", str(path), "show", f"{commit}:{file_path}"],
            capture_output=True, check=False, timeout=10,
        )
        if result.returncode != 0:
            return None
        # Try to decode as text; skip binary files
        return result.stdout.decode("utf-8")
    except (FileNotFoundError, subprocess.TimeoutExpired, UnicodeDecodeError):
        return None


def get_commit_info(path: Path, commit: str) -> Optional[dict]:
    """Get metadata about a specific commit.

    Returns:
        {"sha": "...", "short_sha": "...", "message": "...", "author": "...", "date": "..."}
        or None if commit doesn't exist.
    """
    # Use a custom format to get all info in one call
    output = _git_cmd(
        path, "log", "-1", "--format=%H%n%h%n%s%n%an%n%aI", commit,
    )
    if output is None:
        return None
    lines = output.splitlines()
    if len(lines) < 5:
        return None
    return {
        "sha": lines[0],
        "short_sha": lines[1],
        "message": lines[2],
        "author": lines[3],
        "date": lines[4],
    }


def get_merge_base(path: Path, ref_a: str, ref_b: str) -> Optional[str]:
    """Find the merge base (common ancestor) of two refs."""
    return _git_cmd(path, "merge-base", ref_a, ref_b)


def get_pr_refs(path: Path, pr_number: int) -> Optional[dict]:
    """Get the base and head refs for a PR using gh CLI.

    Returns:
        {"base_branch": "main", "head_branch": "feature/x",
         "base_sha": "...", "head_sha": "...", "title": "...", "merge_base": "..."}
        or None if gh CLI is not available or PR not found.
    """
    try:
        result = subprocess.run(
            ["gh", "pr", "view", str(pr_number), "--json",
             "baseRefName,headRefName,headRefOid,title"],
            capture_output=True, text=True, check=True, timeout=15,
            cwd=str(path),
        )
    except (subprocess.CalledProcessError, FileNotFoundError, subprocess.TimeoutExpired):
        return None

    import json
    try:
        data = json.loads(result.stdout)
    except (json.JSONDecodeError, ValueError):
        return None

    head_sha = data.get("headRefOid")
    base_branch = data.get("baseRefName", "main")
    head_branch = data.get("headRefName", "")

    # Resolve base branch to a commit
    base_sha = resolve_commit(path, base_branch)

    # Find merge base for accurate diffing
    merge_base = None
    if base_sha and head_sha:
        merge_base = get_merge_base(path, base_sha, head_sha)

    return {
        "base_branch": base_branch,
        "head_branch": head_branch,
        "base_sha": base_sha,
        "head_sha": head_sha,
        "merge_base": merge_base,
        "title": data.get("title", ""),
    }


def get_changed_files_between(path: Path, base: str, head: str) -> list[str]:
    """Get list of files changed between two commits."""
    output = _git_cmd(path, "diff", "--name-only", base, head)
    if output is None:
        return []
    return [line for line in output.splitlines() if line]
