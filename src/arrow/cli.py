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

    print(f"  Project:        {result.get('project_name', '?')}")
    if result.get("git_branch"):
        print(f"  Branch:         {result['git_branch']}")
    if result.get("git_commit"):
        print(f"  Commit:         {result['git_commit'][:8]}")
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


def cmd_snapshot(args):
    """Index a codebase at a specific git commit/tag/branch."""
    _setup_logging(args.log_level)

    root = Path(args.path).resolve()
    if not root.is_dir():
        print(f"Error: {args.path} is not a directory", file=sys.stderr)
        sys.exit(1)

    storage, indexer, _ = _get_components(args.db_path, args.vec_path)

    print(f"Indexing {root} at {args.ref}...")
    result = indexer.index_git_commit(root, args.ref)

    if "error" in result:
        print(f"Error: {result['error']}", file=sys.stderr)
        storage.close()
        sys.exit(1)

    if result.get("status") == "already indexed":
        print(f"  Already indexed: {result['project_name']}")
        storage.close()
        return

    print(f"  Project:        {result.get('project_name', '?')}")
    if result.get("commit"):
        commit = result["commit"]
        print(f"  Commit:         {commit['short_sha']} — {commit['message']}")
        print(f"  Author:         {commit['author']} ({commit['date']})")
    print(f"  Files scanned:  {result['files_scanned']}")
    print(f"  Files indexed:  {result['files_indexed']}")
    print(f"  Chunks created: {result['chunks_created']}")
    print(f"  Languages:      {result['languages']}")
    print(f"  Time:           {result['elapsed']}")

    if result.get("errors"):
        print(f"  Errors:         {result['errors']}")

    storage.close()


def cmd_pr(args):
    """Index both sides of a pull request."""
    _setup_logging(args.log_level)

    root = Path(args.path).resolve()
    if not root.is_dir():
        print(f"Error: {args.path} is not a directory", file=sys.stderr)
        sys.exit(1)

    storage, indexer, _ = _get_components(args.db_path, args.vec_path)

    print(f"Indexing PR #{args.number} in {root}...")
    result = indexer.index_pr(root, args.number)

    if "error" in result:
        print(f"Error: {result['error']}", file=sys.stderr)
        storage.close()
        sys.exit(1)

    print(f"  PR:             #{result['pr_number']} — {result['title']}")
    print(f"  Base:           {result['base_branch']} ({result['base_commit']})")
    print(f"  Head:           {result['head_branch']} ({result['head_commit']})")
    print(f"  Changed files:  {result['changed_file_count']}")
    print(f"  Base project:   {result['base_project']}")
    print(f"  Head project:   {result['head_project']}")
    print(f"  Time:           {result['elapsed']}")

    if result["changed_files"]:
        print(f"\n  Changed files:")
        for f in result["changed_files"][:30]:
            print(f"    {f}")
        if result["changed_file_count"] > 30:
            print(f"    ... and {result['changed_file_count'] - 30} more")

    print(f"\n  Search base: arrow search \"query\" --project \"{result['base_project']}\"")
    print(f"  Search head: arrow search \"query\" --project \"{result['head_project']}\"")

    storage.close()


def cmd_search(args):
    """Search the indexed codebase."""
    _setup_logging("WARNING")

    storage, _, searcher = _get_components(args.db_path, args.vec_path)

    if not storage.list_projects():
        print("Error: No project indexed. Run `arrow index <path>` first.", file=sys.stderr)
        sys.exit(1)

    project_id = None
    if args.project:
        proj = storage.get_project_by_name(args.project)
        if not proj:
            print(f"Error: Project not found: {args.project}", file=sys.stderr)
            sys.exit(1)
        project_id = proj.id

    results = searcher.search(args.query, limit=args.limit, project_id=project_id)

    if not results:
        print("No results found.")
        storage.close()
        return

    for i, r in enumerate(results, 1):
        proj_label = f" [{r.project_name}]" if r.project_name else ""
        print(f"\n--- [{i}] {r.file_path}:{r.chunk.start_line}-{r.chunk.end_line} "
              f"({r.chunk.kind}: {r.chunk.name}){proj_label} score={r.score:.4f} ---")
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

    if not storage.list_projects():
        print("Error: No project indexed. Run `arrow index <path>` first.", file=sys.stderr)
        sys.exit(1)

    project_id = None
    if args.project:
        proj = storage.get_project_by_name(args.project)
        if not proj:
            print(f"Error: Project not found: {args.project}", file=sys.stderr)
            sys.exit(1)
        project_id = proj.id

    ctx = searcher.get_context(
        args.query, token_budget=args.budget, project_id=project_id
    )

    if args.json:
        print(json.dumps(ctx, indent=2))
    else:
        print(f"Query: {ctx['query']}")
        print(f"Tokens: {ctx['tokens_used']}/{ctx['token_budget']}")
        print(f"Chunks: {len(ctx['chunks'])}")
        print()
        for chunk in ctx["chunks"]:
            trunc = " [truncated]" if chunk.get("truncated") else ""
            proj_label = f" [{chunk.get('project', '')}]" if chunk.get("project") else ""
            print(f"--- {chunk['file']}:{chunk['lines']} ({chunk['kind']}: {chunk['name']})"
                  f"{proj_label} [{chunk['tokens']} tokens]{trunc} ---")
            print(chunk["content"])
            print()

    storage.close()


