"""Arrow MCP Server — intelligent code indexing and retrieval for Claude Code."""

from __future__ import annotations

import json
import logging
import os
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
    instructions="Local code indexing and intelligent retrieval for Claude Code",
)

# Global state
_storage: Storage | None = None
_indexer: Indexer | None = None
_vector_store: VectorStore | None = None
_embedder: Embedder | None = None
_searcher: HybridSearcher | None = None
_watcher: FileWatcher | None = None


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


def _start_watcher(root: str) -> None:
    """Start file watcher for automatic re-indexing."""
    global _watcher
    if _watcher is not None:
        _watcher.stop()

    def on_change():
        try:
            indexer = _get_indexer()
            indexer.index_codebase(root)
            logger.info("Background re-index complete")
        except Exception:
            logger.exception("Background re-index failed")

    _watcher = FileWatcher(root, on_change)
    _watcher.start()


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

    # Start file watcher for automatic background re-indexing
    _start_watcher(str(root))

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
    """Hybrid search the indexed codebase using BM25 + semantic vector search.

    Combines full-text BM25 (keyword matching) with embedding-based semantic
    search using reciprocal rank fusion. Falls back to BM25-only if embeddings
    are not yet ready.

    Args:
        query: Search query (keywords, function names, natural language).
        limit: Maximum number of results to return (default 10).

    Returns:
        JSON array of matching code chunks with file path, line numbers, and content.
    """
    storage = _get_storage()

    if not storage.get_project_meta("root_path"):
        return json.dumps({
            "error": "No project indexed yet. Run index_codebase(path) first."
        })

    searcher = _get_searcher()
    results = searcher.search(query, limit=limit)

    output = []
    for r in results:
        output.append({
            "file": r.file_path,
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
def get_context(query: str, token_budget: int = 8000) -> str:
    """Get the most relevant code for a query, compressed to fit a token budget.

    This is the primary tool. It runs hybrid search, ranks results, and
    returns the most relevant code fitting within the specified token budget.
    Use this before reading files manually.

    Args:
        query: What you're looking for (natural language or keywords).
        token_budget: Maximum tokens to return (default 8000).

    Returns:
        JSON with the most relevant code chunks within the token budget.
    """
    storage = _get_storage()

    if not storage.get_project_meta("root_path"):
        return json.dumps({
            "error": "No project indexed yet. Run index_codebase(path) first."
        })

    searcher = _get_searcher()
    context = searcher.get_context(query, token_budget=token_budget)
    return json.dumps(context, indent=2)


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

    symbols = storage.search_symbols(
        symbol, kind=kind if kind != "any" else None
    )

    output = []
    for sym in symbols:
        chunk = storage.get_chunk_by_id(sym.chunk_id)
        if chunk:
            file_rec = storage.get_file_by_id(chunk.file_id)
            output.append({
                "name": sym.name,
                "kind": sym.kind,
                "file": file_rec.path if file_rec else "",
                "lines": f"{chunk.start_line}-{chunk.end_line}",
            })

    return json.dumps(output, indent=2)


@mcp.tool()
def trace_dependencies(file: str, depth: int = 2) -> str:
    """Trace import dependencies for a file.

    Shows what a file imports and what imports it (reverse dependencies).

    Args:
        file: Relative path to the file.
        depth: How many levels deep to trace (default 2).

    Returns:
        JSON dependency graph with imports and importers.
    """
    storage = _get_storage()

    if not storage.get_project_meta("root_path"):
        return json.dumps({
            "error": "No project indexed yet. Run index_codebase(path) first."
        })

    file_rec = storage.get_file(file)
    if not file_rec:
        return json.dumps({"error": f"File not indexed: {file}"})

    # Get imports from this file
    imports = storage.conn.execute(
        "SELECT symbol FROM imports WHERE source_file = ?",
        (file_rec.id,),
    ).fetchall()

    # Get reverse dependencies (files that import this file)
    # Match by filename stem in import symbols
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
def file_summary(path: str) -> str:
    """Get a summary of a specific indexed file: exports, functions, dependencies.

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

    # Get imports
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
