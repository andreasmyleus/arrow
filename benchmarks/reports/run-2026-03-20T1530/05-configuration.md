# Benchmark Query 5: Configuration Management

**Query:** "How is configuration managed — env vars, defaults, CLI flags?"
**Date:** 2026-03-20T15:30
**Codebase:** /Users/andreas/arrow (63 files, 828 chunks indexed)

---

## Round 1 — Traditional Tools (Glob + Grep + Read)

| Metric | Value |
|---|---|
| Start | 1774007797165 |
| End | 1774007812290 |
| Duration | 15,125 ms |
| Tool calls | 8 (2 Glob, 2 Grep, 3 Read, 1 Bash) |
| Files read | 3 (config.py, cli.py, Dockerfile) |
| Quality | 5/5 |
| Precision | 95% |

### Findings

Configuration in Arrow uses a 3-layer system with clear priority ordering:

1. **TOML config file** (`config.py`):
   - `ArrowConfig` dataclass with nested `SearchConfig` and `IndexConfig`
   - Search order: explicit path arg > `./arrow.toml` (project-local) > `~/.arrow/config.toml` (global)
   - Singleton pattern via `get_config()` (lazy-loaded once)
   - Defaults: `token_budget=0`, `non_code_penalty=0.3`, `frecency_boost=True`, `max_results=50`, `auto_index_cwd=True`, `watch_files=True`, `max_file_size_kb=512`

2. **Environment variables** (override config file):
   - `ARROW_DB_PATH` — database location (used in server.py, cli.py)
   - `ARROW_VECTOR_PATH` — vector index location (used in server.py, cli.py)
   - Priority: env var > config file `db_path`/`vector_path` > hardcoded default `~/.arrow/index.db`

3. **CLI flags** (override env vars):
   - `--db-path` and `--vec-path` global flags (set into env vars when provided)
   - `--transport` (stdio|http), `--port` (8080), `--log-level` (INFO)
   - Per-subcommand flags: `--force`, `--limit`, `--project`, `--budget`, `--json`, etc.
   - Uses `argparse` with subparsers for 20+ subcommands

4. **Dockerfile**:
   - Sets `ARROW_DB_PATH=/data/index.db` and `ARROW_VECTOR_PATH=/data/vectors.usearch`
   - Default entrypoint: `python -m arrow --transport http --port 8080`

---

## Round 2 — Arrow MCP (`get_context`)

| Metric | Value |
|---|---|
| Start | 1774007814782 |
| End | 1774007825401 |
| Duration | 10,619 ms |
| Tool calls | 1 |
| Chunks returned | 0 |
| Quality | 0/5 |
| Precision | 0% |

### Findings

Arrow returned **no results** for this query. The natural-language phrasing "How is configuration managed -- env vars, defaults, CLI flags?" failed to match any chunks above the relevance threshold. This is a conceptual/architectural query that spans multiple files (config.py, cli.py, server.py, Dockerfile) and uses terms (env vars, defaults, CLI flags) that may not appear as literal tokens in the indexed chunks.

---

## Comparison

| Metric | Traditional | Arrow |
|---|---|---|
| Duration (ms) | 15,125 | 10,619 |
| Tool calls | 8 | 1 |
| Quality (1-5) | 5 | 0 |
| Precision (%) | 95% | 0% |
| Completeness | Full picture across 4 files | No results |

### Analysis

This query represents a **total failure case for Arrow**. The query is architectural in nature -- asking "how" something is managed across the codebase rather than searching for a specific function or pattern. Arrow's relevance filtering rejected all candidate chunks, likely because:

1. The query terms ("env vars", "defaults", "CLI flags") are high-level concepts not directly present as identifiers in code
2. The answer spans 4 files (config.py, cli.py, server.py, Dockerfile), requiring cross-file synthesis
3. Arrow's relevance threshold is tuned for precision, which means broad conceptual queries get zero results rather than noisy results

Traditional tools excelled here because a targeted search strategy (Glob for known config files, Grep for `environ|getenv|ARROW_`, Read for full file context) can systematically locate all configuration-related code. The manual approach also allowed reading entire files to understand the full config loading flow.

### Verdict

**Traditional tools win decisively.** Arrow's zero-result response makes this the worst-case scenario for the MCP approach. For architectural "how does X work" queries spanning multiple files, traditional targeted search remains essential.
