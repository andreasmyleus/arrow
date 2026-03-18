# Arrow

A local, high-performance MCP server that gives Claude Code intelligent code indexing and retrieval — the same capabilities that power Cursor IDE's context engine.

## What it does

Arrow pre-indexes your codebases using tree-sitter AST parsing, then serves relevant code chunks to Claude Code via MCP tools. Instead of reading entire files, Claude gets exactly the code it needs, using a fraction of the context window.

- **Multi-repo support** — index all your local repos in parallel, organized by `org/repo`, in one shared database
- **Git-aware** — tracks branch + HEAD commit per project, auto-updates when commits change
- **GitHub remote caching** — cache content from GitHub MCP reads for cross-project search
- **AST-based chunking** — tree-sitter parses code into semantic units (functions, classes) across 64+ languages
- **Hybrid search** — BM25 full-text (FTS5) + semantic vector search (usearch + ONNX embeddings)
- **Incremental indexing** — xxHash3 content-hashing ensures only changed files are re-indexed
- **Token-budget aware** — `get_context` returns the most relevant code within an exact token limit
- **Automatic re-indexing** — watchdog monitors file changes per-project and re-indexes in the background
- **Concurrent-safe** — SQLite WAL mode + per-project write locks for multiple Claude Code sessions / subagents
- **100% local** — no cloud APIs, no external dependencies, runs on CPU

## Performance

### Micro-benchmarks

```
Hashing:      6,300 MB/s (xxHash3-128)
Indexing:     146 files/s (tree-sitter + tokenization)
Incremental:  2ms (hash check only, no re-indexing)
Search:       0.5ms per query (FTS5 BM25)
get_context:  1-4ms (search + rank + token trim)
```

### Arrow vs Traditional (Grep + Read)

Real-world coding tasks on Arrow's own codebase (22 files, ~4k lines). Arrow uses `get_context` with a 4000-token budget. Traditional approach uses Glob + Grep + Read (the way Claude Code works without Arrow).

| Task | Arrow | Traditional | Token Savings |
|------|-------|-------------|---------------|
| How does hybrid search work? | 3,976 tok / 4ms | ~6,999 tok / 22ms | 43% |
| Find storage/database functions | 3,990 tok / 1ms | ~20,243 tok / 10ms | 80% |
| Find index_codebase implementation | 3,938 tok / 1ms | ~5,917 tok / 13ms | 33% |
| How does file discovery work? | 3,982 tok / 1ms | ~8,645 tok / 13ms | 54% |
| Find all test fixtures | 3,987 tok / 1ms | ~8,881 tok / 13ms | 55% |
| Bug: FTS returns no results | 3,999 tok / 1ms | ~9,464 tok / 16ms | 58% |
| Add new MCP tool | 3,949 tok / 1ms | ~62,135 tok / 13.2s | 94% |
| Chunks flow: indexer to storage | 3,993 tok / 2ms | ~15,498 tok / 14ms | 74% |
| Debug: get_context slow | 3,998 tok / 1ms | ~19,131 tok / 12ms | 79% |
| Review Docker setup | 3,961 tok / 0ms | ~970,799 tok / 12.6s | 100% |
| **Total** | **39,773 tok / 14ms** | **~1,127,712 tok / 25.9s** | **96%** |

**Key takeaway:** Arrow delivers relevant code in **1-4ms** using **96% fewer tokens** than reading files manually. For broad tasks ("review Docker setup", "add new MCP tool"), the savings are extreme because Arrow targets only the relevant chunks instead of reading entire files.

### Comprehensive Benchmark (110 queries, 10 complexity tiers)

Tested across query types ranging from simple symbol lookups to broad architectural reviews. All queries use a 4000-token budget. Benchmarked on Arrow's own codebase (14 files, 47 chunks).

| Complexity Tier | Queries | Arrow Tokens | Traditional Tokens | Savings | Avg Time |
|-----------------|---------|-------------|-------------------|---------|----------|
| Symbol lookup | 15 | 57,468 | 302,607 | 81% | 0.4ms |
| Method lookup | 15 | 42,768 | 190,510 | 78% | 0.4ms |
| Single concept | 10 | 25,763 | 133,193 | 81% | 0.4ms |
| Two concepts | 10 | 39,413 | 173,685 | 77% | 0.5ms |
| How-does-X-work | 10 | 35,929 | 248,423 | 86% | 0.9ms |
| Cross-file tracing | 10 | 31,761 | 205,294 | 85% | 0.9ms |
| Debugging | 10 | 35,453 | 230,516 | 85% | 0.8ms |
| Implementation planning | 10 | 39,826 | 263,587 | 85% | 0.9ms |
| Architecture review | 10 | 39,891 | 666,190 | 94% | 0.9ms |
| Broad / exploratory | 10 | 39,778 | 770,235 | 95% | 1.0ms |
| **Total** | **110** | **388,050** | **3,184,240** | **88%** | **0.7ms** |

**Total benchmark time: 76ms** (0.7ms avg per query). Savings scale with query complexity — simple lookups save ~77-81%, while broad architectural questions save 94-95% because the traditional approach reads entire files.

## CLI

Arrow includes a full CLI for indexing, searching, and serving without Claude Code.

```
arrow <command> [options]

Commands:
  serve     Start the MCP server (stdio or HTTP)
  index     Index a codebase (auto-detects org/repo from git)
  search    Search the indexed codebase
  context   Get relevant code within a token budget
  status    Show index status and stats
  repos     List all indexed projects
  symbols   Search for symbols (functions, classes, etc.)
  remove    Remove a project from the index
```

### Examples

