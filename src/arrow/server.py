"""Arrow MCP Server — intelligent code indexing and retrieval for Claude Code."""

from __future__ import annotations

import json
import logging
import os
import re
import subprocess
import time
import threading
import uuid
from pathlib import Path

from mcp.server.fastmcp import FastMCP

from .embedder import Embedder, get_embedder
from .git_utils import get_diff_hunks, is_git_repo
from .indexer import Indexer
from .search import HybridSearcher
from .storage import Storage
from .vector_store import VectorStore
from .watcher import FileWatcher

logger = logging.getLogger(__name__)

DEFAULT_DB_DIR = Path.home() / ".arrow"
DEFAULT_DB_PATH = DEFAULT_DB_DIR / "index.db"
DEFAULT_VECTOR_PATH = DEFAULT_DB_DIR / "vectors.usearch"
DEFAULT_CLONE_DIR = DEFAULT_DB_DIR / "clones"

mcp = FastMCP(
    "arrow",
    instructions="Local code indexing and intelligent retrieval for Claude Code. "
    "Supports multiple projects, git-aware indexing, and GitHub remote content caching.",
)

# Global state (shared across all projects)
_storage: Storage | None = None
_indexer: Indexer | None = None
_vector_store: VectorStore | None = None
_embedder: Embedder | None = None
_searcher: HybridSearcher | None = None

# Per-project state
_watchers: dict[int, FileWatcher] = {}
_project_locks: dict[int, threading.Lock] = {}

# Extensions for non-code files that won't "break" from code changes
_NON_CODE_EXTS = {".md", ".json", ".yaml", ".yml", ".toml", ".csv", ".xml",
                  ".txt", ".rst", ".html", ".css", ".svg", ".lock"}


def _get_storage() -> Storage:
    global _storage
    if _storage is None:
        db_path = os.environ.get("ARROW_DB_PATH", str(DEFAULT_DB_PATH))
        _storage = Storage(db_path)
    return _storage


def _get_vector_store() -> VectorStore:
    global _vector_store
    if _vector_store is None:
        vec_path = os.environ.get("ARROW_VECTOR_PATH", str(DEFAULT_VECTOR_PATH))
        _vector_store = VectorStore(vec_path)
    return _vector_store


def _get_embedder() -> Embedder:
    global _embedder
    if _embedder is None:
        _embedder = get_embedder()
    return _embedder


def _get_indexer() -> Indexer:
    global _indexer
    if _indexer is None:
        _indexer = Indexer(
            _get_storage(),
            vector_store=_get_vector_store(),
            embedder=_get_embedder(),
        )
    return _indexer


def _get_searcher() -> HybridSearcher:
    global _searcher
    if _searcher is None:
        _searcher = HybridSearcher(
            _get_storage(),
            vector_store=_get_vector_store(),
            embedder=_get_embedder(),
        )
    return _searcher


_project_locks_guard = threading.Lock()


def _get_project_lock(project_id: int) -> threading.Lock:
    """Get or create a per-project lock for write serialization."""
    with _project_locks_guard:
        if project_id not in _project_locks:
            _project_locks[project_id] = threading.Lock()
        return _project_locks[project_id]


def _start_watcher(project_id: int, root: str) -> None:
    """Start file watcher for a specific project."""
    if project_id in _watchers:
        _watchers[project_id].stop()

    def on_change():
        lock = _get_project_lock(project_id)
        if not lock.acquire(blocking=False):
            logger.debug("Skipping re-index for project %d, already running", project_id)
            return
        try:
            # Create dedicated storage/indexer for this thread
            # (SQLite connections can't cross threads)
            from .storage import Storage as _S

            db_path = os.environ.get("ARROW_DB_PATH", str(DEFAULT_DB_PATH))
            vec_path = os.environ.get("ARROW_VECTOR_PATH", str(DEFAULT_VECTOR_PATH))
            thread_storage = _S(db_path)
            thread_vs = VectorStore(vec_path)
            thread_emb = get_embedder()
            thread_indexer = Indexer(
                thread_storage, vector_store=thread_vs, embedder=thread_emb,
            )
            thread_indexer.index_codebase(root)
            thread_storage.close()
            logger.info("Background re-index complete for %s", root)
        except Exception:
            logger.exception("Background re-index failed for %s", root)
        finally:
            lock.release()

    watcher = FileWatcher(root, on_change)
    watcher.project_id = project_id
    watcher.start()
    _watchers[project_id] = watcher


def _stop_watcher(project_id: int) -> None:
    """Stop watcher for a specific project."""
    if project_id in _watchers:
        _watchers[project_id].stop()
        del _watchers[project_id]


def _start_all_watchers() -> None:
    """Start watchers for all local projects."""
    storage = _get_storage()
    for project in storage.list_projects():
        if project.root_path and not project.is_remote:
            if project.id not in _watchers:
                root = project.root_path
                if Path(root).is_dir():
                    _start_watcher(project.id, root)


_PROJECT_NOT_FOUND = -1  # Sentinel for project name given but not found


def _resolve_project_id(project: str | None) -> int | None:
    """Resolve optional project name to project_id.

    Returns None if project is None (search all projects).
    Returns the project ID if found.
    Returns _PROJECT_NOT_FOUND (-1) if the project name was given but not
    found, so callers don't silently fall back to all-projects search.
    """
    if project is None:
        return None
    storage = _get_storage()
    proj = storage.get_project_by_name(project)
    if proj is None:
        return _PROJECT_NOT_FOUND
    return proj.id


def _check_project_id(project_id: int | None, project: str) -> str | None:
    """Return a JSON error string if project_id is the not-found sentinel."""
    if project_id == _PROJECT_NOT_FOUND:
        storage = _get_storage()
        available = [p.name for p in storage.list_projects()]
        return json.dumps({
            "error": f"Project not found: {project}",
            "available_projects": available,
        })
    return None


def _ensure_indexed() -> str | None:
    """Auto-index cwd if no projects are indexed. Returns error JSON or None.

    When called and no projects exist, attempts to index the current
    working directory (if it's a git repo) synchronously so the caller
    can proceed. Returns an error string only if indexing is not possible.
    """
    storage = _get_storage()
    if storage.list_projects():
        return None  # Already have indexed projects

    cwd = Path.cwd()
    if not cwd.is_dir():
        return json.dumps({
            "error": "No projects indexed yet. Run index_codebase(path) first."
        })

    # Walk up to git root
    try:
        result = subprocess.run(
            ["git", "-C", str(cwd), "rev-parse", "--show-toplevel"],
            capture_output=True, text=True, check=True, timeout=5,
        )
        cwd = Path(result.stdout.strip())
    except Exception:
        pass  # Use cwd as-is

    try:
        indexer = _get_indexer()
        indexer.index_codebase(cwd)
        logger.info("Auto-indexed %s on first tool call", cwd)
        return None
    except Exception:
        logger.exception("Auto-index failed for %s", cwd)
        return json.dumps({
            "error": "No projects indexed yet. Run index_codebase(path) first."
        })


