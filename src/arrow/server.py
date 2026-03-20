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

from .chunker import decompress_content
from .config import get_config
from .embedder import Embedder, get_embedder
from .git_utils import is_git_repo
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

# Session ID for conversation-aware context tracking
_session_id: str = str(uuid.uuid4())

_PROJECT_NOT_FOUND = -1  # Sentinel for project name given but not found


def _get_storage() -> Storage:
    global _storage
    if _storage is None:
        cfg = get_config()
        db_path = os.environ.get(
            "ARROW_DB_PATH", cfg.db_path or str(DEFAULT_DB_PATH)
        )
        _storage = Storage(db_path)
    return _storage


def _get_vector_store() -> VectorStore:
    global _vector_store
    if _vector_store is None:
        cfg = get_config()
        vec_path = os.environ.get(
            "ARROW_VECTOR_PATH", cfg.vector_path or str(DEFAULT_VECTOR_PATH)
        )
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


def _detect_project_from_cwd() -> int | None:
    """Auto-detect the current project from cwd.

    Walks up to git root and checks if any indexed project has that root path.
    If cwd is inside a project directory, returns that project's ID.
    Returns None if no matching project is found (fall back to all-projects).
    """
    cwd = Path.cwd().resolve()
    if not cwd.is_dir():
        return None

    # Walk up to git root
    try:
        result = subprocess.run(
            ["git", "-C", str(cwd), "rev-parse", "--show-toplevel"],
            capture_output=True, text=True, check=True, timeout=5,
        )
        root = Path(result.stdout.strip()).resolve()
    except Exception:
        root = cwd

    storage = _get_storage()

    # Check if the git root matches an indexed project
    proj = storage.get_project_by_root(str(root))
    if proj:
        return proj.id

    # Also check if cwd itself is inside any indexed project's root
    # (e.g., cwd is a subdirectory of the project root)
    cwd_str = str(cwd)
    for p in storage.list_projects():
        if p.root_path and not p.is_remote and cwd_str.startswith(p.root_path):
            return p.id

    return None


