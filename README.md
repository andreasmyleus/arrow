<div align="center">

# Arrow

**A local MCP server that indexes your codebase into semantic chunks and serves exactly the code your AI agent needs.**

*Cursor-style intelligent code retrieval — open source, local, and works with any MCP-compatible agent.*

[![Python 3.10+](https://img.shields.io/badge/python-3.10%2B-blue.svg)](https://www.python.org/downloads/)
[![License: MIT](https://img.shields.io/badge/License-MIT-green.svg)](LICENSE)
[![Tests](https://img.shields.io/badge/tests-195%20passing-brightgreen.svg)](#development)
[![MCP Tools](https://img.shields.io/badge/MCP%20tools-28-purple.svg)](#mcp-tools-28)

```
15x fewer tokens   |   sub-1ms queries   |   49 languages   |   28 MCP tools
```

</div>

---

## Why Arrow?

AI coding agents read entire files to gather context. On a moderately sized codebase, a single question can consume **1M+ tokens** and take **13+ seconds**.

Arrow pre-indexes your code into semantic chunks (functions, classes, methods) using tree-sitter, then serves exactly the relevant pieces in **1-4ms** using **96% fewer tokens**.

```
Before:  "Review Docker setup"  →  119,401 tokens  (read all 59 files)
After:   "Review Docker setup"  →    8,611 tokens  (Arrow, 50 relevant chunks)
```

---

## Quick Start

### 1. Install

```bash
git clone <repo-url>
cd arrow
python -m venv .venv && source .venv/bin/activate
pip install -e .
```

### 2. Register with your agent

**Claude Code (stdio):**
```bash
claude mcp add --transport stdio arrow -- /path/to/arrow/.venv/bin/python -m arrow serve
```

**Docker (HTTP):**
```bash
docker build -t arrow .
docker run -v /path/to/project:/workspace:ro -p 8080:8080 arrow
claude mcp add --transport http arrow http://localhost:8080/mcp
```

**Other MCP agents:** Point your agent's MCP config at the same stdio command or HTTP endpoint.

### 3. Index your project

```bash
arrow index /path/to/project
```

Or ask your agent: *"Index my codebase at /path/to/project"*

### 4. Add to your agent instructions (recommended)

Add to your `CLAUDE.md`, system prompt, or agent config:

```markdown
## Code Context

This project has an MCP server `arrow` for fast code search.
Use these MCP tools BEFORE reading files manually:
- `get_context(query)` — get relevant code (auto-budgets, conversation-aware)
- `search_code(query)` — hybrid search with frecency boost
- `search_structure(symbol)` — find definitions by name
- `what_breaks_if_i_change(file, function)` — impact analysis
- `get_tests_for(function)` — find tests for a function
- `index_github_repo(owner, repo)` — clone + index a remote repo
```

---

## Features

### Search & Retrieval
- **AST-based chunking** — tree-sitter parses 49 languages into semantic units (functions, classes, methods)
- **Hybrid search** — BM25 full-text + semantic vector search with reciprocal rank fusion
- **Smart token budgeting** — auto-estimates optimal budget from query complexity
- **Frecency boost** — recently/frequently accessed files rank higher
- **Regex search** — exact pattern matching against indexed chunks

### Code Analysis
- **Impact analysis** — what breaks if you change a file/function (callers, tests, risk level)
- **Semantic diff context** — changed code + all callers/dependents of modified functions
- **Cross-repo symbol resolution** — find definitions across all indexed repos
- **Test mapping** — maps functions to tests via import tracing + naming conventions
- **Dead code detection** — finds functions with zero callers

### Multi-Repo & Git
- **Multi-repo database** — all repos in one shared SQLite DB, organized by `org/repo`
- **Git-aware** — tracks branch + HEAD, auto-updates on commits
- **History snapshots** — index at any commit, tag, or branch
- **PR review** — index both sides of a PR for comparison
- **GitHub cloning** — one-command clone + index via `gh` CLI
- **Watchdog re-indexing** — monitors file changes, re-indexes in background

### Session & Memory
- **Conversation-aware** — tracks which chunks have been sent, never re-sends duplicates
- **Long-term memory** — persistent key-value store with FTS, survives across sessions
- **Index export/import** — share indexes across machines or CI
- **Concurrent-safe** — SQLite WAL + per-project write locks

---

## Performance

<details>
<summary><b>Micro-benchmarks</b></summary>

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

</details>

### Arrow vs Traditional (Read Entire Files)

110 queries across 10 complexity tiers on Arrow's own codebase. Arrow uses `get_context` with a 4000-token budget. Traditional simulates reading entire files.

```
Token efficiency:  15.2x (Arrow uses 1/15th the tokens)
Overall savings:   93.4%
Arrow p50 latency: 0.95ms
Arrow p99 latency: 1.99ms
```

<details>
<summary><b>Full breakdown by query type</b></summary>

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

</details>

---

## MCP Tools (28)

### Search & Context

| Tool | Description |
|------|-------------|
| `get_context(query, token_budget?, project?)` | **Primary tool.** Relevant code within a token budget. Auto-budgets, conversation-aware. |
| `search_code(query, project?)` | Hybrid BM25 + semantic search with frecency boost |
| `search_regex(pattern, limit?, project?)` | Regex search against indexed chunks |
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

### Indexing

| Tool | Description |
|------|-------------|
| `index_codebase(path)` | Index/re-index a codebase (auto-detects git org/repo) |
| `index_git_commit(path, ref)` | Index at a specific commit/tag/branch |
| `index_pr(path, pr_number)` | Index both sides of a PR for review |
| `index_github_repo(owner, repo, branch?, sparse_paths?)` | Clone + index a GitHub repo via `gh` CLI |
| `index_github_content(owner, repo, branch, files)` | Cache remote GitHub content |

### Project & Session

| Tool | Description |
|------|-------------|
| `project_summary(project?)` | Compressed project overview |
| `file_summary(path, project?)` | Per-file breakdown: functions, classes, imports |
| `list_projects()` | All indexed projects with git info |
| `remove_project(project)` | Remove a project and all its data |
| `export_index(project)` | Export index as JSON |
| `import_index(json_bundle)` | Import index from JSON |
| `context_pressure()` | Session token usage and pressure status |
| `store_memory(key, content, category?, project?)` | Persist knowledge across sessions |
| `recall_memory(query, category?, project?, limit?)` | FTS search of stored memories |
| `list_memories(category?, project?)` | List all memories |
| `delete_memory(memory_id?, key?, category?, project?)` | Delete memories |
| `tool_analytics(hours?)` | Call counts, latency, usage patterns |

> All tools accept an optional `project` parameter to scope results. Omit it to search across all indexed projects.

---

## Docker

```bash
# Build and run
docker build -t arrow .
docker run -v /path/to/project:/workspace:ro -p 8080:8080 arrow

# Register with Claude Code
claude mcp add --transport http arrow http://localhost:8080/mcp
```

With docker-compose:

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

## CLI

```
arrow <command> [options]
```

<details>
<summary><b>All commands</b></summary>

| Command | Description |
|---------|-------------|
| `serve` | Start the MCP server (stdio or HTTP) |
| `index` | Index a codebase |
| `search` | Search indexed code |
| `context` | Get relevant code within a token budget |
| `status` | Show index stats |
| `repos` | List indexed projects |
| `snapshot` | Index at a specific git ref |
| `pr` | Index both sides of a PR |
| `symbols` | Search for symbols |
| `diff-context` | Changed code + callers/dependents |
| `impact` | What breaks if you change a file/function |
| `tests-for` | Find tests for a function |
| `remove` | Remove a project |
| `stale` | Detect stale indexes |
| `deadcode` | Find unreferenced code |
| `export` | Export index as JSON |
| `import` | Import index from JSON |
| `analytics` | Tool usage statistics |
| `pressure` | Context window pressure |
| `remember` | Store a memory |
| `recall` | Search memories |
| `forget` | Delete a memory |
| `memories` | List all memories |

</details>

### Examples

```bash
# Index and search
arrow index /path/to/project
arrow search "database connection"
arrow context "authentication flow" --budget 4000

# Git snapshots and PR review
arrow snapshot /path/to/project v1.2.0
arrow pr /path/to/project 123

# Analysis
arrow impact src/auth.py --function authenticate
arrow deadcode
```

---

## Architecture

```
AI Agent ──(JSON-RPC/stdio|HTTP)──> Arrow MCP Server
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

<details>
<summary><b>Tech stack</b></summary>

| Component | Library | Why |
|-----------|---------|-----|
| MCP SDK | `mcp` (Python) | Official SDK |
| AST parsing | `tree-sitter` | 49 languages, incremental |
| Vector search | `usearch` | 20x faster than FAISS |
| Embeddings | `onnxruntime` + Jina | CPU-only, no GPU needed |
| Full-text search | SQLite FTS5 | BM25 scoring, zero deps |
| Content hashing | `xxhash` (xxHash3-128) | 31 GB/s throughput |
| Token counting | `tiktoken` | Exact token counts |
| Compression | `zstandard` (zstd) | 3.4x faster than zlib |
| File watching | `watchdog` | Native OS APIs |
| Database | SQLite (WAL mode) | 800+ writes/sec |

</details>

---

## Development

```bash
pip install -e ".[test]"
pytest tests/ -v           # 195 tests across 22 files
python benchmarks/bench.py # micro-benchmarks
```

---

## Roadmap

- **Chunk-level summaries** — LLM-generated one-line summaries per function/class
- **Custom chunk boundaries** — `// @arrow-chunk` comments for domain-specific splitting
- **Monorepo workspace support** — `arrow.json` config for sub-projects
- **Type-aware search** — search by type annotations and signatures
- **Language server integration** — LSP hover/definition data for cross-file resolution

---

## License

MIT
