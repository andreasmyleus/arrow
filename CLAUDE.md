# Arrow

A local MCP server that gives Claude Code a brain for your codebase.

## Code Context

This project has an MCP server `arrow` for fast code search.

Use these MCP tools BEFORE reading files manually:
- `get_context(query)` — get relevant code (auto-budgets, conversation-aware, auto-compacts)
- `search_code(query)` — search the codebase with frecency boost
- `search_structure(symbol)` — find definitions
- `get_diff_context(file)` — see changed code + all callers/dependents
- `what_breaks_if_i_change(file, function)` — impact analysis before changes
- `get_tests_for(function)` — find tests for a function
- `resolve_symbol(symbol)` — find definitions across all indexed repos
- `find_dead_code()` — find unreferenced functions
- `store_memory(key, content)` / `recall_memory(query)` — persist knowledge across sessions
- `context_pressure()` — check context window usage
- `list_projects()` — see all indexed repos

## Development

- Python 3.10+, dependencies in `pyproject.toml`
- Source code in `src/arrow/`
- Tests: `pytest tests/ -v` (197 tests across 20 files)
- Benchmarks: `python benchmarks/bench.py` and `python benchmarks/bench_comparison.py`

## Architecture

- `storage.py` — SQLite WAL database, schema, all data access
- `indexer.py` — tree-sitter AST chunking, incremental indexing
- `search.py` — hybrid BM25 + vector search, reciprocal rank fusion, token budgeting
- `server.py` — MCP server with 27 tools, file watchers, session tracking
- `chunker.py` — tree-sitter parsing into semantic chunks (functions, classes)
- `embedder.py` — ONNX Jina embeddings for vector search
- `vector_store.py` — usearch vector index
- `git_utils.py` — git info detection, remote URL parsing
- `discovery.py` — file discovery with gitignore support
- `hasher.py` — xxHash3 content hashing
- `watcher.py` — watchdog file system monitoring
- `cli.py` — CLI commands