```bash
# Index multiple repos (each gets its own org/repo identity)
arrow index /path/to/project
arrow index /path/to/another/project

# List all indexed repos with git info
arrow repos

# Check status of a specific project
arrow status --project org/repo

# Search across all projects
arrow search "database connection"

# Search within a specific project
arrow search "authentication" --project myorg/myrepo

# Get context-window-friendly output
arrow context "authentication flow" --budget 4000

# Find all functions named "parse"
arrow symbols parse --kind function

# Remove a project from the index
arrow remove org/repo

# Start MCP server for Claude Code
arrow serve
arrow serve --transport http --port 8080
```

## Installation

```bash
git clone <repo-url>
cd arrow
python -m venv .venv
source .venv/bin/activate
pip install -e .
```

Requires Python 3.10+.

## Quick Start

### 1. Register with Claude Code

```bash
claude mcp add --transport stdio arrow -- /path/to/arrow/.venv/bin/python -m arrow serve
```

### 2. Index your project

From the CLI:

```bash
arrow index /path/to/project
```

Or via MCP in Claude Code:

```
> Index my codebase at /path/to/project
```

### 3. Available MCP Tools (10)

| Tool | Description |
|------|-------------|
| `index_codebase(path)` | Index/re-index a codebase (auto-detects git org/repo) |
| `get_context(query, token_budget, project?)` | **Main tool.** Get relevant code within a token budget |
| `search_code(query, project?)` | Hybrid BM25 + semantic search |
| `search_structure(symbol, project?)` | Find definitions by name via AST index |
| `trace_dependencies(file, project?)` | Show imports and reverse dependencies |
| `project_summary(project?)` | Compressed project overview (one or all) |
| `file_summary(path, project?)` | Per-file breakdown: functions, classes, imports |
| `list_projects()` | List all indexed projects with git info and file counts |
| `index_github_content(owner, repo, branch, files)` | Cache remote GitHub content for search |
| `remove_project(project)` | Remove a project and all its data |

All search/query tools accept an optional `project` parameter to scope results to a single repo. Omit it to search across all indexed projects.

### 4. Add to CLAUDE.md (recommended)

```markdown
## Code Context

This project has an MCP server `arrow` for fast code search.

Use these MCP tools BEFORE reading files manually:
- `get_context(query, token_budget)` — get relevant code for a task
- `search_code(query)` — search the codebase semantically
- `search_structure(symbol)` — find definitions
- `list_projects()` — see all indexed repos
- `project_summary()` — understand project structure
```

## Docker

```bash
# Build
docker build -t arrow .

# Run (mount your project as /workspace)
docker run -v /path/to/project:/workspace:ro -p 8080:8080 arrow

# Register with Claude Code (HTTP transport)
claude mcp add --transport http arrow http://localhost:8080/mcp
```

Or with docker-compose:

```bash
WORKSPACE_PATH=/path/to/project docker compose up -d
```

### Multi-arch build

```bash
docker buildx build --platform linux/amd64,linux/arm64 -t arrow:latest .
```

## Multi-Repo & Git-Aware Indexing

Arrow tracks all your repos in one shared database, organized by `org/repo` (auto-detected from git remote URLs).

- **Auto-detection** — `index_codebase(/path/to/repo)` reads `git remote get-url origin` to determine `org/repo` identity. Falls back to directory name if not a git repo.
- **Branch + commit tracking** — each project stores current branch and HEAD commit. Re-indexing detects when commits change.
- **Per-project file watchers** — each local project gets its own watchdog instance, auto-started on server startup.
- **GitHub content caching** — `index_github_content(owner, repo, branch, files)` lets Claude pass file contents from GitHub MCP reads into Arrow for search.
- **Scoped search** — pass `project="org/repo"` to any search tool to scope results, or omit to search everything.

### Concurrent Safety

Multiple Claude Code sessions or subagents can index different repos simultaneously:

- **SQLite WAL mode** — concurrent reads never block each other
- **Per-project write locks** — `threading.Lock` per project prevents overlapping index runs on the same project
- **Non-blocking watchers** — file change callbacks use `tryLock` to avoid blocking if an index is already running

## Architecture

```
Claude Code ──(JSON-RPC/stdio)──> Arrow MCP Server
                                    ├── Project Manager (git-aware, multi-repo)
                                    ├── Indexer (tree-sitter + xxHash3)
                                    ├── Hybrid Searcher (FTS5 + usearch)
                                    ├── Context Assembler (token budget)
                                    ├── Structure Analyzer (symbols + imports)
                                    ├── File Watchers (one per project, watchdog)
                                    ├── Per-Project Locks (concurrent safety)
                                    └── Storage (SQLite WAL + FTS5 + usearch)
```

## Tech Stack

| Component | Library | Why |
|-----------|---------|-----|
| MCP SDK | `mcp` (Python) | Official SDK |
| AST parsing | `tree-sitter` | 64+ languages, incremental |
| Vector search | `usearch` | 20x faster than FAISS, f16 quantization |
| Embeddings | `onnxruntime` + Jina | Auto-detect best CPU backend |
| Full-text search | SQLite FTS5 | BM25 scoring, zero dependencies |
| Content hashing | `xxhash` (xxHash3-128) | 31 GB/s throughput |
| Token counting | `tiktoken` | Exact counts for Claude |
| Compression | `zstandard` (zstd) | 3.4x faster than zlib |
| File watching | `watchdog` | Native OS APIs (FSEvents/inotify) |
| Database | SQLite (WAL mode) | 800+ writes/sec |

## Running Tests

```bash
pip install -e ".[test]"
pytest tests/ -v
```

## Running Benchmarks

```bash
python benchmarks/bench.py /path/to/codebase
```

## License

MIT