def cmd_status(args):
    """Show index status and stats."""
    _setup_logging("WARNING")

    storage, indexer, _ = _get_components(args.db_path, args.vec_path)

    projects = storage.list_projects()
    if not projects:
        print("No projects indexed.")
        storage.close()
        return

    if args.project:
        proj = storage.get_project_by_name(args.project)
        if not proj:
            print(f"Error: Project not found: {args.project}", file=sys.stderr)
            sys.exit(1)
        projects = [proj]

    for proj in projects:
        stats = storage.get_stats(project_id=proj.id)
        print(f"\nProject:    {proj.name}")
        if proj.root_path:
            print(f"  Path:       {proj.root_path}")
        if proj.remote_url:
            print(f"  Remote:     {proj.remote_url}")
        if proj.git_branch:
            print(f"  Branch:     {proj.git_branch}")
        if proj.git_commit:
            print(f"  Commit:     {proj.git_commit[:8]}")
        print(f"  Files:      {stats['files']}")
        print(f"  Chunks:     {stats['chunks']}")
        print(f"  Symbols:    {stats['symbols']}")
        if proj.index_duration:
            print(f"  Duration:   {proj.index_duration}")
        if stats["languages"]:
            print(f"  Languages:")
            for lang, count in stats["languages"].items():
                print(f"    {lang}: {count} files")

    storage.close()


def cmd_repos(args):
    """List all indexed projects."""
    _setup_logging("WARNING")

    storage, _, _ = _get_components(args.db_path, args.vec_path)

    projects = storage.list_projects()
    if not projects:
        print("No projects indexed.")
        storage.close()
        return

    for proj in projects:
        stats = storage.get_stats(project_id=proj.id)
        remote = " (remote)" if proj.is_remote else ""
        branch = f" {proj.git_branch}" if proj.git_branch else ""
        commit = f"@{proj.git_commit[:8]}" if proj.git_commit else ""
        files = f"{stats['files']} files"
        dur = f"  [{proj.index_duration}]" if proj.index_duration else ""
        print(f"  {proj.name}{remote}  {branch}{commit}  {files}{dur}")
        if proj.root_path:
            print(f"    {proj.root_path}")

    storage.close()


def cmd_symbols(args):
    """Search for symbols (functions, classes, etc.)."""
    _setup_logging("WARNING")

    storage, _, _ = _get_components(args.db_path, args.vec_path)

    if not storage.list_projects():
        print("Error: No project indexed. Run `arrow index <path>` first.", file=sys.stderr)
        sys.exit(1)

    project_id = None
    if args.project:
        proj = storage.get_project_by_name(args.project)
        if not proj:
            print(f"Error: Project not found: {args.project}", file=sys.stderr)
            sys.exit(1)
        project_id = proj.id

    kind = args.kind if args.kind != "any" else None
    symbols = storage.search_symbols(
        args.name, kind=kind, limit=args.limit, project_id=project_id
    )

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


