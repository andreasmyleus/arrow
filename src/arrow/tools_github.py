"""GitHub and remote indexing tools — clone, index, git commits, PRs."""

from __future__ import annotations

import json
import subprocess
import threading
from pathlib import Path

from .server import (
    DEFAULT_CLONE_DIR,
    _get_indexer,
    _get_storage,
    _project_locks,
    mcp,
)


@mcp.tool()
def index_github_content(
    owner: str, repo: str, branch: str, files: list[dict]
) -> str:
    """Index code from a remote GitHub repository. Pass file content that
    you've already read via the GitHub MCP server.

    This caches remote code locally so Arrow can search across both local
    and remote repos.

    Args:
        owner: GitHub org or username (e.g. "anthropics").
        repo: Repository name (e.g. "claude-code").
        branch: Branch name (e.g. "main").
        files: List of {"path": "src/foo.py", "content": "..."} dicts.

    Returns:
        JSON status with file/chunk counts and timing.
    """
    if not owner or not owner.strip():
        return json.dumps({"error": "owner is required"})
    if not repo or not repo.strip():
        return json.dumps({"error": "repo is required"})
    if not branch or not branch.strip():
        return json.dumps({"error": "branch is required"})
    if not files:
        return json.dumps({"error": "files list is required and must not be empty"})
    for idx, entry in enumerate(files):
        if not isinstance(entry, dict) or "path" not in entry:
            return json.dumps(
                {"error": f"files[{idx}] must have 'path' and 'content' keys"}
            )
        if not entry["path"] or not entry["path"].strip():
            return json.dumps({"error": f"files[{idx}].path must not be empty"})

    indexer = _get_indexer()
    result = indexer.index_remote_files(owner, repo, branch, files)
    return json.dumps(result, indent=2)


@mcp.tool()
def index_github_repo(
    owner: str, repo: str, branch: str = "main",
    sparse_paths: list[str] | None = None,
) -> str:
    """Clone and index a GitHub repo using `gh` CLI. Fetches code automatically
    so you don't need to read files first. Checks the index first and skips
    if already up-to-date.

    Uses shallow clone for speed. Optionally use sparse_paths to index only
    specific directories (e.g. ["src/", "lib/"]).

    Args:
        owner: GitHub org or username (e.g. "anthropics").
        repo: Repository name (e.g. "claude-code").
        branch: Branch name (default "main").
        sparse_paths: Optional list of paths to clone (sparse checkout).
                      Omit to clone the entire repo.

    Returns:
        JSON status with file/chunk counts, timing, and clone path.
    """
    import shutil

    if not owner or not owner.strip():
        return json.dumps({"error": "owner is required"})
    if not repo or not repo.strip():
        return json.dumps({"error": "repo is required"})

    name = f"{owner}/{repo}"
    storage = _get_storage()

    # Check if already indexed and fresh
    existing = storage.get_project_by_name(name)
    if existing and existing.git_branch == branch and existing.last_indexed:
        # Check if the remote has new commits
        try:
            result = subprocess.run(
                ["gh", "api", f"repos/{owner}/{repo}/commits/{branch}",
                 "--jq", ".sha"],
                capture_output=True, text=True, timeout=10,
            )
            remote_sha = result.stdout.strip()
            if remote_sha and existing.git_commit == remote_sha:
                return json.dumps({
                    "status": "already indexed",
                    "project": name,
                    "branch": branch,
                    "commit": remote_sha[:8],
                    "last_indexed": existing.last_indexed,
                    "hint": (
                        "Index is up-to-date. Use search_code() or "
                        "get_context() with project=\""
                        f"{name}\" to search."
                    ),
                }, indent=2)
        except Exception:
            pass  # Can't check, proceed with clone

    # Clone to a persistent location so re-indexes are incremental
    clone_dir = DEFAULT_CLONE_DIR / owner / repo
    clone_dir.parent.mkdir(parents=True, exist_ok=True)

    if clone_dir.is_dir():
        # Update existing clone — handle both branches and tags
        try:
            # Fetch the ref (works for branches; tags need --tags)
            subprocess.run(
                ["git", "-C", str(clone_dir), "fetch", "origin", branch,
                 "--depth=1", "--tags"],
                capture_output=True, text=True, timeout=60,
            )
            # Try origin/<branch> first (branch), then <branch> directly (tag)
            checkout_result = subprocess.run(
                ["git", "-C", str(clone_dir), "checkout",
                 f"origin/{branch}", "--force"],
                capture_output=True, text=True, timeout=30,
            )
            if checkout_result.returncode != 0:
                # Likely a tag — checkout by name directly
                subprocess.run(
                    ["git", "-C", str(clone_dir), "checkout",
                     branch, "--force"],
                    capture_output=True, text=True, timeout=30,
                )
        except Exception:
            # If update fails, remove and re-clone
            shutil.rmtree(clone_dir, ignore_errors=True)
            clone_dir = None

    if not clone_dir or not clone_dir.is_dir():
        clone_dir = DEFAULT_CLONE_DIR / owner / repo
        clone_dir.parent.mkdir(parents=True, exist_ok=True)

        clone_cmd = [
            "gh", "repo", "clone", f"{owner}/{repo}", str(clone_dir),
            "--", "--depth=1", f"--branch={branch}",
        ]
        if sparse_paths:
            clone_cmd.extend(["--sparse"])

        try:
            result = subprocess.run(
                clone_cmd, capture_output=True, text=True, timeout=120,
            )
            if result.returncode != 0:
                return json.dumps({
                    "error": f"Clone failed: {result.stderr.strip()}",
                    "hint": "Is `gh` CLI installed and authenticated? "
                            "Run `gh auth status` to check.",
                })
        except FileNotFoundError:
            return json.dumps({
                "error": "`gh` CLI not found. Install it: "
                         "https://cli.github.com/",
            })
        except subprocess.TimeoutExpired:
            return json.dumps({
                "error": "Clone timed out (120s). Try with sparse_paths "
                         "to clone only specific directories.",
            })

        # Set up sparse checkout if needed
        if sparse_paths and clone_dir.is_dir():
            subprocess.run(
                ["git", "-C", str(clone_dir),
                 "sparse-checkout", "set"] + sparse_paths,
                capture_output=True, text=True, timeout=30,
            )

    # Index the cloned repo
    indexer = _get_indexer()
    idx_result = indexer.index_codebase(clone_dir)

    # Rename project to owner/repo format
    pid = idx_result.get("project_id")
    if pid:
        proj = storage.get_project(pid)
        if proj and proj.name != name:
            try:
                storage.conn.execute(
                    "UPDATE projects SET name = ? WHERE id = ?",
                    (name, pid),
                )
                storage.conn.commit()
                idx_result["project_name"] = name
            except Exception:
                pass  # Name conflict, keep auto-detected name

    # Verify we indexed the latest version
    indexed_project = storage.get_project(pid) if pid else None
    if indexed_project and indexed_project.git_commit:
        try:
            remote_check = subprocess.run(
                ["gh", "api", f"repos/{owner}/{repo}/commits/{branch}",
                 "--jq", ".sha"],
                capture_output=True, text=True, timeout=10,
            )
            remote_sha = remote_check.stdout.strip()
            if remote_sha and remote_sha != indexed_project.git_commit:
                idx_result["warning"] = (
                    f"Index commit ({indexed_project.git_commit[:8]}) "
                    f"differs from remote HEAD ({remote_sha[:8]}). "
                    f"The clone may not have updated fully. "
                    f"Try removing {clone_dir} and re-running."
                )
        except Exception:
            pass  # Non-critical check

    idx_result["clone_path"] = str(clone_dir)
    idx_result["hint"] = (
        f"Indexed. Use search_code() or get_context() with "
        f"project=\"{idx_result.get('project_name', name)}\" to search."
    )
    return json.dumps(idx_result, indent=2)


