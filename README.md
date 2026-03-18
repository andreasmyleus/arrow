# Arrow

A local, high-performance MCP server that gives Claude Code intelligent code indexing and retrieval — the same capabilities that power Cursor IDE's context engine.

## What it does

Arrow pre-indexes your codebase using tree-sitter AST parsing, then serves relevant code chunks to Claude Code via MCP tools. Instead of reading entire files, Claude gets exactly the code it needs, using a fraction of the context window.

- **AST-based chunking** — tree-sitter parses code into semantic units (functions, classes) across 64+ languages
- **Hybrid search** — BM25 full-text (FTS5) + semantic vector search (usearch + ONNX embeddings)
- **Incremental indexing** — xxHash3 content-hashing ensures only changed files are re-indexed
- **Token-budget aware** — `get_context` returns the most relevant code within an exact token limit
- **Automatic re-indexing** — watchdog monitors file changes and re-indexes in the background
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

Tested across query types ranging from simple symbol lookups to broad architectural reviews. All queries use a 4000-token budget.

| Complexity Tier | Queries | Arrow Tokens | Traditional Tokens | Savings |
|-----------------|---------|-------------|-------------------|---------|
| Symbol lookup | 15 | 51,962 | 258,403 | 80% |
| Method lookup | 15 | 52,071 | 169,984 | 69% |
| Single concept | 10 | 25,142 | 116,988 | 79% |
| Two concepts | 10 | 39,899 | 154,541 | 74% |
| How-does-X-work | 10 | 35,837 | 226,538 | 84% |
| Cross-file tracing | 10 | 31,899 | 185,968 | 83% |
| Debugging | 10 | 35,340 | 213,882 | 84% |
| Implementation planning | 10 | 39,885 | 242,264 | 84% |
| Architecture review | 10 | 39,669 | 609,049 | 93% |
| Broad / exploratory | 10 | 39,741 | 706,405 | 94% |
| **Total** | **110** | **391,445** | **2,884,022** | **86%** |

**Average query time: 0.3ms.** Savings scale with query complexity — simple lookups save ~70-80%, while broad architectural questions save 93-94% because the traditional approach reads entire files.

## CLI

Arrow includes a full CLI for indexing, searching, and serving without Claude Code.

```
arrow <command> [options]

Commands:
  serve     Start the MCP server (stdio or HTTP)
  index     Index a codebase
  search    Search the indexed codebase
  context   Get relevant code within a token budget
  status    Show index status and stats
  symbols   Search for symbols (functions, classes, etc.)
```

### Examples

```bash
# Index a project
arrow index /path/to/project

# Check what's indexed
arrow status

# Search for code
arrow search "database connection"

# Get context-window-friendly output
arrow context "authentication flow" --budget 4000

# Find all functions named "parse"
arrow symbols parse --kind function

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

### 3. Available MCP Tools (7)

| Tool | Description |
|------|-------------|
| `index_codebase(path)` | Index/re-index a codebase (incremental via xxHash3) |
| `get_context(query, token_budget)` | **Main tool.** Get relevant code within a token budget |
| `search_code(query)` | Hybrid BM25 + semantic search |
| `search_structure(symbol)` | Find definitions by name via AST index |
| `trace_dependencies(file)` | Show imports and reverse dependencies |
| `project_summary()` | Compressed project overview |
| `file_summary(path)` | Per-file breakdown: functions, classes, imports |

### 4. Add to CLAUDE.md (recommended)

```markdown
## Code Context

This project has an MCP server `arrow` for fast code search.

Use these MCP tools BEFORE reading files manually:
- `get_context(query, token_budget)` — get relevant code for a task
- `search_code(query)` — search the codebase semantically
- `search_structure(symbol)` — find definitions
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

## Architecture

```
Claude Code ──(JSON-RPC/stdio)──> Arrow MCP Server
                                    ├── Indexer (tree-sitter + xxHash3)
                                    ├── Hybrid Searcher (FTS5 + usearch)
                                    ├── Context Assembler (token budget)
                                    ├── Structure Analyzer (symbols + imports)
                                    ├── File Watcher (watchdog)
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