def cmd_diff_context(args):
    """Show changed code plus callers and dependents."""
    _setup_logging("WARNING")

    storage, indexer, searcher = _get_components(args.db_path, args.vec_path)

    project_id = None
    if args.project:
        proj = storage.get_project_by_name(args.project)
        if not proj:
            print(f"Error: Project not found: {args.project}", file=sys.stderr)
            sys.exit(1)
        project_id = proj.id

    file_rec = storage.get_file(args.file, project_id=project_id)
    if not file_rec:
        print(f"Error: File not indexed: {args.file}", file=sys.stderr)
        sys.exit(1)

    # Use server tool logic directly
    from .server import get_diff_context as _get_diff_context
    result = json.loads(_get_diff_context(
        args.file, args.line_start, args.line_end, args.project
    ))

    if "error" in result:
        print(f"Error: {result['error']}", file=sys.stderr)
        sys.exit(1)

    print(f"File: {result['file']}")
    print(f"Changed functions: {len(result['changed_functions'])}")
    for func in result["changed_functions"]:
        print(f"  {func['kind']}: {func['name']} ({func['lines']})")

    if result["callers"]:
        print(f"\nCallers ({result['total_callers']}):")
        for caller in result["callers"][:20]:
            print(f"  {caller['file']}:{caller['lines']} "
                  f"({caller['kind']}: {caller['name']}) -> {caller['calls']}")

    if result["dependent_files"]:
        print(f"\nDependent files ({result['total_dependents']}):")
        for dep in result["dependent_files"]:
            print(f"  {dep['path']}")

    storage.close()


def cmd_impact(args):
    """Show what breaks if you change a file or function."""
    _setup_logging("WARNING")

    from .server import what_breaks_if_i_change
    result = json.loads(what_breaks_if_i_change(
        args.file, args.function, args.project
    ))

    if "error" in result:
        print(f"Error: {result['error']}", file=sys.stderr)
        sys.exit(1)

    print(f"Impact analysis: {result['file']}")
    print(f"Symbols: {', '.join(result['symbols_analyzed'])}")
    print(f"Risk: {result['risk'].upper()}")

    summary = result["summary"]
    print(f"\n  Callers:    {summary['total_callers']}")
    print(f"  Tests:      {summary['total_tests']}")
    print(f"  Dependents: {summary['total_dependents']}")

    if result["callers"]:
        print(f"\nCallers:")
        for caller in result["callers"][:20]:
            print(f"  {caller['file']} — {caller['kind']}: "
                  f"{caller['name']} (calls {caller['calls']})")

    if result["affected_tests"]:
        print(f"\nAffected tests:")
        for test in result["affected_tests"][:20]:
            print(f"  {test['file']} — {test['test_name']} "
                  f"(references {test['references']})")


def cmd_tests_for(args):
    """Find tests for a specific function."""
    _setup_logging("WARNING")

    from .server import get_tests_for
    result = json.loads(get_tests_for(
        args.function, args.file, args.project
    ))

    print(f"Tests for: {result['function']}")
    if result.get("source_file"):
        print(f"Source: {result['source_file']}")

    if not result["tests"]:
        print("No tests found.")
        return

    print(f"Found {result['total']} test(s):\n")
    for test in result["tests"]:
        print(f"--- {test['file']}:{test['lines']} "
              f"({test['test_name']}) [{test['match_type']}] ---")
        lines = test["content"].splitlines()
        for line in lines[:15]:
            print(f"  {line}")
        if len(lines) > 15:
            print(f"  ... ({len(lines) - 15} more lines)")
        print()


def cmd_stale(args):
    """Check if the index is stale."""
    _setup_logging("WARNING")

    from .server import detect_stale_index
    result = json.loads(detect_stale_index(args.project))

    if isinstance(result, dict) and "error" in result:
        print(f"Error: {result['error']}", file=sys.stderr)
        sys.exit(1)

    for proj in result:
        print(f"\n{proj['project']}:")
        print(f"  Files:  {proj['total_files']}")
        print(f"  Drift:  {proj['drift_count']} ({proj['drift_pct']}%)")
        print(f"  Status: {proj['recommendation']}")
        if proj["stale_files"]:
            print(f"  Stale:")
            for f in proj["stale_files"][:10]:
                print(f"    {f}")


def cmd_deadcode(args):
    """Find dead code (functions with zero callers)."""
    _setup_logging("WARNING")

    from .server import find_dead_code
    result = json.loads(find_dead_code(args.project))

    print(f"Dead code: {result['total']} unreferenced functions\n")
    for item in result["dead_code"]:
        print(f"  {item['kind']:10s} {item['name']:30s} "
              f"{item['file']}:{item['lines']}")