def _record_chunk_sent(
    storage, chunk_info: dict, project_id: int | None,
) -> None:
    """Record a sent chunk in the session, looking up its chunk_id."""
    file_rec = storage.get_file(
        chunk_info["file"], project_id=project_id
    )
    if not file_rec:
        return
    # Find matching chunk by file + name + lines
    chunks = storage.get_chunks_for_file(file_rec.id)
    lines = chunk_info.get("lines", "")
    tokens = chunk_info.get("tokens", 0)
    for ch in chunks:
        ch_lines = f"{ch.start_line}-{ch.end_line}"
        if ch.name == chunk_info.get("name") and ch_lines == lines:
            storage.record_sent_chunk(
                _session_id, ch.id, tokens=tokens
            )
            return


# ─── MCP Tools ──────────────────────────────────────────────────────────


@mcp.tool()
def index_codebase(path: str, force: bool = False) -> str:
    """Index or re-index a codebase. Auto-detects git org/repo, branch, and commit.
    Incremental by default — only changed files are re-indexed.
    Supports multiple projects in parallel.

    Args:
        path: Absolute path to the codebase root directory.
        force: If True, re-index all files regardless of whether they changed.

    Returns:
        JSON status with file/chunk counts, project info, git metadata, and timing.
    """
    if not path or not path.strip():
        return json.dumps({"error": "path is required"})
    root = Path(path).resolve()
    if not root.is_dir():
        return json.dumps({"error": f"Not a directory: {path}"})

    indexer = _get_indexer()

    # Acquire project lock for concurrent safety
    # We need to resolve project first to get the lock
    storage = _get_storage()
    existing = storage.get_project_by_root(str(root))
    if existing:
        lock = _get_project_lock(existing.id)
        lock.acquire()
        try:
            result = indexer.index_codebase(root, force=force)
        finally:
            lock.release()
    else:
        result = indexer.index_codebase(root, force=force)
        # Lock for future concurrent access
        if "project_id" in result:
            _get_project_lock(result["project_id"])

    # Start file watcher for this project
    if "project_id" in result:
        _start_watcher(result["project_id"], str(root))

    return json.dumps(result, indent=2)


@mcp.tool()
def list_projects() -> str:
    """List all indexed projects with git info, file counts, and status.

    Returns:
        JSON array of projects with name, root_path, git branch/commit,
        file counts, and last indexed time.
    """
    storage = _get_storage()
    projects = storage.list_projects()

    output = []
    for p in projects:
        stats = storage.get_stats(project_id=p.id)
        output.append({
            "name": p.name,
            "root_path": p.root_path,
            "remote_url": p.remote_url,
            "git_branch": p.git_branch,
            "git_commit": p.git_commit[:8] if p.git_commit else None,
            "is_remote": p.is_remote,
            "files": stats["files"],
            "chunks": stats["chunks"],
            "symbols": stats["symbols"],
            "languages": stats["languages"],
            "last_indexed": p.last_indexed,
            "index_duration": p.index_duration,
            "watching": p.id in _watchers,
        })

    return json.dumps(output, indent=2)


@mcp.tool()
def project_summary(project: str | None = None) -> str:
    """Get a compressed project overview: language distribution, file structure,
    entry points, and key stats.

    Args:
        project: Project name (e.g. "org/repo"). Omit for all-projects summary.

    Returns:
        JSON summary of the project(s).
    """
    indexer = _get_indexer()

    err = _ensure_indexed()
    if err:
        return err

    project_id = _resolve_project_id(project)
    err = _check_project_id(project_id, project) if project else None
    if err:
        return err

    summary = indexer.generate_project_summary(project_id=project_id)
    return json.dumps(summary, indent=2)


@mcp.tool()
def search_code(query: str, limit: int = 10, project: str | None = None) -> str:
    """Hybrid search the indexed codebase using BM25 + semantic vector search.

    Args:
        query: Search query (keywords, function names, natural language).
        limit: Maximum number of results to return (default 10).
        project: Optional project name to scope search (e.g. "org/repo").
                 Omit to search across all projects.

    Returns:
        JSON array of matching code chunks with file path, project, and content.
    """
    if not query or not query.strip():
        return json.dumps({"error": "query is required"})
    if limit <= 0:
        return json.dumps({"error": "limit must be a positive integer"})
    limit = min(limit, 100)  # Cap at 100

    err = _ensure_indexed()
    if err:
        return err

    project_id = _resolve_project_id(project)
    err = _check_project_id(project_id, project) if project else None
    if err:
        return err

    searcher = _get_searcher()
    results = searcher.search(query, limit=limit, project_id=project_id)

    output = []
    for r in results:
        output.append({
            "file": r.file_path,
            "project": r.project_name,
            "name": r.chunk.name if r.chunk else "",
            "kind": r.chunk.kind if r.chunk else "",
            "lines": (
                f"{r.chunk.start_line}-{r.chunk.end_line}" if r.chunk else ""
            ),
            "score": round(r.score, 4),
            "content": r.content,
            "tokens": r.chunk.token_count if r.chunk else 0,
        })

    return json.dumps(output, indent=2)


