# Query 10: "Find all environment variable reads"

Category: Regex
Arrow tool(s) under test: search_regex

## Round 1 — Traditional
**Timestamps:** start=1774009889304 end=1774009902966
**Wall time:** 13662ms
**Tool calls:** 3 (Grep x3)
**Tokens from content:** ~280
**Answer quality:** 5
**Precision:** 95%

### Answer
Environment variable reads span production source, config/infra, demo scripts, and tests:

**Production source code:**
- **src/arrow/cli.py** (lines 31-32, 48, 50): `os.environ.get("ARROW_DB_PATH")`, `os.environ.get("ARROW_VECTOR_PATH")`, and direct `os.environ[...]` sets
- **src/arrow/server.py** (lines 65-66, 76-77, 138-139, 1085-1089, 1154): Multiple `os.environ.get` calls for `ARROW_DB_PATH` and `ARROW_VECTOR_PATH` across different init paths

**Config/infrastructure:**
- **Dockerfile** (lines 33-34): `ENV ARROW_DB_PATH=/data/index.db`, `ENV ARROW_VECTOR_PATH=/data/vectors.usearch`
- **docker-compose.yml** (lines 10-11): Sets same env vars
- **arrow.toml** (line 47): Documents env var precedence

**Demo scripts:**
- **demo_comparison.py** (line 185): Sets `ARROW_VECTOR_PATH`
- **demo_part2.py** (lines 14-15, 296-297): Sets and reads both env vars

**Tests (7 files):**
- conftest.py, test_auto_warm.py, test_server.py, test_tool_chain.py, test_diff_context.py, test_search_regex.py, test_doc_search.py — all set/pop `ARROW_DB_PATH` and `ARROW_VECTOR_PATH` in fixtures
- test_precision.py, test_search_regex.py — contain synthetic test data with `os.environ.get` patterns

### Files read
Content from 15 files via Grep (no full file reads needed)

## Round 2 — Arrow
**Timestamps:** start=1774009911907 end=1774009920316
**Wall time:** 8409ms
**Tool calls:** 1 (search_regex x1 — denied)
**Tokens from content:** 0
**Chunks returned:** 0
**Answer quality:** 1
**Precision:** 0%

### Answer
Arrow's `search_regex` tool was denied permission by the runtime environment. No results were returned and no answer could be produced.

### Observations
The Arrow round could not be evaluated because the `search_regex` MCP tool call was denied at runtime (permission error). This makes a fair comparison impossible for this query.

**Traditional round performance:** Grep handled this query efficiently. The multi-pattern regex `os\.environ|getenv|ARROW_` matched all relevant lines across the entire codebase in a single pass per file glob. Three Grep calls (one for `*.py`, one for config files, one for Dockerfile) provided complete coverage. Precision docked to 95% because the `ARROW_` pattern also matched non-env-var references in benchmark report markdown files and test assertion strings, though these were easy to mentally filter.

This is an ideal query type for regex search — a well-defined pattern with no semantic ambiguity. Both traditional Grep and Arrow's `search_regex` should perform similarly since both do literal regex matching against file contents.

**Winner: Traditional (Arrow could not run due to permission denial — no valid comparison)**