def cmd_export(args):
    """Export a project index."""
    _setup_logging("WARNING")

    from .server import export_index
    result = export_index(args.project)

    if args.output:
        Path(args.output).write_text(result)
        data = json.loads(result)
        print(f"Exported {data['stats']['files']} files, "
              f"{data['stats']['chunks']} chunks to {args.output}")
    else:
        print(result)


def cmd_import(args):
    """Import a project index."""
    _setup_logging("WARNING")

    bundle = Path(args.file).read_text()
    from .server import import_index
    result = json.loads(import_index(bundle))

    if "error" in result:
        print(f"Error: {result['error']}", file=sys.stderr)
        sys.exit(1)

    print(f"Imported: {result['project_name']}")
    print(f"  Files:   {result['files']}")
    print(f"  Chunks:  {result['chunks']}")
    print(f"  Symbols: {result['symbols']}")


def cmd_analytics(args):
    """Show tool usage analytics."""
    _setup_logging("WARNING")

    from .server import tool_analytics
    result = json.loads(tool_analytics(args.hours))

    print(f"Tool analytics (last {result['window_hours']}h):\n")
    print(f"  Total calls:        {result['total_calls']}")
    print(f"  Total tokens saved: {result['total_tokens_saved']}\n")

    for tool in result["tools"]:
        avg = tool["avg_latency_ms"] or 0
        saved = tool["total_tokens_saved"] or 0
        print(f"  {tool['tool_name']:25s} "
              f"{tool['calls']:4d} calls  "
              f"{avg:6.1f}ms avg  "
              f"{saved:6d} tokens saved")


def cmd_pressure(args):
    """Show context window pressure."""
    _setup_logging("WARNING")

    from .server import context_pressure
    result = json.loads(context_pressure())

    print(f"Context pressure: {result['context_pressure_pct']}%"
          f" ({result['status']})")
    print(f"  Session tokens: {result['session_tokens']:,}"
          f" / {result['compact_threshold']:,}")
    print(f"  Chunks sent:    {result['chunks_sent']}")
    print(f"  {result['recommendation']}")


def cmd_compact(args):
    """Compact session context."""
    _setup_logging("WARNING")

    from .server import compact_context
    result = json.loads(compact_context(reset=args.reset))

    if "message" in result:
        print(result["message"])
        return

    print(f"Compacted {result['chunks']} chunks "
          f"across {result['files']} files")
    print(f"  Before: {result['session_tokens_before']:,} tokens")
    print(f"  After:  {result['compact_tokens']:,} tokens"
          f" ({result['savings_pct']}% savings)")
    if args.reset:
        print("  Session cleared.")