@mcp.tool()
def get_context(
    query: str, token_budget: int = 0, project: str | None = None
) -> str:
    """Get the most relevant code for a query, compressed to fit a token budget.

    This is the primary tool. It runs hybrid search, ranks results, and
    returns the most relevant code fitting within the specified token budget.

    Args:
        query: What you're looking for (natural language or keywords).
        token_budget: Maximum tokens to return. Set to 0 (default) for
                      automatic budget based on query complexity. Simple
                      lookups get ~500 tokens, broad questions get ~8000+.
        project: Optional project name to scope search. Omit for all projects.

    Returns:
        JSON with the most relevant code chunks within the token budget.
    """
    if not query or not query.strip():
        return json.dumps({"error": "query is required"})
    if token_budget < 0:
        return json.dumps({"error": "token_budget must be >= 0 (0 = auto)"})
    storage = _get_storage()
    err = _ensure_indexed()
    if err:
        return err

    project_id = _resolve_project_id(project)
    err = _check_project_id(project_id, project) if project else None
    if err:
        return err

    searcher = _get_searcher()

    # Auto-estimate budget if not specified
    auto = token_budget <= 0
    if auto:
        token_budget = searcher.estimate_budget(
            query, project_id=project_id
        )

    # Conversation-aware: exclude already-sent chunks
    sent = storage.get_sent_chunk_ids(_session_id)
    session_tokens = storage.get_session_token_total(_session_id)

    t0 = time.time()
    context = searcher.get_context(
        query, token_budget=token_budget, project_id=project_id,
        exclude_chunk_ids=sent, frecency_boost=True,
    )
    latency = (time.time() - t0) * 1000

    # Track which chunks were sent in this session
    for chunk in context.get("chunks", []):
        # Record file access for frecency
        file_rec = storage.get_file(
            chunk["file"], project_id=project_id
        )
        if file_rec:
            storage.record_file_access(file_rec.id, project_id)
        # Record sent chunk with token count
        _record_chunk_sent(storage, chunk, project_id)

    # Record analytics
    storage.record_tool_call(
        "get_context", latency, project_id=project_id
    )

    context["budget_mode"] = "auto" if auto else "manual"
    context["session_chunks_excluded"] = len(sent)
    context["session_tokens_total"] = session_tokens

    # Add search hints when no results found to help the agent pivot
    if not context.get("chunks"):
        stats = storage.get_stats(project_id=project_id)
        context["suggestions"] = [
            "Try broader or alternative keywords",
            "Use search_structure() to find by function/class name",
            "Use file_summary() if you know the file path",
        ]
        context["indexed_stats"] = {
            "files": stats["files"],
            "chunks": stats["chunks"],
            "languages": list(stats["languages"].keys()),
        }

    return json.dumps(context, indent=2)


@mcp.tool()
def search_structure(
    symbol: str, kind: str = "any", project: str | None = None
) -> str:
    """Find functions, classes, or variables by name via the AST structure index.

    Args:
        symbol: Name to search for (supports prefix matching).
        kind: Filter by kind: "function", "class", "method", "any" (default).
        project: Optional project name to scope search.

    Returns:
        JSON array of matching symbol definitions.
    """
    _VALID_KINDS = {"function", "class", "method", "any"}
    storage = _get_storage()
    if not symbol or not symbol.strip():
        return json.dumps({"error": "symbol is required"})

    if kind not in _VALID_KINDS:
        return json.dumps({
            "error": f"Invalid kind: {kind!r}. Must be one of: {', '.join(sorted(_VALID_KINDS))}",
        })

    err = _ensure_indexed()
    if err:
        return err

    project_id = _resolve_project_id(project)
    symbols = storage.search_symbols(
        symbol.strip(), kind=kind if kind != "any" else None, project_id=project_id
    )

    output = []
    for sym in symbols:
        chunk = storage.get_chunk_by_id(sym.chunk_id)
        if chunk:
            file_rec = storage.get_file_by_id(chunk.file_id)
            proj = storage.get_project(chunk.project_id) if chunk.project_id else None
            output.append({
                "name": sym.name,
                "kind": sym.kind,
                "file": file_rec.path if file_rec else "",
                "project": proj.name if proj else "",
                "lines": f"{chunk.start_line}-{chunk.end_line}",
            })

    return json.dumps(output, indent=2)


@mcp.tool()
def trace_dependencies(
    file: str, depth: int = 2, project: str | None = None
) -> str:
    """Trace import dependencies for a file.

    Args:
        file: Relative path to the file.
        depth: How many levels deep to trace (default 2).
        project: Optional project name to scope the file lookup.

    Returns:
        JSON dependency graph with imports and importers.
    """
    if not file or not file.strip():
        return json.dumps({"error": "file path is required"})
    storage = _get_storage()
    project_id = _resolve_project_id(project)
    file_rec = storage.get_file(file, project_id=project_id)

    if not file_rec:
        return json.dumps({"error": f"File not indexed: {file}"})

    effective_pid = file_rec.project_id
    if depth < 1:
        return json.dumps({"error": "depth must be >= 1"})
    depth = min(depth, 5)  # Cap at 5

    def _get_imports_for(fid):
        rows = storage.conn.execute(
            "SELECT symbol FROM imports WHERE source_file = ?",
            (fid,),
        ).fetchall()
        return [r[0] for r in rows if r[0]]

    def _get_importers_of(fpath, pid):
        stem = Path(fpath).stem
        if pid is not None:
            rows = storage.conn.execute(
                """SELECT DISTINCT f.path FROM imports i
                   JOIN files f ON f.id = i.source_file
                   WHERE i.symbol LIKE ? AND f.project_id = ?""",
                (f"%{stem}%", pid),
            ).fetchall()
        else:
            rows = storage.conn.execute(
                """SELECT DISTINCT f.path FROM imports i
                   JOIN files f ON f.id = i.source_file
                   WHERE i.symbol LIKE ?""",
                (f"%{stem}%",),
            ).fetchall()
        return [r[0] for r in rows if r[0]]

    # Level-1 results
    imports = _get_imports_for(file_rec.id)
    imported_by = _get_importers_of(file, effective_pid)

    # Recurse for deeper levels
    deeper_importers = {}
    if depth > 1:
        seen = {file}
        frontier = list(set(imported_by))
        for _lvl in range(depth - 1):
            next_frontier = []
            for imp_path in frontier:
                if imp_path in seen:
                    continue
                seen.add(imp_path)
                imp_rec = storage.get_file(imp_path, project_id=effective_pid)
                if imp_rec:
                    trans = _get_importers_of(imp_path, effective_pid)
                    trans = [p for p in trans if p not in seen]
                    if trans:
                        deeper_importers[imp_path] = trans
                        next_frontier.extend(trans)
            frontier = list(set(next_frontier))
            if not frontier:
                break

    result = {
        "file": file,
        "language": file_rec.language,
        "imports": imports,
        "imported_by": imported_by,
        "depth": depth,
    }
    if deeper_importers:
        result["transitive_importers"] = deeper_importers

    return json.dumps(result, indent=2)


