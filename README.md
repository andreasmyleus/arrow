<div align="center">

# Arrow

**A local MCP server that gives Claude Code a brain for your codebase.**

*The same intelligent code retrieval that powers Cursor IDE — but open source, local, and built for Claude Code.*

[![Python 3.10+](https://img.shields.io/badge/python-3.10%2B-blue.svg)](https://www.python.org/downloads/)
[![License: MIT](https://img.shields.io/badge/License-MIT-green.svg)](LICENSE)
[![Tests](https://img.shields.io/badge/tests-197%20passing-brightgreen.svg)](#running-tests)
[![MCP Tools](https://img.shields.io/badge/MCP%20tools-27-purple.svg)](#available-mcp-tools-27)

```
96% fewer tokens   |   0.6ms avg query   |   64+ languages   |   27 MCP tools
```

</div>

---

## The Problem

Claude Code reads entire files with Glob + Grep + Read. On a moderately sized codebase, a single question can consume **1M+ tokens** and take **13+ seconds** just to gather context.

**Arrow fixes this.** It pre-indexes your code into semantic chunks (functions, classes, methods), then serves exactly the relevant pieces in **1-4ms** using **96% fewer tokens**.

```
Before:  "Review Docker setup"  →  970,799 tokens / 12.6s
After:   "Review Docker setup"  →    3,961 tokens / 0ms
```

## Quick Start

### 1. Install

```bash
git clone <repo-url>
cd arrow
python -m venv .venv && source .venv/bin/activate
pip install -e .
```

### 2. Register with Claude Code

```bash
claude mcp add --transport stdio arrow -- /path/to/arrow/.venv/bin/python -m arrow serve
```

### 3. Index your project

```bash
arrow index /path/to/project
```

Or just ask Claude: *"Index my codebase at /path/to/project"*

### 4. Add to your CLAUDE.md (recommended)

```markdown
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
```

That's it. Claude will now use Arrow automatically for all code lookups.

---

## Features

### Core Intelligence

| Feature | Description |
|---------|-------------|
| **AST-based chunking** | tree-sitter parses code into semantic units (functions, classes) across 64+ languages |
| **Hybrid search** | BM25 full-text (FTS5) + semantic vector search (usearch + ONNX embeddings) |
| **Smart token budgeting** | Auto-estimates optimal budget from query complexity (500 tok for lookups, 8000+ for architecture) |
| **Frecency-weighted results** | Recently/frequently accessed files are boosted in search rankings |
| **Incremental indexing** | xxHash3 content-hashing ensures only changed files are re-indexed |
| **Auto-warm on startup** | Background-indexes the working directory so the first query is instant |

### Code Analysis

| Feature | Description |
|---------|-------------|
| **Semantic diff context** | Changed code + all callers and dependents of modified functions |
| **Change impact analysis** | Traces reverse dependencies, affected tests, and risk level (low/medium/high) |
| **Cross-repo symbol resolution** | Find definitions across all indexed repos when tracing imports |
| **Test mapping** | Maps any function to its test files via import tracing + naming conventions |
| **Dead code detection** | Finds functions/classes with zero callers across the full index |
| **Stale index detection** | Detects drift between index and working tree |

### Multi-Repo & Git

| Feature | Description |
|---------|-------------|
| **Multi-repo support** | All repos in one shared database, organized by `org/repo` |
| **Git-aware** | Tracks branch + HEAD commit per project, auto-updates on commits |
| **Git history snapshots** | Index code at any commit, tag, or branch for historical search |
| **PR review** | Index both sides of a PR (base + head) for comparison |
| **GitHub remote caching** | Cache content from GitHub MCP reads for cross-project search |
| **Automatic re-indexing** | Watchdog monitors file changes per-project, re-indexes in background |

### Session Management

| Feature | Description |
|---------|-------------|
| **Conversation-aware context** | Tracks which chunks Claude has seen — never re-sends the same code |
| **Context window compaction** | Auto-compacts at 256k tokens, returns signatures instead of full code |
| **Long-term memory** | Persistent key-value memory with FTS search, survives across sessions |
| **Index export/import** | Share indexes across machines or CI with JSON bundles |
| **Tool analytics** | Tracks call counts, latency, and usage patterns per MCP tool |
| **Concurrent-safe** | SQLite WAL + per-project write locks for multiple sessions/subagents |

---

## Performance

### Micro-benchmarks

| Operation | Speed |
|-----------|-------|
| Hashing | 6,300 MB/s (xxHash3-128) |
| Indexing | 146 files/s (tree-sitter + tokenization) |
| Incremental check | 2ms (hash check only) |
| Search | 0.5ms per query (FTS5 BM25) |
| get_context | 1-4ms (search + rank + token trim) |

### Arrow vs Traditional (Grep + Read)

Real-world coding tasks on Arrow's own codebase. Arrow uses `get_context` with a 4000-token budget. Traditional uses Glob + Grep + Read.

| Task | Arrow | Traditional | Savings |
|------|-------|-------------|---------|
| How does hybrid search work? | 3,976 tok / 4ms | ~6,999 tok / 22ms | **43%** |
| Find storage/database functions | 3,990 tok / 1ms | ~20,243 tok / 10ms | **80%** |
| Add new MCP tool | 3,949 tok / 1ms | ~62,135 tok / 13.2s | **94%** |
| Review Docker setup | 3,961 tok / 0ms | ~970,799 tok / 12.6s | **100%** |
| **Total (10 tasks)** | **39,773 tok / 14ms** | **~1,127,712 tok / 25.9s** | **96%** |

<details>
<summary><b>Full 110-query benchmark across 10 complexity tiers</b></summary>

All queries use a 4000-token budget. Benchmarked on Arrow's own codebase (14 files, 161 chunks).

| Complexity Tier | Queries | Arrow Tokens | Traditional Tokens | Savings | Avg Time |
|-----------------|---------|-------------|-------------------|---------|----------|
| Symbol lookup | 15 | 45,857 | 289,543 | 84% | 0.4ms |
| Method lookup | 15 | 36,717 | 199,929 | 82% | 0.2ms |
| Single concept | 10 | 19,950 | 131,566 | 85% | 0.3ms |
| Two concepts | 10 | 34,793 | 177,044 | 80% | 0.4ms |
| How-does-X-work | 10 | 35,721 | 263,327 | 86% | 0.8ms |
| Cross-file tracing | 10 | 31,736 | 224,210 | 86% | 0.7ms |
| Debugging | 10 | 35,855 | 249,383 | 86% | 0.7ms |
| Implementation planning | 10 | 39,795 | 277,203 | 86% | 0.7ms |
| Architecture review | 10 | 39,819 | 712,856 | 94% | 0.8ms |
| Broad / exploratory | 10 | 39,828 | 816,129 | 95% | 0.9ms |
| **Total** | **110** | **360,071** | **3,341,190** | **89%** | **0.6ms** |

Total benchmark time: **62ms** (0.6ms avg per query).

</details>

---

## Available MCP Tools (27)

### Indexing

| Tool | Description |
|------|-------------|
| `index_codebase(path)` | Index/re-index a codebase (auto-detects git org/repo) |
| `index_git_commit(path, ref)` | Index at a specific commit/tag/branch |
| `index_pr(path, pr_number)` | Index both sides of a PR for review |
| `index_github_content(owner, repo, branch, files)` | Cache remote GitHub content |

### Search & Context

| Tool | Description |
|------|-------------|
| `get_context(query, token_budget?, project?)` | **Main tool.** Relevant code within a token budget. Auto-budgets, conversation-aware, auto-compacts at 256k. |
| `search_code(query, project?)` | Hybrid BM25 + semantic search with frecency boost |
| `search_structure(symbol, project?)` | Find definitions by name via AST index |
| `resolve_symbol(symbol, project?)` | Cross-repo symbol resolution |

### Code Analysis

| Tool | Description |
|------|-------------|
| `get_diff_context(file, line_start?, line_end?)` | Changed code + callers/dependents |
| `what_breaks_if_i_change(file, function?)` | Impact analysis: callers, tests, risk level |
| `get_tests_for(function, file?, project?)` | Find tests via import tracing + naming conventions |
| `trace_dependencies(file, project?)` | Imports and reverse dependencies |
| `find_dead_code(project?)` | Functions/classes with zero callers |
| `detect_stale_index(project?)` | Check if index is outdated vs working tree |

### Project Management

| Tool | Description |
|------|-------------|
| `project_summary(project?)` | Compressed project overview |
| `file_summary(path, project?)` | Per-file breakdown: functions, classes, imports |
| `list_projects()` | All indexed projects with git info |
| `remove_project(project)` | Remove a project and all its data |
| `export_index(project)` | Export index as JSON |
| `import_index(json_bundle)` | Import index from JSON |

### Session & Memory

| Tool | Description |
|------|-------------|
| `context_pressure()` | Session token usage, pressure %, status |
| `compact_context(reset?)` | Compact sent context to signatures |
| `store_memory(key, content, category?, project?)` | Persist knowledge across sessions |
| `recall_memory(query, category?, project?, limit?)` | FTS search of stored memories |
| `list_memories(category?, project?)` | List all memories |
| `delete_memory(memory_id?, key?, category?, project?)` | Delete memories |
| `tool_analytics(hours?)` | Call counts, latency, usage patterns |

> All search/query tools accept an optional `project` parameter to scope results. Omit it to search across all indexed projects.

---

## CLI Reference

```
arrow <command> [options]
```

<details>
<summary><b>All commands</b></summary>

| Command | Description |
|---------|-------------|
| `serve` | Start the MCP server (stdio or HTTP) |
| `index` | Index a codebase (auto-detects org/repo from git) |
| `search` | Search the indexed codebase |
| `context` | Get relevant code within a token budget |
| `status` | Show index status and stats |
| `repos` | List all indexed projects |
| `snapshot` | Index at a specific git commit/tag/branch |
| `pr` | Index both sides of a pull request |
| `symbols` | Search for symbols (functions, classes, etc.) |
| `diff-context` | Show changed code + callers/dependents |
| `impact` | What breaks if you change a file/function |
| `tests-for` | Find tests for a function |
| `remove` | Remove a project from the index |
| `stale` | Detect stale/outdated indexes |
| `deadcode` | Find unreferenced functions/classes |
| `export` | Export a project index as JSON |
| `import` | Import a project index from JSON |
| `analytics` | Show MCP tool usage statistics |
| `pressure` | Show context window pressure |
| `compact` | Compact sent context to signatures |
| `remember` | Store a long-term memory |
| `recall` | Search long-term memories |
| `forget` | Delete a memory |
| `memories` | List all stored memories |

</details>

### Common Examples

```bash
# Index multiple repos
arrow index /path/to/project
arrow index /path/to/another/project

# Search across all projects or scoped
arrow search "database connection"
arrow search "authentication" --project myorg/myrepo

# Get context-window-friendly output
arrow context "authentication flow" --budget 4000

# Git history snapshots
arrow snapshot /path/to/project v1.2.0
arrow search "auth" --project "org/repo@v1.2.0"

# PR review — index both sides
arrow pr /path/to/project 123
arrow search "auth" --project "org/repo@pr:PR-123"

# Impact analysis
arrow impact src/auth.py --function authenticate

# Long-term memory
arrow remember "auth-pattern" "Uses JWT with refresh rotation" --category architecture
arrow recall "JWT tokens"
```

---

## Docker

```bash
# Build and run
docker build -t arrow .
docker run -v /path/to/project:/workspace:ro -p 8080:8080 arrow

# Register with Claude Code (HTTP transport)
claude mcp add --transport http arrow http://localhost:8080/mcp
```

Or with docker-compose:

```bash
WORKSPACE_PATH=/path/to/project docker compose up -d
```

<details>
<summary>Multi-arch build</summary>

```bash
docker buildx build --platform linux/amd64,linux/arm64 -t arrow:latest .
```

</details>

---

## How It Works

### Architecture

```
Claude Code ──(JSON-RPC/stdio)──> Arrow MCP Server
                                    |
                    +---------------+---------------+
                    |               |               |
               Indexer         Searcher        Analyzer
            (tree-sitter)    (FTS5+usearch)   (impact/deps)
                    |               |               |
                    +-------+-------+-------+-------+
                            |               |
                       Storage          Memory
                    (SQLite WAL)    (FTS5 k/v store)
```

### Multi-Repo & Git

Arrow tracks all repos in one shared database, organized by `org/repo` (auto-detected from git remote URLs).

- **Auto-detection** — reads `git remote get-url origin` to determine identity
- **Branch + commit tracking** — stores current branch and HEAD commit per project
- **Per-project file watchers** — each project gets its own watchdog instance
- **Concurrent safety** — SQLite WAL mode + per-project write locks

### Tech Stack

| Component | Library | Why |
|-----------|---------|-----|
| MCP SDK | `mcp` (Python) | Official SDK |
| AST parsing | `tree-sitter` | 64+ languages, incremental |
| Vector search | `usearch` | 20x faster than FAISS |
| Embeddings | `onnxruntime` + Jina | CPU-only, no GPU needed |
| Full-text search | SQLite FTS5 | BM25 scoring, zero deps |
| Content hashing | `xxhash` (xxHash3-128) | 31 GB/s throughput |
| Token counting | `tiktoken` | Exact counts for Claude |
| Compression | `zstandard` (zstd) | 3.4x faster than zlib |
| File watching | `watchdog` | Native OS APIs |
| Database | SQLite (WAL mode) | 800+ writes/sec |

---

## Development

### Running Tests

```bash
pip install -e ".[test]"
pytest tests/ -v
```

197 tests across 20 test files covering indexing, search, storage, server tools, git utils, memory, compaction, analytics, and more.

### Running Benchmarks

```bash
python benchmarks/bench.py /path/to/codebase
```

---

## Roadmap

- **Chunk-level summaries** — LLM-generated one-line summaries per function/class
- **Custom chunk boundaries** — `// @arrow-chunk` comments for domain-specific splitting
- **Monorepo workspace support** — `arrow.json` config for sub-projects
- **Type-aware search** — search by type annotations and signatures
- **Embedding model hot-swap** — swap models without re-indexing
- **Persistent query cache** — sub-microsecond repeated queries
- **Language server integration** — LSP hover/definition data for cross-file resolution

---

## License

MIT
