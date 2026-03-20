# Query 05: Configuration Management

**Query:** "How is configuration managed — env vars, defaults, CLI flags?"
**Category:** get_context — Cross-cutting
**Arrow tool under test:** get_context

---

## Round 1 — Traditional (Glob + Grep + Read)

| Metric | Value |
|---|---|
| Wall time | 24,018 ms |
| Tool calls | 8 |
| Estimated tokens read | ~12,000 |
| Quality | 5/5 |
| Precision | 95% |

### Findings

Arrow's configuration is managed through a 3-layer system with clear precedence:

1. **TOML config file** (`config.py`):
   - Loads from `./arrow.toml` (project-local) or `~/.arrow/config.toml` (global), first found wins
   - `ArrowConfig` dataclass with nested `SearchConfig` and `IndexConfig`
   - Defaults: `token_budget=0` (unlimited), `non_code_penalty=0.3`, `frecency_boost=True`, `max_results=50`, `auto_index_cwd=True`, `watch_files=True`, `max_file_size_kb=512`
   - Singleton pattern via `get_config()` with lazy loading

2. **Environment variables** (override config file):
   - `ARROW_DB_PATH` — database location (default: `~/.arrow/index.db`)
   - `ARROW_VECTOR_PATH` — vector index location (default: `~/.arrow/vectors.usearch`)
   - Used in both `server.py` (`_get_storage`, `_get_vector_store`) and `cli.py` (`_get_components`)

3. **CLI flags** (override everything, set env vars):
   - `--db-path` / `--vec-path` — global args on main parser
   - `--transport` (stdio/http), `--port`, `--log-level` on `serve` subcommand
   - `--force` on `index`, `--budget`/`--json` on `context`, `--limit`/`--project` on search
   - CLI `cmd_serve` sets env vars from flags: `os.environ["ARROW_DB_PATH"] = args.db_path`

**Precedence:** CLI flags > env vars > TOML config > hardcoded defaults.

### Files examined
- `/Users/andreas/arrow/src/arrow/config.py` — full config system
- `/Users/andreas/arrow/src/arrow/cli.py` — all CLI flags and argparse setup
- `/Users/andreas/arrow/src/arrow/server.py` — env var consumption
- `/Users/andreas/arrow/pyproject.toml` — entry point `arrow = "arrow.cli:main"`

---

## Round 2 — Arrow (get_context)

| Metric | Value |
|---|---|
| Wall time | 11,537 ms |
| Tool calls | 1 |
| Tokens returned | 0 |
| Chunks returned | 0 |
| Quality | 0/5 |
| Precision | 0% |

### Findings

`get_context` returned **no results** for this query. The response was:

> No results for: How is configuration managed — env vars, defaults, CLI flags?

The query is cross-cutting and conceptual — it asks about a pattern that spans multiple files (`config.py`, `cli.py`, `server.py`). The natural language phrasing with em dashes and mixed terminology ("env vars", "defaults", "CLI flags") may not match well against code chunk content.

---

## Comparison

| Dimension | Traditional | Arrow |
|---|---|---|
| Wall time | 24.0s | 11.5s |
| Tool calls | 8 | 1 |
| Tokens consumed | ~12,000 | ~0 |
| Quality | 5/5 | 0/5 |
| Precision | 95% | 0% |
| Completeness | Full picture across 4 files | Nothing returned |

### Verdict

**Traditional wins decisively.** Arrow returned zero results for this cross-cutting architectural query. The traditional approach identified the complete 3-layer configuration system across `config.py`, `cli.py`, and `server.py`, including the exact precedence chain and all environment variables.

This is a significant failure case for `get_context`. Cross-cutting queries about design patterns (like "how is configuration managed") require understanding that spans multiple files and chunk types. The query's natural language style with special characters (em dash) and abbreviated terms ("env vars") likely contributed to poor relevance matching. A simpler keyword query like "ArrowConfig environ argparse" might have performed better, but the tool should handle natural-language architectural questions.
