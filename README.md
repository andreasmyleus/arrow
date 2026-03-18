# Arrow

A local, high-performance MCP server that gives Claude Code intelligent code indexing and retrieval — the same capabilities that power Cursor IDE's context engine.

## What it does

Arrow pre-indexes your codebase using tree-sitter AST parsing, then serves relevant code chunks to Claude Code via MCP tools. Instead of reading entire files, Claude gets exactly the code it needs, using a fraction of the context window.

- **AST-based chunking** — tree-sitter parses code into semantic units (functions, classes) across 64+ languages
- **Hybrid search** — BM25 full-text + semantic vector search (Phase 2)
- **Incremental indexing** — xxHash3 content-hashing ensures only changed files are re-indexed
- **Token-budget aware** — never sends more context than necessary
- **100% local** — no cloud APIs, no external dependencies, runs on CPU

## Installation

```bash
# Clone and install
git clone <repo-url> arrow
cd arrow
python -m venv .venv
source .venv/bin/activate
pip install -e .
```

## Quick Start

### 1. Register with Claude Code

```bash
claude mcp add --transport stdio arrow -- python -m arrow.server
```

### 2. Index your project

Use the `index_codebase` tool in Claude Code:

```
> Index my codebase at /path/to/project
```

Or Claude will call it automatically when configured.

### 3. Available MCP Tools

| Tool | Description |
|------|-------------|
| `index_codebase(path)` | Index/re-index a codebase (incremental) |
| `project_summary()` | Compressed project overview |
| `search_code(query)` | BM25 full-text search |
| `search_structure(symbol)` | Find definitions by name |
| `file_summary(path)` | Summary of a specific file |

### 4. Add to CLAUDE.md (recommended)

Add this to your project's `CLAUDE.md` to make Claude always use Arrow:

```markdown
## Code Context

This project has an MCP server `arrow` for fast code search.

Use these MCP tools BEFORE reading files manually:
- `search_code(query)` — search the codebase
- `project_summary()` — understand project structure
- `search_structure(symbol)` — find definitions
- `file_summary(path)` — summarize a file
```

## Tech Stack

| Component | Library | Why |
|-----------|---------|-----|
| MCP SDK | `mcp` (Python) | Official SDK |
| AST parsing | `tree-sitter` | 64+ languages, incremental |
| Content hashing | `xxhash` (xxHash3-128) | 31 GB/s throughput |
| Token counting | `tiktoken` | Exact counts for Claude |
| Compression | `zstandard` (zstd) | 3.4x faster than zlib |
| Database | SQLite (WAL + FTS5) | Zero dependencies |

## License

MIT
