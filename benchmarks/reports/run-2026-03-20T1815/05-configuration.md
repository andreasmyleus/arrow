# Query 5: "How is configuration managed — env vars, defaults, CLI flags?"

Category: Architecture / cross-cutting concern
Arrow tool(s) under test: get_context

## Round 1 — Traditional

**Timestamps:** start=1774009860166 end=1774009878313
**Wall time:** 18147ms
**Tool calls:** 8 (Read x5, Grep x1, Glob x1, Read pyproject.toml x1)
**Tokens from content:** ~5576 (1394 lines x ~4 tokens)
**Answer quality:** 5
**Precision:** 95%

### Answer

Configuration is managed through three layers with a clear precedence order:

**1. TOML config file (`config.py`)**
- Search order: explicit path argument > `./arrow.toml` (project-local) > `~/.arrow/config.toml` (global)
- Dataclass-based with sensible defaults:
  - `SearchConfig`: token_budget=0, non_code_penalty=0.3, frecency_boost=True, max_results=50
  - `IndexConfig`: auto_index_cwd=True, watch_files=True, max_file_size_kb=512
  - `ArrowConfig`: db_path=None, vector_path=None (falls through to hardcoded defaults)
- Singleton pattern via `get_config()` — loaded lazily once, reused everywhere
- `reset_config()` provided for testing

**2. Environment variables (override TOML)**
- `ARROW_DB_PATH` — overrides db_path from config; default `~/.arrow/index.db`
- `ARROW_VECTOR_PATH` — overrides vector_path from config; default `~/.arrow/vectors.usearch`
- Used in `server.py` (`_get_storage`, `_get_vector_store`, `_start_watcher`, `_auto_warm_cwd`) and `cli.py` (`_get_components`)
- Precedence: env var > config.toml value > hardcoded default

**3. CLI flags (argparse)**
- **`arrow` CLI** (`cli.py`): global `--db-path`, `--vec-path`; per-subcommand `--log-level`, `--force`, `--limit`, `--project`, `--budget`, `--json`, `--transport`, `--port`, `--kind`, `--category`, etc.
- **`arrow serve`** (`server.py` `main()`): `--transport` (stdio|http), `--port` (8080), `--db-path`, `--log-level`
- CLI flags set env vars when present: `os.environ["ARROW_DB_PATH"] = args.db_path`
- Entry point registered in `pyproject.toml`: `arrow = "arrow.cli:main"`

**4. Dockerfile defaults**
- Sets `ARROW_DB_PATH=/data/index.db` and `ARROW_VECTOR_PATH=/data/vectors.usearch` via `ENV`
- Default entrypoint: `python -m arrow --transport http --port 8080`

**Hardcoded defaults** (in both `cli.py` and `server.py`):
- `DEFAULT_DB_DIR = ~/.arrow`
- `DEFAULT_DB_PATH = ~/.arrow/index.db`
- `DEFAULT_VECTOR_PATH = ~/.arrow/vectors.usearch`
- `DEFAULT_CLONE_DIR = ~/.arrow/clones`

### Files read
- /Users/andreas/arrow/src/arrow/config.py (103 lines)
- /Users/andreas/arrow/src/arrow/cli.py (860 lines)
- /Users/andreas/arrow/src/arrow/server.py (partial: lines 1-155, 1075-1170)
- /Users/andreas/arrow/pyproject.toml (50 lines)
- /Users/andreas/arrow/Dockerfile (45 lines)

## Round 2 — Arrow

**Timestamps:** start=1774009882413 end=1774009891140
**Wall time:** 8727ms
**Tool calls:** 1 (get_context x1)
**Tokens from content:** 0 (Arrow-reported)
**Chunks returned:** 0
**Answer quality:** 1
**Precision:** 0%

### Answer

Arrow returned no results for this query. The response was:
> "No results for: How is configuration managed — env vars, defaults, CLI flags?"

The tool suggested trying broader keywords, `search_structure()`, or `file_summary()`.

### Files returned
None.

## Comparison

| Metric | Traditional | Arrow |
|---|---|---|
| Wall time | 18147ms | 8727ms |
| Tool calls | 8 | 1 |
| Tokens consumed | ~5576 | 0 |
| Chunks | N/A | 0 |
| Quality (1-5) | 5 | 1 |
| Precision | 95% | 0% |

### Analysis

Arrow failed completely on this cross-cutting architecture query, returning zero results. The question asks about a concept ("configuration management") that spans multiple files (config.py, cli.py, server.py, Dockerfile, pyproject.toml) and involves patterns (env var lookups, argparse flags, TOML loading, dataclass defaults) rather than specific symbol names. This type of broad architectural query appears to be a weakness for `get_context`, likely because the natural language query doesn't match well against code chunk embeddings or BM25 terms.

Traditional tools required 8 calls and ~18 seconds but produced a thorough, high-quality answer covering all four configuration layers. The extra time was spent reading large files (cli.py in full at 860 lines), but the Grep for `os.environ|getenv` provided an efficient way to locate all env var usage across the codebase.

**Winner: Traditional** — Arrow was unusable for this query, while traditional tools delivered a complete answer despite higher token cost.
