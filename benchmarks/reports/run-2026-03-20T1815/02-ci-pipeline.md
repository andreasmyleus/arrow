# Query 2: "What does the CI pipeline do?"

Category: Targeted lookup
Arrow tool(s) under test: get_context

## Round 1 — Traditional
**Timestamps:** start=1774009847222 end=1774009854351
**Wall time:** 7129ms
**Tool calls:** 4 (Glob x3, Read x1)
**Tokens from content:** ~204
**Answer quality:** 5
**Precision:** 100%

### Answer
The CI pipeline is defined in `.github/workflows/ci.yml` and triggers on pushes and PRs to `main`. It has two jobs:

1. **test** — Runs the test suite across a matrix of 2 OSes (ubuntu-latest, macos-latest) x 2 Python versions (3.11, 3.12) = 4 combinations. Steps: checkout, setup Python, install deps with `pip install -e ".[test]"`, run `pytest tests/ -v`.

2. **docker** — Builds the Docker image (`docker build -t arrow-mcp:test .`) and runs a smoke test that imports `Storage` and `Indexer` inside the container to verify the image works.

### Files read
- .github/workflows/ci.yml (51 lines)

## Round 2 — Arrow
**Timestamps:** start=1774009857010 end=1774009866364
**Wall time:** 9354ms
**Tool calls:** 1 (get_context x1)
**Tokens from content:** 0 (Arrow returned no results)
**Chunks returned:** 0
**Answer quality:** 1
**Precision:** 0%

### Answer
Arrow returned no results. The CI pipeline configuration file (`.github/workflows/ci.yml`) is a YAML file that would not be chunked by tree-sitter AST parsing, so it is likely not in the index at all. No answer could be produced from Arrow alone.

### Observations
Traditional tools won decisively. Arrow's `get_context` returned zero results because:

1. **YAML files are not indexed** — Arrow uses tree-sitter for AST-based chunking, which targets source code files (Python, JS, etc.). CI workflow YAML files are configuration, not code, and are excluded from the index entirely.
2. **Structural limitation** — This query targets non-code project infrastructure. Arrow is designed for code search, not configuration file discovery.

This is a category of query where traditional file-finding tools (Glob + Read) are fundamentally better suited. The question requires finding and reading a config file, not searching code semantics. Traditional tools found the answer in one Glob + one Read with perfect precision. Arrow could not answer at all.

**Winner: Traditional (by default — Arrow had no coverage of the relevant file type)**
