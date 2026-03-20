# Query 2: "What does the CI pipeline do?"

Category: get_context — Primary retrieval
Arrow tool(s) under test: get_context

## Round 1 — Traditional
**Timestamps:** start=1774007790115 end=1774007797830
**Wall time:** 7715ms
**Tool calls:** 6 (Glob x4, Read x1, Bash x1 for timestamp)
**Tokens from content:** ~204 (51 lines x 4 tokens/line)
**Answer quality:** 5/5
**Precision:** 100%

### Answer
The CI pipeline is defined in `.github/workflows/ci.yml` and triggers on pushes and pull requests to `main`. It has two jobs:

1. **test** — Runs the test suite across a matrix of 2 OSes (ubuntu-latest, macos-latest) and 2 Python versions (3.11, 3.12), totalling 4 combinations. Steps: checkout, setup Python, install dependencies via `pip install -e ".[test]"`, run `pytest tests/ -v`.

2. **docker** — Runs on ubuntu-latest only. Builds the Docker image (`docker build -t arrow-mcp:test .`) and runs a smoke test that imports `Storage` and `Indexer` inside the container to verify the image works.

### Files read
- /Users/andreas/arrow/.github/workflows/ci.yml (51 lines)

## Round 2 — Arrow
**Timestamps:** start=1774007801015 end=1774007810995
**Wall time:** 9980ms
**Tool calls:** 1 (get_context)
**Tokens from content:** 0
**Chunks returned:** 0
**Answer quality:** 0/5
**Precision:** 0%

### Answer
Arrow returned no results. The CI pipeline is defined in `.github/workflows/ci.yml`, which is a YAML configuration file. Arrow's index covers 63 files and 828 chunks but apparently does not index GitHub Actions workflow files (YAML files in `.github/workflows/`), so the query produced zero matches.

### Observations
**Winner: Traditional (by a wide margin)**

This query exposes a fundamental coverage gap in Arrow's index. The CI pipeline lives in a `.github/workflows/ci.yml` file, which is either excluded from indexing (e.g., via gitignore-style rules or file-type filters) or not chunked in a way that makes it searchable. Traditional tools found it immediately via a simple glob pattern search.

Key issues:
- Arrow returned zero results and zero tokens — a complete miss.
- The traditional approach was also faster (7.7s vs 10.0s) despite using more tool calls.
- For non-code configuration files like CI workflows, traditional file discovery (Glob + Read) is clearly superior when Arrow lacks index coverage.
- Arrow's CLAUDE.md does mention section-aware chunkers for YAML files, so the `.github/` directory may be excluded from indexing rather than YAML being unsupported.