def cmd_remove(args):
    """Remove a project from the index."""
    _setup_logging("WARNING")

    storage, _, _ = _get_components(args.db_path, args.vec_path)

    proj = storage.get_project_by_name(args.name)
    if not proj:
        print(f"Error: Project not found: {args.name}", file=sys.stderr)
        sys.exit(1)

    storage.delete_project(proj.id)
    print(f"Removed project '{args.name}' and all its data.")
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
    p_search.add_argument("--project", type=str, default=None, help="Project name filter")
    p_search.set_defaults(func=cmd_search)

    # context
    p_ctx = subparsers.add_parser("context", help="Get context for a query")
    p_ctx.add_argument("query", help="What you're looking for")
    p_ctx.add_argument("--budget", type=int, default=8000, help="Token budget (default: 8000)")
    p_ctx.add_argument("--json", action="store_true", help="Output as JSON")
    p_ctx.add_argument("--project", type=str, default=None, help="Project name filter")
    p_ctx.set_defaults(func=cmd_context)

    # status
    p_status = subparsers.add_parser("status", help="Show index status")
    p_status.add_argument("--project", type=str, default=None, help="Show specific project")
    p_status.set_defaults(func=cmd_status)

    # repos
    p_repos = subparsers.add_parser("repos", help="List all indexed projects")
    p_repos.set_defaults(func=cmd_repos)

    # symbols
    p_sym = subparsers.add_parser("symbols", help="Search for symbols")
    p_sym.add_argument("name", help="Symbol name (prefix match)")
    p_sym.add_argument(
        "--kind", default="any",
        choices=["any", "function", "class", "method", "interface", "module"],
        help="Filter by kind",
    )
    p_sym.add_argument("--limit", type=int, default=20, help="Max results (default: 20)")
    p_sym.add_argument("--project", type=str, default=None, help="Project name filter")
    p_sym.set_defaults(func=cmd_symbols)

    # snapshot
    p_snap = subparsers.add_parser("snapshot", help="Index at a specific git commit/tag/branch")
    p_snap.add_argument("path", help="Path to the git repository")
    p_snap.add_argument("ref", help="Git ref: commit SHA, tag, or branch name")
    p_snap.add_argument(
        "--log-level", choices=["DEBUG", "INFO", "WARNING", "ERROR"],
        default="INFO", help="Log level",
    )
    p_snap.set_defaults(func=cmd_snapshot)

    # pr
    p_pr = subparsers.add_parser("pr", help="Index both sides of a pull request")
    p_pr.add_argument("path", help="Path to the git repository")
    p_pr.add_argument("number", type=int, help="PR number")
    p_pr.add_argument(
        "--log-level", choices=["DEBUG", "INFO", "WARNING", "ERROR"],
        default="INFO", help="Log level",
    )
    p_pr.set_defaults(func=cmd_pr)

    # diff-context
    p_diff = subparsers.add_parser(
        "diff-context", help="Show changed code + callers/dependents",
    )
    p_diff.add_argument("file", help="Relative path to changed file")
    p_diff.add_argument(
        "--line-start", type=int, default=0,
        help="Start line (0=auto from git diff)",
    )
    p_diff.add_argument(
        "--line-end", type=int, default=0,
        help="End line (0=auto from git diff)",
    )
    p_diff.add_argument("--project", type=str, default=None)
    p_diff.set_defaults(func=cmd_diff_context)

    # impact
    p_impact = subparsers.add_parser(
        "impact", help="Show what breaks if you change a file/function",
    )
    p_impact.add_argument("file", help="Relative path to the file")
    p_impact.add_argument(
        "--function", type=str, default=None,
        help="Specific function name (omit for all)",
    )
    p_impact.add_argument("--project", type=str, default=None)
    p_impact.set_defaults(func=cmd_impact)

    # tests-for
    p_tests = subparsers.add_parser(
        "tests-for", help="Find tests for a function",
    )
    p_tests.add_argument("function", help="Function name")
    p_tests.add_argument(
        "--file", type=str, default=None,
        help="Source file (narrows search)",
    )
    p_tests.add_argument("--project", type=str, default=None)
    p_tests.set_defaults(func=cmd_tests_for)

    # remove
    p_stale = subparsers.add_parser("stale", help="Check if index is stale")
    p_stale.add_argument("--project", default=None, help="Project name")
    p_stale.set_defaults(func=cmd_stale)

    p_dead = subparsers.add_parser("deadcode", help="Find dead code")
    p_dead.add_argument("--project", default=None, help="Project name")
    p_dead.set_defaults(func=cmd_deadcode)

    p_export = subparsers.add_parser("export", help="Export a project index")
    p_export.add_argument("project", help="Project name")
    p_export.add_argument("-o", "--output", default=None, help="Output file path")
    p_export.set_defaults(func=cmd_export)

    p_import = subparsers.add_parser("import", help="Import a project index")
    p_import.add_argument("file", help="JSON bundle file path")
    p_import.set_defaults(func=cmd_import)

    p_analytics = subparsers.add_parser("analytics", help="Show tool usage analytics")
    p_analytics.add_argument("--hours", type=int, default=24, help="Hours to look back")
    p_analytics.set_defaults(func=cmd_analytics)

    subparsers.add_parser(
        "pressure", help="Show context window pressure"
    ).set_defaults(func=cmd_pressure)

    p_compact = subparsers.add_parser(
        "compact", help="Compact session context"
    )
    p_compact.add_argument(
        "--reset", action="store_true",
        help="Clear session history after compacting",
    )
    p_compact.set_defaults(func=cmd_compact)

    p_remove = subparsers.add_parser("remove", help="Remove a project from the index")
    p_remove.add_argument("name", help="Project name (e.g. org/repo)")
    p_remove.set_defaults(func=cmd_remove)

    args = parser.parse_args()

    if not args.command:
        parser.print_help()
        sys.exit(0)

    args.func(args)
