<div align="center">

# Arrow

**A local MCP server that gives Claude Code a brain for your codebase.**

*The same intelligent code retrieval that powers Cursor IDE — but open source, local, and built for Claude Code.*

[![Python 3.10+](https://img.shields.io/badge/python-3.10%2B-blue.svg)](https://www.python.org/downloads/)
[![License: MIT](https://img.shields.io/badge/License-MIT-green.svg)](LICENSE)
[![Tests](https://img.shields.io/badge/tests-197%20passing-brightgreen.svg)](#running-tests)
[![MCP Tools](https://img.shields.io/badge/MCP%20tools-28-purple.svg)](#available-mcp-tools-28)

```
15x fewer tokens   |   sub-1ms queries   |   64+ languages   |   28 MCP tools
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
- `index_github_repo(owner, repo)` — clone + index a remote GitHub repo (uses `gh` CLI)
```

Add a remote repos section to your CLAUDE.md if you work across GitHub repos:

```markdown
## Remote Repos

When you need code from a GitHub repo:
1. Always check the index first — use `search_code(query, project="owner/repo")`
2. If not indexed, use `index_github_repo(owner, repo)` to clone and index in one step
3. Never manually fetch + pass files — `index_github_repo` handles cloning, caching, and incremental updates
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
| **GitHub repo cloning** | One-command clone + index of any GitHub repo via `gh` CLI |
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

| Operation | Speed | Details |
|-----------|-------|---------|
| Hashing | 3,300 MB/s | xxHash3-128, 10K ops |
| Token counting | 2,081 ops/s | tiktoken cl100k_base |
| Indexing | 71 files/s | tree-sitter + tokenization |
| Incremental check | 70ms | 14 files, hash check only |
| Search (p50) | 0.45ms | FTS5 BM25, 10 results |
| Search (p99) | 0.60ms | Consistent low latency |
| get_context | 0.8-0.95ms | search + rank + token trim |
| Budget fill rate | 82-99% | Fills budget efficiently |

### Arrow vs Traditional (Grep + Read)

110 queries across 10 complexity tiers. Arrow uses `get_context` with a 4000-token budget. Traditional simulates Glob + Grep + Read (entire file reads). Benchmarked on Arrow's own codebase (14 files, 219 chunks).

```
Token efficiency:  15.2x (Arrow uses 1/15th the tokens)
Overall savings:   93.4%
Median savings:    91.5%
Arrow p50 latency: 0.95ms
Arrow p99 latency: 1.99ms
```

| Complexity Tier | Queries | Arrow Tokens | Traditional Tokens | Savings |
|-----------------|---------|-------------|-------------------|---------|
| Symbol lookup | 15 | 46,413 | 507,639 | **91%** |
| Method lookup | 15 | 41,409 | 362,634 | **89%** |
| Single concept | 10 | 21,992 | 242,239 | **91%** |
| Two concepts | 10 | 37,889 | 338,415 | **89%** |
| How-does-X-work | 10 | 35,906 | 427,370 | **92%** |
| Cross-file tracing | 10 | 31,799 | 370,599 | **91%** |
| Debugging | 10 | 35,697 | 412,895 | **91%** |
| Implementation planning | 10 | 39,901 | 458,582 | **91%** |
| Architecture review | 10 | 39,906 | 1,175,121 | **97%** |
| Broad / exploratory | 10 | 39,673 | 1,334,045 | **97%** |
| **Total** | **110** | **370,585** | **5,629,539** | **93.4%** |

Total benchmark time: **92ms** (0.8ms avg per query).

<details>
<summary><b>Index statistics</b></summary>

```
Files:       14
Chunks:      219
Symbols:     216
Imports:     261
Chunks/file: 15.6 avg
Tokens:      47,730 total, 218 avg, 13-2085 range
Languages:   python(14)
Chunk kinds: function(203), class(14), module(2)
```

</details>

---

## Available MCP Tools (28)

### Indexing

| Tool | Description |
|------|-------------|
| `index_codebase(path)` | Index/re-index a codebase (auto-detects git org/repo) |
| `index_git_commit(path, ref)` | Index at a specific commit/tag/branch |
| `index_pr(path, pr_number)` | Index both sides of a PR for review |
| `index_github_content(owner, repo, branch, files)` | Cache remote GitHub content |
| `index_github_repo(owner, repo, branch?, sparse_paths?)` | Clone + index a GitHub repo via `gh` CLI |

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
| `search_regex(pattern, limit?, project?)` | Regex search against indexed code |
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
