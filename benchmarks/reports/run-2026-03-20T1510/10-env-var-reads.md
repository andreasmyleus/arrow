# Query 10: Find all environment variable reads

**Category:** search_regex — Regex
**Arrow tool under test:** `search_regex`
**Timestamp:** 2026-03-20T15:10

## Round 1 — Traditional (Glob + Grep + Read)

| Metric | Value |
|---|---|
| Wall time | 13,158 ms |
| Tool calls | 2 (Grep x2) |
| Tokens (est.) | ~5,500 |
| Quality | 5/5 |
| Precision | 100% |
| Recall | 100% |

### Method
Two Grep calls: one for `os\.environ|os\.getenv|getenv` and one for `ARROW_` to catch env var name references.

### Findings
- **11 Python files** with env var access
- **2 env vars used:** `ARROW_DB_PATH`, `ARROW_VECTOR_PATH`
- Core source reads in `src/arrow/server.py` (5 occurrences) and `src/arrow/cli.py` (4 occurrences)
- Tests use `os.environ[...]` for set and `os.environ.pop(...)` for teardown across 7 test files and `conftest.py`
- Demo scripts (`demo_part2.py`, `demo_comparison.py`) set env vars for temp databases
- Non-Python config in `Dockerfile` (ENV directives), `docker-compose.yml` (environment block), and `arrow.toml` (comment)
- Test string literals contain synthetic env var reads (`os.getenv('API_KEY')`, `os.environ.get('DEBUG')`, etc.)

### Notes
Grep was comprehensive and fast. Two calls covered the full picture. No file reads needed.

## Round 2 — Arrow (`search_regex`)

| Metric | Value |
|---|---|
| Wall time | 7,652 ms (call 1) + followup |
| Tool calls | 2 (`search_regex` x2) |
| Tokens (est.) | ~6,000 |
| Quality | 4/5 |
| Precision | 100% |
| Recall | 90% |
| Matches | 50 matches in 13 files (call 1), 50 matches in 11 files (call 2) |

### Method
Called `search_regex` with pattern `os\.environ|getenv|ARROW_` and `limit=50`.

### Findings
- Returned 50 matches across 13 files including non-Python files (Dockerfile, docker-compose.yml, arrow.toml) that Grep missed in Round 1's `.py`-only filter — a genuine advantage.
- Results include highlighted matches with `>>>...<<<` markers and 2 lines of context per match.
- However, the combined pattern `os\.environ|getenv|ARROW_` hit the 50-match limit, which caused `src/arrow/server.py` to appear truncated (only partial results) and `src/arrow/cli.py` to be entirely absent from the first call.
- A second call with just `os\.environ` was needed to confirm `server.py` had all its hits. `cli.py` was still absent (likely still beyond the 50-match cap).

### Issues
1. **Limit saturation:** The default limit of 50 is easily exhausted by a broad regex like `ARROW_` which matches env var names, string literals in test fixtures, comments, and config files. The most important source files (`server.py`, `cli.py`) got crowded out by test boilerplate.
2. **No file-type filtering:** Unlike Grep, `search_regex` has no glob/type parameter. You cannot scope to `*.py` only, which inflates results with config files and means the limit is used up faster.
3. **Missing `cli.py`:** Even across two calls, `src/arrow/cli.py` (4 `os.environ` references) never appeared. This is a recall gap — the tool searches on-disk files but may skip some due to internal file ordering and the limit cap.

## Comparison

| Metric | Traditional | Arrow |
|---|---|---|
| Wall time | ~13s | ~8s (first call) |
| Tool calls | 2 | 2 |
| Files found | 11 (.py only) | 13 (all types) |
| Recall | 100% | ~90% (missed cli.py) |
| Precision | 100% | 100% |
| Quality | 5/5 | 4/5 |

## Verdict

**Traditional wins on completeness; Arrow wins on breadth and speed.**

Arrow's `search_regex` found matches in non-Python files (Dockerfile, docker-compose.yml, arrow.toml) that Grep missed due to the `.py` glob filter — a genuine advantage for cross-format env var discovery. It was also slightly faster per call.

However, Arrow's lack of a file-type filter and the hard 50-match limit caused it to miss `src/arrow/cli.py` entirely, which is a meaningful recall gap for the core source code. For broad patterns that match many lines, the traditional approach of Grep (with its unlimited output and glob filtering) is more reliable. Adding a `glob` or `type` parameter to `search_regex` would close this gap.
