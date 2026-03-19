"""Data management tools — stale detection, dead code, export/import, analytics, memory."""

from __future__ import annotations

import json
import logging
import time
from pathlib import Path

from .server import (
    _get_storage,
    _project_locks,
    _resolve_project_id,
    _session_id,
    _stop_watcher,
    mcp,
)

logger = logging.getLogger(__name__)


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
            "error": f"Invalid category: {category!r}. Must be one of: "
                     f"{', '.join(sorted(_VALID_CATEGORIES))}",
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
