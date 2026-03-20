# Query 10: Find all environment variable reads

**Category:** search_regex — Exact pattern matching
**Date:** 2026-03-20
**Codebase:** /Users/andreas/arrow

## Query

"Find all environment variable reads" — regex pattern `os\.environ|getenv|ARROW_`

## Round 1 — Traditional (Glob + Grep + Read)

| Metric | Value |
|--------|-------|
| Start | 1774007823036 |
| End | 1774007829881 |
| Duration | 6845 ms |
| Tool calls | 1 (Grep) |
| Results | 64 matching lines across 16 files |
| Quality | 5/5 |
| Precision | 95% |

### Findings

Source code env var reads (production code):
- **src/arrow/cli.py**: `os.environ.get("ARROW_DB_PATH")`, `os.environ.get("ARROW_VECTOR_PATH")`, direct `os.environ[...]` sets (lines 31-50)
- **src/arrow/server.py**: `os.environ.get("ARROW_DB_PATH")`, `os.environ.get("ARROW_VECTOR_PATH")` in multiple init paths (lines 65-66, 76-77, 138-139, 1039-1043, 1108)

Config/deployment env var references:
- **arrow.toml**: Documents `ARROW_DB_PATH` / `ARROW_VECTOR_PATH` precedence (line 47)
- **Dockerfile**: `ENV ARROW_DB_PATH=/data/index.db`, `ENV ARROW_VECTOR_PATH=/data/vectors.usearch` (lines 33-34)
- **docker-compose.yml**: Sets both env vars (lines 10-11)

Test fixtures (env var setup/teardown):
- **tests/conftest.py**, **tests/test_auto_warm.py**, **tests/test_server.py**, **tests/test_tool_chain.py**, **tests/test_search_regex.py**, **tests/test_doc_search.py**, **tests/test_diff_context.py**: All set/pop `ARROW_DB_PATH` and `ARROW_VECTOR_PATH`
- **tests/test_precision.py**, **tests/test_search_regex.py**: Contain synthetic test data with `os.environ.get` patterns

Other:
- **demo_part2.py**, **demo_comparison.py**: Set env vars for demo scripts

### Notes

Single Grep call was sufficient — the regex pattern `os\.environ|getenv|ARROW_` captured all relevant matches in one pass. Precision docked slightly for matching `ARROW_` in non-env-var contexts (e.g., benchmark spec docs, test assertion strings).

## Round 2 — Arrow (search_regex)

| Metric | Value |
|--------|-------|
| Start | 1774007832915 |
| End | 1774007839430 |
| Duration | 6515 ms |
| Tool calls | 1 (mcp__arrow__search_regex — DENIED) |
| Results | 0 (permission denied) |
| Quality | N/A |
| Precision | N/A |

### Notes

The `mcp__arrow__search_regex` tool call was denied by the permission system. Round 2 could not be completed. No results were returned.

## Comparison

| Metric | Traditional | Arrow |
|--------|------------|-------|
| Duration (ms) | 6845 | N/A (blocked) |
| Tool calls | 1 | 1 (denied) |
| Files found | 16 | 0 |
| Match lines | 64 | 0 |
| Quality (1-5) | 5 | N/A |
| Precision (%) | 95% | N/A |

## Verdict

**Round 2 blocked by permission denial.** Traditional tools completed successfully with a single Grep call finding 64 matches across 16 files. The regex alternation pattern worked well for this multi-pattern search. No comparison possible due to Arrow tool being denied.

**Winner:** Traditional (by default — Arrow was blocked)
