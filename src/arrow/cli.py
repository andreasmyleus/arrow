"""Arrow CLI — index, search, and serve from the command line."""

from __future__ import annotations

import json
import logging
import os
import sys
import time
from pathlib import Path

DEFAULT_DB_DIR = Path.home() / ".arrow"
DEFAULT_DB_PATH = DEFAULT_DB_DIR / "index.db"
DEFAULT_VECTOR_PATH = DEFAULT_DB_DIR / "vectors.usearch"


def _setup_logging(level: str = "INFO"):
    logging.basicConfig(
        level=getattr(logging, level),
        format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    )


def _get_components(db_path=None, vec_path=None):
    from .embedder import Embedder, get_embedder
    from .indexer import Indexer
    from .search import HybridSearcher
    from .storage import Storage
    from .vector_store import VectorStore

    db = db_path or os.environ.get("ARROW_DB_PATH", str(DEFAULT_DB_PATH))
    vec = vec_path or os.environ.get("ARROW_VECTOR_PATH", str(DEFAULT_VECTOR_PATH))

    storage = Storage(db)
    vector_store = VectorStore(vec)
    embedder = get_embedder()
    indexer = Indexer(storage, vector_store=vector_store, embedder=embedder)
    searcher = HybridSearcher(storage, vector_store=vector_store, embedder=embedder)

    return storage, indexer, searcher


def cmd_serve(args):
    """Start the MCP server."""
    _setup_logging(args.log_level)

    if args.db_path:
        os.environ["ARROW_DB_PATH"] = args.db_path
    if args.vec_path:
        os.environ["ARROW_VECTOR_PATH"] = args.vec_path

    from .server import mcp

    if args.transport == "stdio":
        mcp.run(transport="stdio")
    else:
        mcp.run(transport="streamable-http", host="0.0.0.0", port=args.port)


def cmd_index(args):
    """Index a codebase."""
    _setup_logging(args.log_level)

    root = Path(args.path).resolve()
    if not root.is_dir():
        print(f"Error: {args.path} is not a directory", file=sys.stderr)
        sys.exit(1)

    storage, indexer, _ = _get_components(args.db_path, args.vec_path)

    print(f"Indexing {root}...")
    result = indexer.index_codebase(root, force=args.force)

    print(f"  Files scanned:  {result['files_scanned']}")
    print(f"  Files indexed:  {result['files_indexed']}")
    print(f"  Files skipped:  {result['files_skipped']}")
    print(f"  Files removed:  {result['files_removed']}")
    print(f"  Chunks created: {result['chunks_created']}")
    print(f"  Languages:      {result['languages']}")
    print(f"  Time:           {result['elapsed']}")

    if result.get("errors"):
        print(f"  Errors:         {result['errors']}")

    storage.close()


def cmd_search(args):
    """Search the indexed codebase."""
    _setup_logging("WARNING")

    storage, _, searcher = _get_components(args.db_path, args.vec_path)

    if not storage.get_project_meta("root_path"):
        print("Error: No project indexed. Run `arrow index <path>` first.", file=sys.stderr)
        sys.exit(1)

    results = searcher.search(args.query, limit=args.limit)

    if not results:
        print("No results found.")
        storage.close()
        return

    for i, r in enumerate(results, 1):
        print(f"\n--- [{i}] {r.file_path}:{r.chunk.start_line}-{r.chunk.end_line} "
              f"({r.chunk.kind}: {r.chunk.name}) score={r.score:.4f} ---")
        # Show first 20 lines of content
        lines = r.content.splitlines()
        for line in lines[:20]:
            print(f"  {line}")
        if len(lines) > 20:
            print(f"  ... ({len(lines) - 20} more lines)")

    storage.close()


def cmd_context(args):
    """Get context for a query within a token budget."""
    _setup_logging("WARNING")

    storage, _, searcher = _get_components(args.db_path, args.vec_path)

    if not storage.get_project_meta("root_path"):
        print("Error: No project indexed. Run `arrow index <path>` first.", file=sys.stderr)
        sys.exit(1)

    ctx = searcher.get_context(args.query, token_budget=args.budget)

    if args.json:
        print(json.dumps(ctx, indent=2))
    else:
        print(f"Query: {ctx['query']}")
        print(f"Tokens: {ctx['tokens_used']}/{ctx['token_budget']}")
        print(f"Chunks: {len(ctx['chunks'])}")
        print()
        for chunk in ctx["chunks"]:
            trunc = " [truncated]" if chunk.get("truncated") else ""
            print(f"--- {chunk['file']}:{chunk['lines']} ({chunk['kind']}: {chunk['name']})"
                  f" [{chunk['tokens']} tokens]{trunc} ---")
            print(chunk["content"])
            print()

    storage.close()


