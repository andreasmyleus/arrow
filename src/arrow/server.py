"""Arrow MCP Server — intelligent code indexing and retrieval for Claude Code."""

from __future__ import annotations

import json
import logging
import os
import threading
from pathlib import Path

from mcp.server.fastmcp import FastMCP

from .embedder import Embedder, get_embedder
from .indexer import Indexer
from .search import HybridSearcher
from .storage import Storage
from .vector_store import VectorStore
from .watcher import FileWatcher

logger = logging.getLogger(__name__)

DEFAULT_DB_DIR = Path.home() / ".arrow"
DEFAULT_DB_PATH = DEFAULT_DB_DIR / "index.db"
DEFAULT_VECTOR_PATH = DEFAULT_DB_DIR / "vectors.usearch"

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


def _get_project_lock(project_id: int) -> threading.Lock:
    """Get or create a per-project lock for write serialization."""
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
            indexer = _get_indexer()
            indexer.index_codebase(root)
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


def _resolve_project_id(project: str | None) -> int | None:
    """Resolve optional project name to project_id."""
    if project is None:
        return None
    storage = _get_storage()
    proj = storage.get_project_by_name(project)
    return proj.id if proj else None


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
    storage = _get_storage()
    indexer = _get_indexer()

    if not storage.list_projects():
        return json.dumps({
            "error": "No projects indexed yet. Run index_codebase(path) first."
        })

    project_id = _resolve_project_id(project)
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
    storage = _get_storage()
    if not storage.list_projects():
        return json.dumps({
            "error": "No projects indexed yet. Run index_codebase(path) first."
        })

    project_id = _resolve_project_id(project)
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
    query: str, token_budget: int = 8000, project: str | None = None
) -> str:
    """Get the most relevant code for a query, compressed to fit a token budget.

    This is the primary tool. It runs hybrid search, ranks results, and
    returns the most relevant code fitting within the specified token budget.

    Args:
        query: What you're looking for (natural language or keywords).
        token_budget: Maximum tokens to return (default 8000).
        project: Optional project name to scope search. Omit for all projects.

    Returns:
        JSON with the most relevant code chunks within the token budget.
    """
    storage = _get_storage()
    if not storage.list_projects():
        return json.dumps({
            "error": "No projects indexed yet. Run index_codebase(path) first."
        })

    project_id = _resolve_project_id(project)
    searcher = _get_searcher()
    context = searcher.get_context(
        query, token_budget=token_budget, project_id=project_id
    )
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
    storage = _get_storage()
    if not storage.list_projects():
        return json.dumps({
            "error": "No projects indexed yet. Run index_codebase(path) first."
        })

    project_id = _resolve_project_id(project)
    symbols = storage.search_symbols(
        symbol, kind=kind if kind != "any" else None, project_id=project_id
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
    storage = _get_storage()
    project_id = _resolve_project_id(project)
    file_rec = storage.get_file(file, project_id=project_id)

    if not file_rec:
        return json.dumps({"error": f"File not indexed: {file}"})

    imports = storage.conn.execute(
        "SELECT symbol FROM imports WHERE source_file = ?",
        (file_rec.id,),
    ).fetchall()

    file_stem = Path(file).stem
    importers = storage.conn.execute(
        """SELECT DISTINCT f.path FROM imports i
           JOIN files f ON f.id = i.source_file
           WHERE i.symbol LIKE ?""",
        (f"%{file_stem}%",),
    ).fetchall()

    return json.dumps({
        "file": file,
        "language": file_rec.language,
        "imports": [row[0] for row in imports],
        "imported_by": [row[0] for row in importers],
        "depth": depth,
    }, indent=2)


@mcp.tool()
def file_summary(path: str, project: str | None = None) -> str:
    """Get a summary of a specific indexed file.

    Args:
        path: Relative path to the file.
        project: Optional project name to scope the file lookup.

    Returns:
        JSON summary with functions, classes, imports, and token counts.
    """
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
        total_tokens += chunk.token_count
        entry = {
            "name": chunk.name,
            "lines": f"{chunk.start_line}-{chunk.end_line}",
            "tokens": chunk.token_count,
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
        "imports": [row[0] for row in imports],
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
    indexer = _get_indexer()
    result = indexer.index_remote_files(owner, repo, branch, files)
    return json.dumps(result, indent=2)


@mcp.tool()
def remove_project(project: str) -> str:
    """Remove a project and all its indexed data.

    Args:
        project: Project name (e.g. "org/repo").

    Returns:
        JSON confirmation.
    """
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

    if args.transport == "stdio":
        mcp.run(transport="stdio")
    else:
        mcp.run(transport="streamable-http", host="0.0.0.0", port=args.port)


if __name__ == "__main__":
    main()