@mcp.tool()
def index_git_commit(path: str, ref: str) -> str:
    """Index a codebase at a specific git commit, tag, or branch.

    Creates a snapshot project named "org/repo@<ref>" that can be searched
    independently. Useful for comparing code across versions, investigating
    old commits, or caching historical code state.

    Args:
        path: Path to the local git repository.
        ref: Git ref — commit SHA (full or short), tag name, or branch name.

    Returns:
        JSON status with file/chunk counts, commit info, and timing.
    """
    if not path or not path.strip():
        return json.dumps({"error": "path is required"})
    if not ref or not ref.strip():
        return json.dumps({"error": "ref is required"})
    root = Path(path).resolve()
    if not root.is_dir():
        return json.dumps({"error": f"Not a directory: {path}"})

    indexer = _get_indexer()

    # Acquire lock based on the root path (not project, since it may not exist yet)
    lock_key = f"snapshot:{root}:{ref}"
    lock = _project_locks.setdefault(lock_key, threading.Lock())
    if not lock.acquire(timeout=30):
        return json.dumps({"error": "Another indexing operation is in progress for this ref"})

    try:
        result = indexer.index_git_commit(root, ref)
    finally:
        lock.release()

    return json.dumps(result, indent=2)


@mcp.tool()
def index_pr(path: str, pr_number: int) -> str:
    """Index both sides of a pull request for comparison and review.

    Uses `gh pr view` to get PR metadata, then indexes the merge base
    (before the PR) and the PR head (after the PR). Both snapshots are
    searchable independently, and the list of changed files is returned.

    Args:
        path: Path to the local git repository.
        pr_number: Pull request number.

    Returns:
        JSON with base/head project names, changed files, and commit info.
        Use the project names with search_code() or get_context() to search
        either side of the PR.
    """
    if not path or not path.strip():
        return json.dumps({"error": "path is required"})
    if pr_number < 1:
        return json.dumps({"error": "pr_number must be a positive integer"})

    root = Path(path).resolve()
    if not root.is_dir():
        return json.dumps({"error": f"Not a directory: {path}"})

    indexer = _get_indexer()

    lock_key = f"pr:{root}:{pr_number}"
    lock = _project_locks.setdefault(lock_key, threading.Lock())
    if not lock.acquire(timeout=60):
        return json.dumps({"error": "Another PR indexing operation is in progress"})

    try:
        result = indexer.index_pr(root, pr_number)
    finally:
        lock.release()

    return json.dumps(result, indent=2)
