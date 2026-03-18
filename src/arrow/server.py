"""Arrow MCP Server — intelligent code indexing and retrieval for Claude Code."""

from __future__ import annotations

import json
import logging
import os
from pathlib import Path
from mcp.server.fastmcp import FastMCP

from .chunker import decompress_content
from .indexer import Indexer
from .storage import Storage

logger = logging.getLogger(__name__)

# Default database location
DEFAULT_DB_DIR = Path.home() / ".arrow"
DEFAULT_DB_PATH = DEFAULT_DB_DIR / "index.db"

# Create MCP server
mcp = FastMCP(
    "arrow",
    instructions="Local code indexing and intelligent retrieval for Claude Code",
)

# Global state
_storage: Storage | None = None
_indexer: Indexer | None = None


def _get_storage() -> Storage:
    global _storage
    if _storage is None:
        db_path = os.environ.get("ARROW_DB_PATH", str(DEFAULT_DB_PATH))
        _storage = Storage(db_path)
    return _storage


def _get_indexer() -> Indexer:
    global _indexer
    if _indexer is None:
        _indexer = Indexer(_get_storage())
    return _indexer


@mcp.tool()
def index_codebase(path: str, force: bool = False) -> str:
    """Index or re-index a codebase. Incremental by default — only changed files are re-indexed.

    Args:
        path: Absolute path to the codebase root directory.
        force: If True, re-index all files regardless of whether they changed.

    Returns:
        JSON status with file/chunk counts, languages found, and timing.
    """
    root = Path(path).resolve()
    if not root.is_dir():
        return json.dumps({"error": f"Not a directory: {path}"})

    indexer = _get_indexer()
    result = indexer.index_codebase(root, force=force)
    return json.dumps(result, indent=2)


@mcp.tool()
def project_summary() -> str:
    """Get a compressed project overview: language distribution, file structure,
    entry points, and key stats. Cached and updated incrementally.

    Returns:
        JSON summary of the indexed project.
    """
    indexer = _get_indexer()
    storage = _get_storage()

    root = storage.get_project_meta("root_path")
    if not root:
        return json.dumps({
            "error": "No project indexed yet. Run index_codebase(path) first."
        })

    summary = indexer.generate_project_summary()
    return json.dumps(summary, indent=2)


@mcp.tool()
def search_code(query: str, limit: int = 10) -> str:
    """Search the indexed codebase using BM25 full-text search.

    Args:
        query: Search query (keywords, function names, etc.)
        limit: Maximum number of results to return (default 10).

    Returns:
        JSON array of matching code chunks with file path, line numbers, and content.
    """
    storage = _get_storage()

    if not storage.get_project_meta("root_path"):
        return json.dumps({
            "error": "No project indexed yet. Run index_codebase(path) first."
        })

    results = storage.search_fts(query, limit=limit)

    output = []
    for chunk_id, score in results:
        chunk = storage.get_chunk_by_id(chunk_id)
        if chunk is None:
            continue

        file_rec = storage.get_file_by_id(chunk.file_id)
        file_path = file_rec.path if file_rec else ""

        # Decompress content
        try:
            content = decompress_content(chunk.content) if isinstance(chunk.content, bytes) else chunk.content
        except Exception:
            content = "<decompression error>"

        output.append({
            "file": file_path or chunk.scope_context.split("::")[0],
            "name": chunk.name,
            "kind": chunk.kind,
            "lines": f"{chunk.start_line}-{chunk.end_line}",
            "score": round(score, 4),
            "content": content,
            "tokens": chunk.token_count,
        })

    return json.dumps(output, indent=2)


@mcp.tool()
def search_structure(symbol: str, kind: str = "any") -> str:
    """Find functions, classes, or variables by name via the AST structure index.

    Args:
        symbol: Name to search for (supports prefix matching).
        kind: Filter by kind: "function", "class", "method", "any" (default).

    Returns:
        JSON array of matching symbol definitions.
    """
    storage = _get_storage()

    if not storage.get_project_meta("root_path"):
        return json.dumps({
            "error": "No project indexed yet. Run index_codebase(path) first."
        })

    symbols = storage.search_symbols(symbol, kind=kind if kind != "any" else None)

    output = []
    for sym in symbols:
        chunk = storage.get_chunk_by_id(sym.chunk_id)
        if chunk:
            output.append({
                "name": sym.name,
                "kind": sym.kind,
                "file": chunk.scope_context.split("::")[0],
                "lines": f"{chunk.start_line}-{chunk.end_line}",
            })

    return json.dumps(output, indent=2)


@mcp.tool()
def file_summary(path: str) -> str:
    """Get a summary of a specific indexed file: exports, functions, dependencies, complexity.

    Args:
        path: Relative path to the file (as shown in project_summary).

    Returns:
        JSON summary of the file.
    """
    storage = _get_storage()
    file_rec = storage.get_file(path)

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

    return json.dumps({
        "path": path,
        "language": file_rec.language,
        "total_tokens": total_tokens,
        "total_chunks": len(chunks),
        "functions": functions,
        "classes": classes,
        "other": other,
    }, indent=2)


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

    if args.transport == "stdio":
        mcp.run(transport="stdio")
    else:
        mcp.run(transport="streamable-http", host="0.0.0.0", port=args.port)


if __name__ == "__main__":
    main()