def _resolve_project_id(project: str | None) -> int | None:
    """Resolve optional project name to project_id.

    When project is None, auto-detects the current project from cwd to avoid
    cross-project contamination (e.g., returning pydantic results when working
    in the arrow repo). Falls back to all-projects search only if cwd doesn't
    match any indexed project.

    Returns None if no project can be determined (search all projects).
    Returns the project ID if found.
    Returns _PROJECT_NOT_FOUND (-1) if the project name was given but not
    found, so callers don't silently fall back to all-projects search.
    """
    if project is None:
        return _detect_project_from_cwd()
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
    """Auto-index cwd or refresh stale local projects. Returns error JSON or None.

    - If no projects exist: index cwd (auto-detect git root).
    - If local projects exist: do an incremental re-index so edits made
      by the agent since the last tool call are picked up automatically.
      The indexer skips unchanged files (hash check), so this is fast.
    """
    storage = _get_storage()
    projects = storage.list_projects()

    if projects:
        # Refresh local projects incrementally
        indexer = _get_indexer()
        for proj in projects:
            if proj.root_path and not proj.is_remote:
                root = Path(proj.root_path)
                if root.is_dir():
                    try:
                        indexer.index_codebase(root)
                    except Exception:
                        logger.debug(
                            "Incremental refresh failed for %s",
                            proj.name,
                        )
        return None

    cwd = Path.cwd()
    if not cwd.is_dir():
        return json.dumps({
            "error": "No projects indexed. Run index_codebase(path) first."
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
            "error": "No projects indexed. Run index_codebase(path) first."
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


# ─── Formatting helpers ─────────────────────────────────────────────────


def _fmt_chunk(chunk: dict, show_score: bool = False) -> str:
    """Format a code chunk as a readable text block."""
    header_parts = [f"# {chunk.get('file', '?')}"]
    name = chunk.get("name") or chunk.get("test_name", "")
    kind = chunk.get("kind", "")
    lines = chunk.get("lines", "")
    if name:
        header_parts.append(f"  {kind} {name}" if kind else f"  {name}")
    if lines:
        header_parts[0] += f":{lines}"
    if show_score and "score" in chunk:
        header_parts.append(f"  score={chunk['score']}")
    header = "".join(header_parts)

    content = chunk.get("content", "")
    if not content:
        return header
    return f"{header}\n{content}"


def _fmt_chunks(chunks: list[dict], **kwargs) -> str:
    """Format a list of code chunks separated by blank lines."""
    return "\n\n".join(_fmt_chunk(c, **kwargs) for c in chunks)


# ─── MCP Tools (core search & indexing) ─────────────────────────────────


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
def search_code(query: str, limit: int = 5, project: str | None = None) -> str:
    """Hybrid search the indexed codebase using BM25 + semantic vector search.

    Args:
        query: Search query (keywords, function names, natural language).
        limit: Maximum number of results to return (default 5).
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

    chunks = []
    for r in results:
        chunks.append({
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

    return f"Found {len(chunks)} results\n\n" + _fmt_chunks(
        chunks, show_score=True
    )


@mcp.tool()
def search_regex(
    pattern: str,
    limit: int = 50,
    context_lines: int = 2,
    project: str | None = None,
) -> str:
    """Search code with a regex pattern, showing matched lines with context.

    Searches actual files on disk (like grep -n -C) for precise line-level
    results. Falls back to searching indexed chunks for remote projects.

    Args:
        pattern: Python regex pattern (e.g. r"except.*:.*log", r"os\\.environ").
        limit: Maximum number of matching lines to return (default 50).
        context_lines: Lines of context around each match, like grep -C (default 2).
        project: Optional project name to scope search.

    Returns:
        Matched lines with file:line references and surrounding context,
        grouped by file. Matches are highlighted with >> markers.
    """
    if not pattern or not pattern.strip():
        return json.dumps({"error": "pattern is required"})
    if limit <= 0:
        return json.dumps({"error": "limit must be a positive integer"})
    limit = min(limit, 500)
    context_lines = max(0, min(context_lines, 10))

    try:
        compiled = re.compile(pattern)
    except re.error as exc:
        return json.dumps({"error": f"Invalid regex: {exc}"})

    err = _ensure_indexed()
    if err:
        return err

    storage = _get_storage()
    project_id = _resolve_project_id(project)
    err = _check_project_id(project_id, project) if project else None
    if err:
        return err

    t0 = time.time()

    # Determine project root for on-disk search
    project_root = None
    if project_id is not None and project_id != _PROJECT_NOT_FOUND:
        proj_rec = storage.get_project(project_id)
        if proj_rec and proj_rec.root_path and not proj_rec.is_remote:
            root_path = Path(proj_rec.root_path)
            if root_path.is_dir():
                project_root = root_path

    if project_root:
        # On-disk search: grep actual files for precise line-level results
        results = _search_regex_on_disk(
            compiled, project_root, limit, context_lines
        )
    else:
        # Fallback: search indexed chunks (for remote projects or no root)
        results = _search_regex_in_chunks(
            compiled, storage, project_id, limit, context_lines
        )

    latency = (time.time() - t0) * 1000
    storage.record_tool_call(
        "search_regex", latency, project_id=project_id
    )

    return results


def _search_regex_on_disk(
    compiled: re.Pattern,
    project_root: Path,
    limit: int,
    context_lines: int,
) -> str:
    """Search files on disk with regex, returning grep-like output."""
    from .discovery import discover_files

    match_groups: list[dict] = []
    total_matches = 0

    for filepath in discover_files(project_root):
        if total_matches >= limit:
            break
        try:
            with open(filepath, "r", encoding="utf-8", errors="replace") as f:
                lines = f.readlines()
        except (OSError, UnicodeDecodeError):
            continue

        # Find matching line numbers
        match_line_nos = []
        for i, line in enumerate(lines):
            if compiled.search(line):
                match_line_nos.append(i)

        if not match_line_nos:
            continue

        # Build context groups (merge overlapping contexts)
        rel_path = str(filepath.relative_to(project_root))
        file_matches: list[dict] = []

        for match_line in match_line_nos:
            if total_matches >= limit:
                break
            total_matches += 1

            ctx_start = max(0, match_line - context_lines)
            ctx_end = min(len(lines), match_line + context_lines + 1)

            # Merge with previous group if contexts overlap
            if file_matches and file_matches[-1]["ctx_end"] >= ctx_start:
                prev = file_matches[-1]
                prev["ctx_end"] = ctx_end
                prev["match_lines"].append(match_line)
            else:
                file_matches.append({
                    "ctx_start": ctx_start,
                    "ctx_end": ctx_end,
                    "match_lines": [match_line],
                })

        if file_matches:
            match_groups.append({
                "file": rel_path,
                "abs_path": str(filepath),
                "groups": file_matches,
                "lines": lines,
            })

    return _format_regex_results(compiled, match_groups, total_matches)


def _search_regex_in_chunks(
    compiled: re.Pattern,
    storage: Storage,
    project_id: int | None,
    limit: int,
    context_lines: int,
) -> str:
    """Search indexed chunks with regex (fallback for remote projects)."""
    chunks = storage.search_regex(
        compiled.pattern, limit=limit * 3, project_id=project_id
    )

    match_groups: list[dict] = []
    total_matches = 0

    for chunk in chunks:
        if total_matches >= limit:
            break
        file_rec = storage.get_file_by_id(chunk.file_id)
        if not file_rec:
            continue

        text = chunk.content_text or ""
        lines = text.split("\n")
        match_line_nos = []
        for i, line in enumerate(lines):
            if compiled.search(line):
                match_line_nos.append(i)

        if not match_line_nos:
            continue

        file_matches: list[dict] = []
        for match_line in match_line_nos:
            if total_matches >= limit:
                break
            total_matches += 1

            ctx_start = max(0, match_line - context_lines)
            ctx_end = min(len(lines), match_line + context_lines + 1)

            if file_matches and file_matches[-1]["ctx_end"] >= ctx_start:
                prev = file_matches[-1]
                prev["ctx_end"] = ctx_end
                prev["match_lines"].append(match_line)
            else:
                file_matches.append({
                    "ctx_start": ctx_start,
                    "ctx_end": ctx_end,
                    "match_lines": [match_line],
                })

        if file_matches:
            match_groups.append({
                "file": file_rec.path,
                "abs_path": file_rec.path,
                "groups": file_matches,
                "lines": lines,
                "line_offset": chunk.start_line,
            })

    return _format_regex_results(compiled, match_groups, total_matches)


def _format_regex_results(
    compiled: re.Pattern,
    match_groups: list[dict],
    total_matches: int,
) -> str:
    """Format regex results in a grep-like style with context."""
    if not match_groups:
        return f"Regex /{compiled.pattern}/ — 0 matches"

    parts = [
        f"Regex /{compiled.pattern}/ — {total_matches} matches "
        f"in {len(match_groups)} files\n"
    ]

    for file_group in match_groups:
        file_path = file_group["file"]
        lines = file_group["lines"]
        line_offset = file_group.get("line_offset", 1)  # 1-based for on-disk
        parts.append(f"# {file_path}")

        for group in file_group["groups"]:
            ctx_start = group["ctx_start"]
            ctx_end = group["ctx_end"]
            match_lines_set = set(group["match_lines"])

            for i in range(ctx_start, ctx_end):
                if i >= len(lines):
                    break
                line_text = lines[i].rstrip("\n") if isinstance(lines[i], str) else lines[i]
                line_no = i + line_offset
                is_match = i in match_lines_set

                if is_match:
                    # Highlight the match with >>> <<< markers
                    highlighted = compiled.sub(
                        lambda m: f">>>{m.group(0)}<<<", line_text
                    )
                    parts.append(f"  {line_no:>5} >> {highlighted}")
                else:
                    parts.append(f"  {line_no:>5}    {line_text}")

            # Separator between groups within same file
            if group != file_group["groups"][-1]:
                parts.append("        ...")

        parts.append("")  # blank line between files

    return "\n".join(parts)


@mcp.tool()
def get_context(
    query: str, token_budget: int = 0, project: str | None = None,
    deduplicate: bool = True,
) -> str:
    """Get the most relevant code for a query using relevance-first retrieval.

    This is the primary tool. It runs hybrid search, ranks results by
    relevance, and returns only chunks that pass relevance thresholds.
    The number of results is driven by relevance scores, not by filling
    a token budget.

    Args:
        query: What you're looking for (natural language or keywords).
        token_budget: Hard token ceiling (safety net). Set to 0 (default)
                      for automatic ceiling based on query type. The ceiling
                      prevents runaway responses but is never a fill target —
                      most queries return well under the ceiling.
        project: Optional project name to scope search. Omit for all projects.
        deduplicate: Whether to deprioritize chunks already sent in this
                     session. When True (default), previously sent chunks
                     are demoted in ranking but still returned if highly
                     relevant. Set to False to treat every query independently.

    Returns:
        The most relevant code chunks (only those passing relevance cutoffs).
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

    # Resolve budget: caller arg > config > auto-estimate
    cfg = get_config()
    if token_budget <= 0:
        token_budget = cfg.search.token_budget  # 0 = auto
    auto = token_budget <= 0
    search_limit = 50  # default for explicit budgets
    query_classification = None
    if auto:
        token_budget, search_limit, query_classification = (
            searcher.estimate_budget(query, project_id=project_id)
        )

    # Conversation-aware dedup: penalize or skip already-sent chunks
    sent = storage.get_sent_chunk_ids(_session_id)
    session_tokens = storage.get_session_token_total(_session_id)
    dedup_strategy = "penalize" if deduplicate else "none"

    t0 = time.time()
    context = searcher.get_context(
        query, token_budget=token_budget, project_id=project_id,
        exclude_chunk_ids=sent, frecency_boost=cfg.search.frecency_boost,
        dedup_strategy=dedup_strategy,
        search_limit=search_limit,
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
        return (
            f"No results for: {query}\n\n"
            f"Indexed: {stats['files']} files, {stats['chunks']} chunks\n"
            "Suggestions:\n"
            "- Try broader or alternative keywords\n"
            "- Use search_structure() to find by function/class name\n"
            "- Use file_summary() if you know the file path"
        )

    budget_str = f"{context['token_budget']}t ({context['budget_mode']})"
    meta = (
        f"query: {query}\n"
        f"budget: {budget_str} "
        f"| used: {context['tokens_used']}t "
        f"| {context['chunks_returned']}/{context['chunks_searched']} chunks"
    )
    if context.get("session_chunks_excluded"):
        meta += f" | {context['session_chunks_excluded']} excluded (already sent)"

    return meta + "\n\n" + _fmt_chunks(context["chunks"])


@mcp.tool()
def search_structure(
    symbol: str, kind: str = "any", project: str | None = None
) -> str:
    """Find functions, classes, or variables by name via the AST structure index.

    Returns precise results with source code included. Exact name matches
    are returned exclusively when found; prefix matches are only included
    when there is no exact match.

    Args:
        symbol: Name to search for. Exact matches prioritized over prefix.
        kind: Filter by kind: "function", "class", "method", "any".
        project: Optional project name to scope search.

    Returns:
        JSON array of matching definitions with source code.
    """
    valid_kinds = {"function", "class", "method", "any"}
    storage = _get_storage()
    if not symbol or not symbol.strip():
        return json.dumps({"error": "symbol is required"})

    if kind not in valid_kinds:
        return json.dumps({
            "error": (
                f"Invalid kind: {kind!r}. "
                f"Must be one of: {', '.join(sorted(valid_kinds))}"
            ),
        })

    err = _ensure_indexed()
    if err:
        return err

    symbol_name = symbol.strip()
    project_id = _resolve_project_id(project)
    symbols = storage.search_symbols(
        symbol_name,
        kind=kind if kind != "any" else None,
        project_id=project_id,
    )

    # If we have exact matches, only return those — avoids prefix noise
    # (e.g. searching "search" returning "search_code", "search_fts", …)
    exact = [s for s in symbols if s.name == symbol_name]
    matched = exact if exact else symbols

    # Deduplicate by chunk_id
    seen_chunks: set[int] = set()
    output = []
    for sym in matched:
        if sym.chunk_id in seen_chunks:
            continue
        seen_chunks.add(sym.chunk_id)

        chunk = storage.get_chunk_by_id(sym.chunk_id)
        if not chunk:
            continue

        file_rec = storage.get_file_by_id(chunk.file_id)
        proj = (
            storage.get_project(chunk.project_id)
            if chunk.project_id else None
        )

        # Include actual source so callers don't need a separate Read
        try:
            source = decompress_content(chunk.content)
        except Exception:
            source = chunk.content_text or ""

        output.append({
            "name": sym.name,
            "kind": sym.kind,
            "file": file_rec.path if file_rec else "",
            "project": proj.name if proj else "",
            "lines": f"{chunk.start_line}-{chunk.end_line}",
            "source": source,
        })

    return json.dumps(output, indent=2)


# ─── Register tools from submodules ─────────────────────────────────────
# Import after mcp is defined so @mcp.tool() decorators register correctly.

# Register tools from submodules and re-export for backward compatibility.
from .tools_analysis import (  # noqa: F401, E402
    file_summary,
    get_diff_context,
    get_tests_for,
    resolve_symbol,
    trace_dependencies,
    what_breaks_if_i_change,
)
from .tools_github import (  # noqa: F401, E402
    index_git_commit,
    index_github_content,
    index_github_repo,
    index_pr,
)
from .tools_data import (  # noqa: F401, E402
    context_pressure,
    delete_memory,
    detect_stale_index,
    export_index,
    find_dead_code,
    import_index,
    list_memories,
    recall_memory,
    remove_project,
    store_memory,
    tool_analytics,
)


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
