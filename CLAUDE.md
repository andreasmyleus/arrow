# Arrow

A local MCP server that gives Claude Code a brain for your codebase.

## Code Context

This project has an MCP server `arrow` for fast code search.
Use these MCP tools BEFORE reading files manually.

### Search & Retrieval (use these first)

- `get_context(query, token_budget?, project?)` — primary tool: relevant code with auto token budgeting, conversation-aware dedup
- `search_code(query, limit?, project?)` — hybrid BM25 + vector search with frecency boost
- `search_regex(pattern, limit?, project?)` — exact regex matching against indexed chunks
- `search_structure(symbol, kind?, project?)` — find functions/classes/methods by name via AST index

### Analysis & Impact

- `get_diff_context(file, line_start?, line_end?, project?)` — changed functions + all callers/dependents
- `what_breaks_if_i_change(file, function?, project?)` — full impact analysis: callers, tests, dependents, risk level
- `trace_dependencies(file, depth?, project?)` — import graph: what this file imports and who imports it
- `resolve_symbol(symbol, project?)` — cross-repo symbol resolution (finds definitions across all indexed repos)
- `get_tests_for(function, file?, project?)` — find tests via import tracing + naming conventions
- `find_dead_code(project?)` — unreferenced functions/methods
- `detect_stale_index(project?)` — check index freshness vs disk state

### Project Management

- `index_codebase(path, force?)` — index/re-index a local codebase (incremental by default)
- `list_projects()` — all indexed projects with stats, git info, watcher status
- `project_summary(project?)` — language distribution, file structure, entry points
- `file_summary(path, project?)` — functions, classes, imports, token counts for one file
- `remove_project(project)` — remove a project and all its indexed data

### GitHub & Remote Repos

- `index_github_repo(owner, repo, branch?, sparse_paths?)` — clone + index via `gh` CLI (supports tags)
- `index_github_content(owner, repo, branch, files)` — index code you've already fetched
- `index_git_commit(path, ref)` — snapshot a repo at a specific commit/tag/branch
- `index_pr(path, pr_number)` — index both sides of a PR for comparison

### Portability

- `export_index(project)` — export project index as JSON bundle
- `import_index(bundle_json)` — import a previously exported bundle

### Session & Memory

- `context_pressure()` — context window usage stats (tokens sent, chunks, status)
- `tool_analytics(hours?)` — call counts, latency, tokens saved per tool
- `store_memory(key, content, category?, project?)` — persist knowledge across sessions
- `recall_memory(query, category?, project?, limit?)` — search stored memories
- `list_memories(category?, project?)` — list all memories
- `delete_memory(memory_id?, key?, category?, project?)` — remove a memory

## Remote Repos

When you need code from a GitHub repo:
1. **Always check the index first** — use `search_code(query, project="owner/repo")` or `get_context(query, project="owner/repo")`
2. **If not indexed**, use `index_github_repo(owner, repo)` to clone and index it in one step
3. **Never manually fetch + pass files** — `index_github_repo` handles cloning, caching, and incremental updates automatically
4. The clone is cached at `~/.arrow/clones/` so subsequent indexes are fast incremental updates
5. Supports tags and branches: `index_github_repo(owner, repo, branch="v2.12.5")`

## Development

- Python 3.10+, dependencies in `pyproject.toml`
- Source code in `src/arrow/`
- Tests: `pytest tests/ -v` (195 tests across 22 files)
- Benchmarks: `python benchmarks/bench.py` and `python benchmarks/bench_comparison.py`

## Architecture

- `server.py` — MCP server init, shared helpers, core search tools, entry points
- `tools_analysis.py` — analysis tools (dependencies, impact, diff context, symbol resolution, tests)
- `tools_github.py` — GitHub/remote indexing tools (clone, content, commits, PRs)
- `tools_data.py` — data management tools (stale detection, export/import, analytics, memory)
- `storage.py` — SQLite WAL database, schema, all data access
- `indexer.py` — tree-sitter AST chunking, incremental indexing
- `search.py` — hybrid BM25 + vector search, reciprocal rank fusion, token budgeting
- `chunker.py` — tree-sitter parsing into semantic chunks (functions, classes)
- `embedder.py` — ONNX Jina embeddings for vector search
- `vector_store.py` — usearch vector index
- `git_utils.py` — git info detection, remote URL parsing
- `discovery.py` — file discovery with gitignore support
- `hasher.py` — xxHash3 content hashing
- `watcher.py` — watchdog file system monitoring
- `config.py` — configuration management
- `cli.py` — CLI commands