@mcp.tool()
def file_summary(path: str, project: str | None = None) -> str:
    """Get a summary of a specific indexed file.

    Args:
        path: Relative path to the file.
        project: Optional project name to scope the file lookup.

    Returns:
        JSON summary with functions, classes, imports, and token counts.
    """
    if not path or not path.strip():
        return json.dumps({"error": "path is required"})

    storage = _get_storage()
    project_id = _resolve_project_id(project)
    file_rec = storage.get_file(path, project_id=project_id)

    if not file_rec:
        return json.dumps({"error": f"File not indexed: {path}"})

    chunks = storage.get_chunks_for_file(file_rec.id)

    functions = []
    classes = []
    other = []
    total_tokens = 0

    for chunk in chunks:
        total_tokens += chunk.token_count or 0
        entry = {
            "name": chunk.name,
            "lines": f"{chunk.start_line}-{chunk.end_line}",
            "tokens": chunk.token_count or 0,
        }
        if chunk.kind in ("function", "method"):
            functions.append(entry)
        elif chunk.kind in ("class", "interface", "enum"):
            classes.append(entry)
        else:
            other.append(entry)

    imports = storage.conn.execute(
        "SELECT symbol FROM imports WHERE source_file = ?",
        (file_rec.id,),
    ).fetchall()

    return json.dumps({
        "path": path,
        "language": file_rec.language,
        "total_tokens": total_tokens,
        "total_chunks": len(chunks),
        "functions": functions,
        "classes": classes,
        "other": other,
        "imports": [row[0] for row in imports if row[0]],
    }, indent=2)


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
        # Update existing clone
        try:
            subprocess.run(
                ["git", "-C", str(clone_dir), "fetch", "origin", branch,
                 "--depth=1"],
                capture_output=True, text=True, timeout=60,
            )
            subprocess.run(
                ["git", "-C", str(clone_dir), "checkout",
                 f"origin/{branch}", "--force"],
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


@mcp.tool()
def get_diff_context(
    file: str, line_start: int = 0, line_end: int = 0,
    project: str | None = None,
) -> str:
    """Get changed code plus all callers and dependents of modified functions.

    When reviewing changes, this returns the diff hunks AND the code that
    calls or depends on the changed functions — so you see the full impact
    without reading random files.

    Args:
        file: Relative path to the changed file.
        line_start: Start of line range to focus on (0 = auto-detect from git diff).
        line_end: End of line range (0 = auto-detect from git diff).
        project: Optional project name to scope lookup.

    Returns:
        JSON with changed functions, their callers, dependent files, and code.
    """
    if not file or not file.strip():
        return json.dumps({"error": "file path is required"})
    if line_start < 0 or line_end < 0:
        return json.dumps({"error": "line_start and line_end must be >= 0"})
    if line_start and line_end and line_start > line_end:
        return json.dumps({
            "error": f"line_start ({line_start}) must be <= line_end ({line_end})"
        })
    storage = _get_storage()
    project_id = _resolve_project_id(project)

    file_rec = storage.get_file(file, project_id=project_id)
    if not file_rec:
        return json.dumps({"error": f"File not indexed: {file}"})

    # Get the project's root path for git operations
    proj = storage.get_project(file_rec.project_id) if file_rec.project_id else None
    root = Path(proj.root_path) if proj and proj.root_path else None

    # Find which functions were changed
    chunks = storage.get_chunks_for_file(file_rec.id)
    changed_functions = []

    if root and root.is_dir():
        hunks = get_diff_hunks(root, file)
        if hunks and not line_start:
            # Auto-detect changed line ranges from git diff
            for hunk in hunks:
                hunk_start = hunk["start"]
                hunk_end = hunk_start + hunk["count"]
                for chunk in chunks:
                    if (chunk.start_line <= hunk_end and
                            chunk.end_line >= hunk_start and
                            chunk.kind in ("function", "method", "class")):
                        if chunk.name not in [c["name"] for c in changed_functions]:
                            changed_functions.append({
                                "name": chunk.name,
                                "kind": chunk.kind,
                                "lines": f"{chunk.start_line}-{chunk.end_line}",
                                "content": chunk.content_text or "",
                            })

    if line_start and line_end:
        for chunk in chunks:
            if (chunk.start_line <= line_end and
                    chunk.end_line >= line_start and
                    chunk.kind in ("function", "method", "class")):
                if chunk.name not in [c["name"] for c in changed_functions]:
                    changed_functions.append({
                        "name": chunk.name,
                        "kind": chunk.kind,
                        "lines": f"{chunk.start_line}-{chunk.end_line}",
                        "content": chunk.content_text or "",
                    })

    # Find callers/dependents for each changed function
    callers = []
    seen_callers = set()
    for func in changed_functions:
        func_callers = storage.get_callers_of_symbol(
            func["name"], project_id=file_rec.project_id
        )
        for caller in func_callers:
            # Skip non-code files (docs, data files)
            ext = Path(caller["file_path"]).suffix.lower()
            if ext in _NON_CODE_EXTS:
                continue
            caller_key = (caller["file_path"], caller["name"])
            if caller_key not in seen_callers:
                seen_callers.add(caller_key)
                callers.append({
                    "file": caller["file_path"],
                    "name": caller["name"],
                    "kind": caller["kind"],
                    "lines": f"{caller['start_line']}-{caller['end_line']}",
                    "calls": func["name"],
                })

    # Find files that import this file
    importers = storage.get_importers_of_file(
        file, project_id=file_rec.project_id
    )

    return json.dumps({
        "file": file,
        "changed_functions": changed_functions,
        "callers": callers[:30],
        "dependent_files": [
            {"path": imp["path"], "language": imp.get("language")}
            for imp in importers
        ],
        "total_callers": len(callers),
        "total_dependents": len(importers),
    }, indent=2)


@mcp.tool()
def what_breaks_if_i_change(
    file: str, function: str | None = None, project: str | None = None
) -> str:
    """Trace reverse dependencies to show what breaks if you change a file or function.

    Returns all callers, test files that exercise the function, config files
    that reference it, and dependent files across the full index.

    Args:
        file: Relative path to the file you plan to change.
        function: Optional specific function name. If omitted, analyzes all
                  exported symbols in the file.
        project: Optional project name to scope lookup.

    Returns:
        JSON impact report with callers, tests, dependents, and risk assessment.
    """
    if not file or not file.strip():
        return json.dumps({"error": "file path is required"})
    storage = _get_storage()
    project_id = _resolve_project_id(project)

    file_rec = storage.get_file(file, project_id=project_id)
    if not file_rec:
        return json.dumps({"error": f"File not indexed: {file}"})

    effective_pid = file_rec.project_id

    # Get symbols to analyze
    if function:
        target_symbols = [function]
    else:
        chunks = storage.get_chunks_for_file(file_rec.id)
        target_symbols = [
            c.name for c in chunks
            if c.kind in ("function", "method", "class")
            and c.name and c.name != "<anonymous>"
            # Skip dunder methods — __init__, __str__, etc. generate
            # massive noise since every class has them
            and not (c.name.startswith("__") and c.name.endswith("__"))
        ]

    # Find all callers for each symbol
    all_callers = []
    seen = set()
    for sym in target_symbols:
        callers = storage.get_callers_of_symbol(sym, project_id=effective_pid)
        for caller in callers:
            # Skip non-code files (docs, data) — they reference the symbol
            # textually but won't break from a code change
            ext = Path(caller["file_path"]).suffix.lower()
            if ext in _NON_CODE_EXTS:
                continue
            key = (caller["file_path"], caller["name"])
            if key not in seen:
                seen.add(key)
                all_callers.append({
                    "file": caller["file_path"],
                    "name": caller["name"],
                    "kind": caller["kind"],
                    "calls": sym,
                })

    # Find test files that reference any of the target symbols
    test_files = storage.get_test_files(project_id=effective_pid)
    test_file_ids = [tf.id for tf in test_files]

    affected_tests = []
    seen_tests = set()
    for sym in target_symbols:
        test_refs = storage.find_chunks_referencing(sym, test_file_ids)
        for ref in test_refs:
            test_key = (ref["file_path"], ref["name"])
            if test_key not in seen_tests:
                seen_tests.add(test_key)
                affected_tests.append({
                    "file": ref["file_path"],
                    "test_name": ref["name"],
                    "references": sym,
                })

    # Find files that import this module
    importers = storage.get_importers_of_file(file, project_id=effective_pid)

    # Risk assessment
    caller_count = len(all_callers)
    test_count = len(affected_tests)
    importer_count = len(importers)

    if caller_count > 20 or importer_count > 10:
        risk = "high"
    elif caller_count > 5 or importer_count > 3:
        risk = "medium"
    else:
        risk = "low"

    return json.dumps({
        "file": file,
        "symbols_analyzed": target_symbols,
        "risk": risk,
        "callers": all_callers[:50],
        "affected_tests": affected_tests[:30],
        "dependent_files": [
            {"path": imp["path"]} for imp in importers
        ],
        "summary": {
            "total_callers": caller_count,
            "total_tests": test_count,
            "total_dependents": importer_count,
        },
    }, indent=2)


@mcp.tool()
def resolve_symbol(
    symbol: str, project: str | None = None
) -> str:
    """Resolve a symbol across all indexed repos (cross-repo import resolution).

    When you see `from shared_lib import auth`, this tool finds which indexed
    repo contains `shared_lib.auth` and returns its definition. Works across
    all indexed projects.

    Args:
        symbol: The symbol name to resolve (e.g. "auth", "DatabaseClient").
        project: Optional source project name — results from other projects
                 are prioritized.

    Returns:
        JSON with all matching definitions across repos, with code.
    """
    storage = _get_storage()

    if not symbol or not symbol.strip():
        return json.dumps({"error": "symbol is required"})

    source_pid = _resolve_project_id(project)
    # If project was given but not found, treat as no-project filter
    if source_pid == _PROJECT_NOT_FOUND:
        source_pid = None

    # Search across all repos (exact match first)
    results = storage.resolve_symbol_across_repos(
        symbol, exclude_project_id=source_pid
    )

    # Also search within source project for completeness
    local_results = storage.resolve_symbol_across_repos(symbol)

    # Fallback to prefix match if exact match found nothing
    if not results and not local_results:
        prefix_results = storage.search_symbols(symbol, limit=20)
        for sym_rec in prefix_results:
            file_rec = storage.get_file_by_id(sym_rec.file_id)
            if not file_rec:
                continue
            proj = storage.get_project(
                file_rec.project_id
            ) if file_rec.project_id else None
            chunk = storage.get_chunk_by_id(
                sym_rec.chunk_id
            ) if sym_rec.chunk_id else None
            local_results.append({
                "name": sym_rec.name,
                "kind": sym_rec.kind,
                "path": file_rec.path,
                "project_id": file_rec.project_id,
                "project_name": proj.name if proj else "",
                "start_line": chunk.start_line if chunk else 0,
                "end_line": chunk.end_line if chunk else 0,
                "content_text": chunk.content_text if chunk else "",
            })

    # Deduplicate: cross-repo first, then local
    seen = set()
    output = []
    for result in results + local_results:
        key = (result["project_name"], result["path"], result["name"])
        if key not in seen:
            seen.add(key)
            content = result.get("content_text", "") or ""
            truncated = len(content) > 2000
            if truncated:
                content = content[:2000] + "\n... (truncated)"
            output.append({
                "symbol": result["name"],
                "kind": result["kind"],
                "file": result["path"],
                "project": result["project_name"],
                "lines": f"{result['start_line']}-{result['end_line']}",
                "content": content,
                "truncated": truncated,
                "cross_repo": result["project_id"] != source_pid if source_pid else False,
            })

    return json.dumps({
        "query": symbol,
        "source_project": project,
        "results": output[:20],
        "total": len(output),
    }, indent=2)


@mcp.tool()
def get_tests_for(
    function: str, file: str | None = None, project: str | None = None
) -> str:
    """Find test code for a specific function via import tracing + naming conventions.

    Maps a function to its test files by:
    1. Finding test files that import the source module
    2. Finding test functions whose names match (test_<function>)
    3. Finding test chunks that reference the function name

    Args:
        function: The function name to find tests for.
        file: Optional source file path (narrows the search).
        project: Optional project name.

    Returns:
        JSON with matching test functions and their code.
    """
    if not function or not function.strip():
        return json.dumps({"error": "function name is required"})

    storage = _get_storage()
    project_id = _resolve_project_id(project)

    # Get all test files
    test_files = storage.get_test_files(project_id=project_id)
    if not test_files:
        return json.dumps({
            "function": function,
            "tests": [],
            "message": "No test files found in the index.",
        })

    # Strategy 1: Find test functions named test_<function> or test<Function>
    camel_name = function[0].upper() + function[1:] if function else ""
    matching_tests = []
    seen = set()

    name_patterns = [
        f"test_{function}",
        f"Test{camel_name}",
        f"test{camel_name}",
    ]

    for tf in test_files:
        chunks = storage.get_chunks_for_file(tf.id)
        for chunk in chunks:
            # Match by naming convention
            name_match = any(
                chunk.name and chunk.name.startswith(pat)
                for pat in name_patterns
            )
            # Match by content reference (word-boundary to avoid
            # false positives for short names like "get", "set")
            content_match = False
            if chunk.content_text and not name_match:
                content_match = bool(
                    re.search(rf'\b{re.escape(function)}\b',
                              chunk.content_text)
                )
            if name_match or content_match:
                key = (tf.path, chunk.name)
                if key not in seen:
                    seen.add(key)
                    matching_tests.append({
                        "file": tf.path,
                        "test_name": chunk.name,
                        "kind": chunk.kind,
                        "lines": f"{chunk.start_line}-{chunk.end_line}",
                        "content": chunk.content_text or "",
                        "match_type": "name" if name_match else "reference",
                    })

    # Strategy 2: If source file given, find tests that import it
    import_tests = []
    if file:
        stem = Path(file).stem
        for tf in test_files:
            # Check if this test file imports the source module
            imports = storage.conn.execute(
                "SELECT symbol FROM imports WHERE source_file = ?",
                (tf.id,),
            ).fetchall()
            if any(stem in (imp[0] or "") for imp in imports):
                # This test file imports the source — get relevant chunks
                chunks = storage.get_chunks_for_file(tf.id)
                for chunk in chunks:
                    if chunk.content_text and re.search(
                        rf'\b{re.escape(function)}\b',
                        chunk.content_text
                    ):
                        key = (tf.path, chunk.name)
                        if key not in seen:
                            seen.add(key)
                            import_tests.append({
                                "file": tf.path,
                                "test_name": chunk.name,
                                "kind": chunk.kind,
                                "lines": f"{chunk.start_line}-{chunk.end_line}",
                                "content": chunk.content_text or "",
                                "match_type": "import",
                            })

    all_tests = matching_tests + import_tests

    return json.dumps({
        "function": function,
        "source_file": file,
        "tests": all_tests[:30],
        "total": len(all_tests),
    }, indent=2)


@mcp.tool()
def detect_stale_index(project: str | None = None) -> str:
    """Check if the index is stale compared to the working tree.

    Compares indexed file hashes against current disk state to find
    files that have changed since last indexing.

    Args:
        project: Project name. Omit to check all local projects.

    Returns:
        JSON with stale files, drift percentage, and recommendation.
    """
    storage = _get_storage()
    from .hasher import hash_file

    projects = storage.list_projects()
    if project:
        proj = storage.get_project_by_name(project)
        if not proj:
            return json.dumps({"error": f"Project not found: {project}"})
        projects = [proj]

    results = []
    for proj in projects:
        if not proj.root_path or proj.is_remote:
            continue
        root = Path(proj.root_path)
        if not root.is_dir():
            continue

        indexed_files = storage.get_all_files(project_id=proj.id)
        stale = []
        missing = []
        for f in indexed_files:
            full = root / f.path
            if not full.exists():
                missing.append(f.path)
                continue
            try:
                current_hash = hash_file(str(full))
                if current_hash != f.content_hash:
                    stale.append(f.path)
            except OSError:
                continue

        total = len(indexed_files)
        drift = len(stale) + len(missing)
        pct = round(drift / total * 100, 1) if total else 0

        results.append({
            "project": proj.name,
            "total_files": total,
            "stale_files": stale[:20],
            "missing_files": missing[:10],
            "drift_count": drift,
            "drift_pct": pct,
            "last_indexed": proj.last_indexed,
            "recommendation": (
                "re-index recommended" if pct > 10
                else "index is fresh" if pct == 0
                else "minor drift"
            ),
        })

    return json.dumps(results, indent=2)


@mcp.tool()
def find_dead_code(project: str | None = None) -> str:
    """Find functions and methods with zero callers in the index.

    Scans all symbols and checks if any other code references them.
    Skips private functions, test helpers, and entry points.

    Args:
        project: Optional project name. Omit for all projects.

    Returns:
        JSON list of unreferenced functions with file and line info.
    """
    storage = _get_storage()
    project_id = _resolve_project_id(project)
    dead = storage.find_dead_code(project_id=project_id)
    return json.dumps({
        "dead_code": dead[:100],
        "total": len(dead),
    }, indent=2)


@mcp.tool()
def export_index(project: str) -> str:
    """Export a project's index as a portable JSON bundle.

    The export includes all files, chunks, symbols, and imports.
    Can be imported on another machine to skip re-indexing.

    Args:
        project: Project name to export (e.g. "org/repo").

    Returns:
        JSON bundle with all index data for the project.
    """
    if not project or not project.strip():
        return json.dumps({"error": "project name is required"})

    storage = _get_storage()
    proj = storage.get_project_by_name(project)
    if not proj:
        return json.dumps({"error": f"Project not found: {project}"})

    files = storage.get_all_files(project_id=proj.id)
    all_chunks = []
    all_symbols = []
    all_imports = []

    for f in files:
        chunks = storage.get_chunks_for_file(f.id)
        for c in chunks:
            all_chunks.append({
                "file_path": f.path,
                "name": c.name,
                "kind": c.kind,
                "start_line": c.start_line,
                "end_line": c.end_line,
                "content_text": c.content_text or "",
                "scope_context": c.scope_context,
                "token_count": c.token_count,
            })

        # Symbols for this file
        syms = storage.conn.execute(
            "SELECT name, kind FROM symbols WHERE file_id = ?",
            (f.id,),
        ).fetchall()
        for s in syms:
            all_symbols.append({
                "file_path": f.path,
                "name": s["name"],
                "kind": s["kind"],
            })

        # Imports for this file
        imps = storage.conn.execute(
            "SELECT symbol FROM imports WHERE source_file = ?",
            (f.id,),
        ).fetchall()
        for imp in imps:
            all_imports.append({
                "file_path": f.path,
                "symbol": imp["symbol"],
            })

    bundle = {
        "version": 1,
        "project": {
            "name": proj.name,
            "remote_url": proj.remote_url,
            "git_branch": proj.git_branch,
            "git_commit": proj.git_commit,
        },
        "files": [
            {"path": f.path, "language": f.language,
             "content_hash": f.content_hash}
            for f in files
        ],
        "chunks": all_chunks,
        "symbols": all_symbols,
        "imports": all_imports,
        "stats": {
            "files": len(files),
            "chunks": len(all_chunks),
            "symbols": len(all_symbols),
            "imports": len(all_imports),
        },
    }

    return json.dumps(bundle)


@mcp.tool()
def import_index(bundle_json: str) -> str:
    """Import a project index from an exported JSON bundle.

    Recreates the project, files, chunks, symbols, and imports
    from a previously exported bundle. Skips re-indexing.

    Args:
        bundle_json: The JSON string from export_index.

    Returns:
        JSON status with counts.
    """
    try:
        bundle = json.loads(bundle_json)
    except json.JSONDecodeError:
        return json.dumps({"error": "Invalid JSON bundle"})

    if "project" not in bundle or "chunks" not in bundle:
        return json.dumps({"error": "Invalid bundle format"})

    storage = _get_storage()
    from .chunker import compress_content

    proj_data = bundle["project"]
    existing = storage.get_project_by_name(proj_data.get("name", ""))
    if existing:
        return json.dumps({
            "error": f"Project '{proj_data['name']}' already exists. "
                     "Remove it first with remove_project().",
        })
    project_id = storage.create_project(
        name=proj_data["name"],
        remote_url=proj_data.get("remote_url"),
        git_branch=proj_data.get("git_branch"),
        git_commit=proj_data.get("git_commit"),
    )

    # Create files
    file_id_map = {}
    for f in bundle.get("files", []):
        fid = storage.upsert_file(
            f["path"], f["content_hash"],
            f.get("language"), project_id=project_id,
        )
        file_id_map[f["path"]] = fid

    # Create chunks
    chunks_created = 0
    for c in bundle.get("chunks", []):
        fid = file_id_map.get(c["file_path"])
        if not fid:
            continue
        compressed = compress_content(c["content_text"])
        storage.insert_chunk(
            file_id=fid,
            name=c["name"],
            kind=c["kind"],
            start_line=c["start_line"],
            end_line=c["end_line"],
            content=compressed,
            content_text=c["content_text"],
            scope_context=c.get("scope_context", ""),
            token_count=c.get("token_count", 0),
            project_id=project_id,
        )
        chunks_created += 1

    # Create symbols
    symbols_created = 0
    for s in bundle.get("symbols", []):
        fid = file_id_map.get(s["file_path"])
        if not fid:
            continue
        file_chunks = storage.get_chunks_for_file(fid)
        if file_chunks:
            storage.insert_symbol(
                chunk_id=file_chunks[0].id,
                name=s["name"],
                kind=s["kind"],
                file_id=fid,
            )
            symbols_created += 1

    # Create imports
    imports_created = 0
    for imp in bundle.get("imports", []):
        fid = file_id_map.get(imp["file_path"])
        if fid:
            storage.conn.execute(
                "INSERT INTO imports (source_file, target_file, symbol)"
                " VALUES (?, NULL, ?)",
                (fid, imp["symbol"]),
            )
            imports_created += 1

    storage.commit()

    elapsed = "0s"
    storage.update_project_indexed(
        project_id, elapsed,
        json.dumps({}),
    )

    return json.dumps({
        "project_name": proj_data["name"],
        "project_id": project_id,
        "files": len(file_id_map),
        "chunks": chunks_created,
        "symbols": symbols_created,
        "imports": imports_created,
        "status": "imported",
    }, indent=2)


@mcp.tool()
def tool_analytics(hours: int = 24) -> str:
    """Get usage analytics for Arrow MCP tools.

    Shows call counts, average latency, and total tokens saved
    per tool over the specified time window.

    Args:
        hours: Look-back window in hours (default 24).

    Returns:
        JSON with per-tool stats and totals.
    """
    if hours < 1:
        return json.dumps({"error": "hours must be >= 1"})
    hours = min(hours, 8760)  # Cap at 1 year
    storage = _get_storage()
    since = time.time() - (hours * 3600)
    stats = storage.get_tool_analytics(since=since)

    total_calls = sum(s["calls"] for s in stats)
    total_saved = sum(s["total_tokens_saved"] or 0 for s in stats)

    return json.dumps({
        "window_hours": hours,
        "tools": stats,
        "total_calls": total_calls,
        "total_tokens_saved": total_saved,
    }, indent=2)


# Session ID for conversation-aware context tracking
_session_id: str = str(uuid.uuid4())


@mcp.tool()
def context_pressure() -> str:
    """Check current context window usage stats.

    Shows how many tokens have been sent this session and how
    many unique chunks. Useful for monitoring session activity.

    Returns:
        JSON with session token stats.
    """
    storage = _get_storage()
    session_tokens = storage.get_session_token_total(_session_id)
    sent_ids = storage.get_sent_chunk_ids(_session_id)

    return json.dumps({
        "session_id": _session_id,
        "session_tokens": session_tokens,
        "chunks_sent": len(sent_ids),
        "status": (
            "critical" if session_tokens > 230_000
            else "high" if session_tokens > 180_000
            else "moderate" if session_tokens > 100_000
            else "low"
        ),
    }, indent=2)


@mcp.tool()
def store_memory(
    key: str, content: str,
    category: str = "general",
    project: str | None = None,
) -> str:
    """Store a long-term memory that persists across sessions.

    Use this to save knowledge about the codebase, architectural
    decisions, conventions, or any context that should survive
    session resets. Memories are searchable by content.

    Args:
        key: Short identifier (e.g. "auth-pattern", "db-convention").
        content: The knowledge to remember.
        category: Group memories: "architecture", "convention",
                  "decision", "note", "general" (default).
        project: Optional project scope. Omit for global memories.

    Returns:
        JSON confirmation with memory ID.
    """
    _VALID_CATEGORIES = {"architecture", "convention", "decision", "note", "general"}
    if not key or not key.strip():
        return json.dumps({"error": "key is required"})
    if not content or not content.strip():
        return json.dumps({"error": "content is required"})
    if category not in _VALID_CATEGORIES:
        return json.dumps({
            "error": f"Invalid category: {category!r}. Must be one of: {', '.join(sorted(_VALID_CATEGORIES))}",
        })
    storage = _get_storage()
    project_id = _resolve_project_id(project)
    mem_id = storage.store_memory(
        key.strip(), content, category=category, project_id=project_id
    )
    return json.dumps({
        "stored": True,
        "id": mem_id,
        "key": key,
        "category": category,
        "project": project,
    })


@mcp.tool()
def recall_memory(
    query: str,
    category: str | None = None,
    project: str | None = None,
    limit: int = 10,
) -> str:
    """Recall stored memories by searching their content.

    Searches across all stored memories using full-text search.
    Returns the most relevant memories matching the query.

    Args:
        query: What to search for in memories.
        category: Optional filter by category.
        project: Optional project scope. Omit for all.
        limit: Max memories to return (default 10).

    Returns:
        JSON array of matching memories.
    """
    if not query or not query.strip():
        return json.dumps({"error": "query is required"})
    if limit < 1:
        return json.dumps({"error": "limit must be >= 1"})

    storage = _get_storage()
    project_id = _resolve_project_id(project)
    try:
        results = storage.recall_memory(
            query, category=category,
            project_id=project_id, limit=limit,
        )
    except Exception:
        logger.debug("recall_memory FTS error for query %r", query, exc_info=True)
        results = []

    return json.dumps({
        "query": query,
        "total": len(results),
        "memories": results,
    }, indent=2)


@mcp.tool()
def list_memories(
    category: str | None = None,
    project: str | None = None,
) -> str:
    """List all stored memories.

    Args:
        category: Optional filter by category.
        project: Optional project scope.

    Returns:
        JSON array of all memories.
    """
    storage = _get_storage()
    project_id = _resolve_project_id(project)
    results = storage.list_memories(
        category=category, project_id=project_id
    )
    return json.dumps({
        "total": len(results),
        "memories": results,
    }, indent=2)


@mcp.tool()
def delete_memory(
    memory_id: int | None = None,
    key: str | None = None,
    category: str | None = None,
    project: str | None = None,
) -> str:
    """Delete a stored memory by ID or by key.

    Args:
        memory_id: Delete by specific ID.
        key: Delete by key name.
        category: Required with key if ambiguous.
        project: Project scope for key-based deletion.

    Returns:
        JSON confirmation with count deleted.
    """
    if memory_id is None and key is None:
        return json.dumps({"error": "Provide memory_id or key to delete"})
    storage = _get_storage()
    project_id = _resolve_project_id(project)
    count = storage.delete_memory(
        memory_id=memory_id, key=key,
        category=category, project_id=project_id,
    )
    return json.dumps({
        "deleted": count,
        "memory_id": memory_id,
        "key": key,
    })


@mcp.tool()
def remove_project(project: str) -> str:
    """Remove a project and all its indexed data.

    Args:
        project: Project name (e.g. "org/repo").

    Returns:
        JSON confirmation.
    """
    if not project or not project.strip():
        return json.dumps({"error": "project name is required"})

    storage = _get_storage()
    proj = storage.get_project_by_name(project)
    if not proj:
        return json.dumps({"error": f"Project not found: {project}"})

    # Stop watcher if running
    _stop_watcher(proj.id)

    # Remove lock
    _project_locks.pop(proj.id, None)

    # Delete project (cascades to files, chunks, symbols, imports)
    storage.delete_project(proj.id)

    return json.dumps({
        "removed": project,
        "message": f"Project '{project}' and all its data have been removed."
    })


# ─── Entry points ──────────────────────────────────────────────────────


def _auto_warm_cwd() -> None:
    """Auto-index the current working directory in the background.

    Called on server startup so the first query doesn't pay the indexing cost.
    Skips if the directory is already indexed and up to date.
    """
    cwd = Path.cwd()
    if not cwd.is_dir() or not is_git_repo(cwd):
        return

    # Walk up to the git repo root so we index the full repo (including tests)
    try:
        result = subprocess.run(
            ["git", "-C", str(cwd), "rev-parse", "--show-toplevel"],
            capture_output=True, text=True, check=True, timeout=5,
        )
        cwd = Path(result.stdout.strip())
    except Exception:
        pass  # Fall back to cwd if we can't find the root

    storage = _get_storage()
    existing = storage.get_project_by_root(str(cwd))

    # If already indexed recently (within last 5 min), skip
    if existing and existing.last_indexed is not None:
        try:
            if time.time() - existing.last_indexed < 300:
                return
        except TypeError:
            pass  # last_indexed not a valid number

    def _warm():
        try:
            # Create dedicated storage/indexer for this thread
            # (SQLite connections can't cross threads)
            from .embedder import get_embedder as _ge
            from .storage import Storage as _S
            from .vector_store import VectorStore as _VS

            db_path = os.environ.get(
                "ARROW_DB_PATH", str(DEFAULT_DB_PATH)
            )
            vec_path = os.environ.get(
                "ARROW_VECTOR_PATH", str(DEFAULT_VECTOR_PATH)
            )
            thread_storage = _S(db_path)
            thread_vs = _VS(vec_path)
            thread_emb = _ge()
            thread_indexer = Indexer(
                thread_storage,
                vector_store=thread_vs,
                embedder=thread_emb,
            )
            result = thread_indexer.index_codebase(cwd)
            thread_storage.close()

            pid = result.get("project_id")
            if pid:
                _start_watcher(pid, str(cwd))
            logger.info(
                "Auto-warm complete: %s (%s files)",
                result.get("project_name", "?"),
                result.get("files_scanned", 0),
            )
        except Exception:
            logger.exception("Auto-warm failed for %s", cwd)

    thread = threading.Thread(target=_warm, daemon=True)
    thread.start()


def main():
    """Run the Arrow MCP server."""
    import argparse

    parser = argparse.ArgumentParser(description="Arrow MCP Server")
    parser.add_argument(
        "--transport",
        choices=["stdio", "http"],
        default="stdio",
        help="Transport protocol (default: stdio)",
    )
    parser.add_argument(
        "--port",
        type=int,
        default=8080,
        help="Port for HTTP transport (default: 8080)",
    )
    parser.add_argument(
        "--db-path",
        type=str,
        default=None,
        help=f"Database path (default: {DEFAULT_DB_PATH})",
    )
    parser.add_argument(
        "--log-level",
        choices=["DEBUG", "INFO", "WARNING", "ERROR"],
        default="INFO",
        help="Logging level (default: INFO)",
    )
    args = parser.parse_args()

    logging.basicConfig(
        level=getattr(logging, args.log_level),
        format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    )

    if args.db_path:
        os.environ["ARROW_DB_PATH"] = args.db_path

    # Start watchers for all existing local projects
    _start_all_watchers()

    # Auto-warm: index the working directory in the background if not indexed
    _auto_warm_cwd()

    if args.transport == "stdio":
        mcp.run(transport="stdio")
    else:
        mcp.run(transport="streamable-http", host="0.0.0.0", port=args.port)


if __name__ == "__main__":
    main()