def cmd_status(args):
    """Show index status and stats."""
    _setup_logging("WARNING")

    storage, indexer, _ = _get_components(args.db_path, args.vec_path)

    root = storage.get_project_meta("root_path")
    if not root:
        print("No project indexed.")
        storage.close()
        return

    summary = indexer.generate_project_summary()

    print(f"Project:    {summary['root']}")
    print(f"Files:      {summary['total_files']}")
    print(f"Chunks:     {summary['total_chunks']}")
    print(f"Symbols:    {summary['total_symbols']}")
    print(f"Last index: {summary['index_duration']}")
    print(f"Languages:")
    for lang, count in summary["languages"].items():
        print(f"  {lang}: {count} files")
    print(f"Structure:")
    for d in summary["structure"][:10]:
        print(f"  {d['directory']}/: {d['files']} files")
    if summary["entry_points"]:
        print(f"Entry points:")
        for ep in summary["entry_points"]:
            print(f"  {ep}")

    storage.close()


def cmd_symbols(args):
    """Search for symbols (functions, classes, etc.)."""
    _setup_logging("WARNING")

    storage, _, _ = _get_components(args.db_path, args.vec_path)

    if not storage.get_project_meta("root_path"):
        print("Error: No project indexed. Run `arrow index <path>` first.", file=sys.stderr)
        sys.exit(1)

    kind = args.kind if args.kind != "any" else None
    symbols = storage.search_symbols(args.name, kind=kind, limit=args.limit)

    if not symbols:
        print("No symbols found.")
        storage.close()
        return

    for sym in symbols:
        chunk = storage.get_chunk_by_id(sym.chunk_id)
        file_rec = storage.get_file_by_id(sym.file_id)
        file_path = file_rec.path if file_rec else "?"
        lines = f"{chunk.start_line}-{chunk.end_line}" if chunk else "?"
        print(f"  {sym.kind:10s} {sym.name:30s} {file_path}:{lines}")

    storage.close()


def main():
    """Arrow CLI entry point."""
    import argparse

    parser = argparse.ArgumentParser(
        prog="arrow",
        description="Arrow — intelligent code indexing and retrieval",
    )
    parser.add_argument(
        "--db-path", type=str, default=None,
        help=f"Database path (default: {DEFAULT_DB_PATH})",
    )
    parser.add_argument(
        "--vec-path", type=str, default=None,
        help=f"Vector index path (default: {DEFAULT_VECTOR_PATH})",
    )

    subparsers = parser.add_subparsers(dest="command", help="Available commands")

    # serve
    p_serve = subparsers.add_parser("serve", help="Start the MCP server")
    p_serve.add_argument(
        "--transport", choices=["stdio", "http"], default="stdio",
        help="Transport protocol (default: stdio)",
    )
    p_serve.add_argument("--port", type=int, default=8080, help="HTTP port (default: 8080)")
    p_serve.add_argument(
        "--log-level", choices=["DEBUG", "INFO", "WARNING", "ERROR"],
        default="INFO", help="Log level (default: INFO)",
    )
    p_serve.set_defaults(func=cmd_serve)

    # index
    p_index = subparsers.add_parser("index", help="Index a codebase")
    p_index.add_argument("path", help="Path to the codebase root")
    p_index.add_argument("--force", action="store_true", help="Force full re-index")
    p_index.add_argument(
        "--log-level", choices=["DEBUG", "INFO", "WARNING", "ERROR"],
        default="INFO", help="Log level",
    )
    p_index.set_defaults(func=cmd_index)

    # search
    p_search = subparsers.add_parser("search", help="Search the codebase")
    p_search.add_argument("query", help="Search query")
    p_search.add_argument("--limit", type=int, default=10, help="Max results (default: 10)")
    p_search.set_defaults(func=cmd_search)

    # context
    p_ctx = subparsers.add_parser("context", help="Get context for a query")
    p_ctx.add_argument("query", help="What you're looking for")
    p_ctx.add_argument("--budget", type=int, default=8000, help="Token budget (default: 8000)")
    p_ctx.add_argument("--json", action="store_true", help="Output as JSON")
    p_ctx.set_defaults(func=cmd_context)

    # status
    p_status = subparsers.add_parser("status", help="Show index status")
    p_status.set_defaults(func=cmd_status)

    # symbols
    p_sym = subparsers.add_parser("symbols", help="Search for symbols")
    p_sym.add_argument("name", help="Symbol name (prefix match)")
    p_sym.add_argument(
        "--kind", default="any",
        choices=["any", "function", "class", "method", "interface", "module"],
        help="Filter by kind",
    )
    p_sym.add_argument("--limit", type=int, default=20, help="Max results (default: 20)")
    p_sym.set_defaults(func=cmd_symbols)

    args = parser.parse_args()

    if not args.command:
        parser.print_help()
        sys.exit(0)

    args.func(args)
