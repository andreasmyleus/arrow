# Query 5: Configuration Management

**Query:** "How is configuration managed — env vars, defaults, CLI flags?"
**Category:** Cross-cutting
**Arrow tool(s) under test:** `get_context`
**Date:** 2026-03-20

---

## Round 1 — Traditional (Glob + Grep + Read)

| Metric | Value |
|---|---|
| Wall time | 34,770 ms |
| Tool calls | 10 (3 Glob + 3 Read + 3 Grep + 1 Read) |
| Lines read | ~1,050 |
| Tokens (est.) | ~4,200 |
| Quality | 5/5 |
| Precision | 95% |

### Answer

Arrow configuration is managed through a three-layer system with clear precedence:

1. **TOML config file** (`config.py`):
   - Search order: explicit path arg > `./arrow.toml` (project-local) > `~/.arrow/config.toml` (global)
   - Dataclass-based with sensible defaults: `SearchConfig` (token_budget=0, non_code_penalty=0.3, frecency_boost=True, max_results=50), `IndexConfig` (auto_index_cwd=True, watch_files=True, max_file_size_kb=512), plus top-level `db_path` and `vector_path`
   - Singleton pattern via `get_config()` — loaded lazily, cached globally

2. **Environment variables** (override config file):
   - `ARROW_DB_PATH` — database location (default: `~/.arrow/index.db`)
   - `ARROW_VECTOR_PATH` — vector index location (default: `~/.arrow/vectors.usearch`)
   - Used in `server.py` (`_get_storage`, `_get_vector_store`, `_auto_warm_cwd`) and `cli.py` (`_get_components`)
   - Dockerfile sets both to `/data/` paths for container deployment

3. **CLI flags** (override everything):
   - `arrow --db-path <path> --vec-path <path>` — global flags on the CLI entry point
   - `arrow serve --transport stdio|http --port 8080 --log-level DEBUG|INFO|WARNING|ERROR`
   - `arrow index <path> --force --log-level ...`
   - `arrow search <query> --limit --project`
   - `arrow context <query> --budget --json --project`
   - CLI flags that set paths propagate by writing to `os.environ` before imports

**Precedence:** CLI flag > env var > config file > hardcoded default.

The `server.py` `main()` also accepts `--db-path`, `--transport`, `--port`, `--log-level` via argparse, separate from the CLI entry point in `cli.py`.

### Files examined
- `src/arrow/config.py` — full file (103 lines)
- `src/arrow/cli.py` — full file (860 lines)
- `src/arrow/server.py` — partial reads (~80 lines) + grep
- `Dockerfile` — full file (44 lines)
- `pyproject.toml` — grep for entry point

---

## Round 2 — Arrow (`get_context`)

| Metric | Value |
|---|---|
| Wall time | 11,788 ms |
| Tool calls | 1 |
| Chunks returned | 0 |
| Tokens returned | 0 |
| Quality | 0/5 |
| Precision | 0% |

### Result

`get_context` returned **no results** for this query. The response was:

> "No results for: How is configuration managed — env vars, defaults, CLI flags?"

The query is conceptual and cross-cutting — configuration logic spans `config.py`, `cli.py`, `server.py`, and `Dockerfile`. The natural-language phrasing with long dashes and multiple concepts ("env vars, defaults, CLI flags") likely failed to match any indexed chunk with sufficient relevance score. The relevance-first cutoff filtered out everything.

---

## Comparison

| Metric | Traditional | Arrow | Delta |
|---|---|---|---|
| Wall time (ms) | 34,770 | 11,788 | Arrow 2.9x faster |
| Tool calls | 10 | 1 | Arrow 10x fewer |
| Tokens consumed | ~4,200 | ~0 | N/A (Arrow returned nothing) |
| Quality (1-5) | 5 | 0 | Traditional wins |
| Precision (%) | 95% | 0% | Traditional wins |

### Verdict

**Traditional wins decisively.** Arrow returned zero results for this cross-cutting conceptual query. The question asks about a design concern that spans multiple files and involves understanding how env vars, TOML config, CLI argparse, and Dockerfile defaults interact. This is exactly the type of architectural/cross-cutting question where keyword-based retrieval struggles — there is no single chunk titled "configuration management" and the query terms ("env vars", "defaults", "CLI flags") are spread across different files.

The traditional approach succeeded by starting with targeted file discovery (Glob for config.py, cli.py, Dockerfile) and then using Grep to trace `os.environ`, `getenv`, and `get_config` across the entire source tree, assembling the full picture incrementally.

### Suggestions for Arrow

- Cross-cutting conceptual queries would benefit from a query reformulation step — splitting "env vars, defaults, CLI flags" into separate sub-searches
- Files like `config.py` should rank highly for any query mentioning "configuration" even without exact keyword overlap
- Consider indexing file-level summaries that capture the purpose/role of each module, not just individual chunks
