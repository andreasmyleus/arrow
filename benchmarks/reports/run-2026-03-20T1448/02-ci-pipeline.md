# Query 02: "What does the CI pipeline do?"

**Category:** Targeted
**Arrow tool(s) under test:** `get_context`
**Date:** 2026-03-20

---

## Round 1 — Traditional (Glob + Grep + Read)

**Start:** 1774010928909
**End:** 1774010948312
**Duration:** 19,403 ms

### Tool calls: 7
1. Glob `**/.github/workflows/*.yml` — found `ci.yml`
2. Glob `**/.github/workflows/*.yaml` — no results
3. Glob `**/Makefile` — no results
4. Glob `**/.gitlab-ci.yml` — no results
5. Grep `ci|pipeline|workflow` in `*.toml` — found `pyproject.toml`
6. Read `.github/workflows/ci.yml` (51 lines)
7. Grep test dependencies in `pyproject.toml`

### Estimated tokens
- `ci.yml`: 51 lines * 4 = ~204 tokens
- `pyproject.toml` snippet: 8 lines * 4 = ~32 tokens
- **Total: ~236 tokens**

### Answer (Traditional)
The CI pipeline (`.github/workflows/ci.yml`) triggers on pushes and PRs to `main` and runs two jobs:

1. **test** — Matrix build across 2 OSes (ubuntu-latest, macos-latest) x 2 Python versions (3.11, 3.12). Checks out code, installs the package with test extras (`pip install -e ".[test]"`), and runs `pytest tests/ -v`.

2. **docker** — Builds the Docker image (`docker build -t arrow-mcp:test .`) and runs a smoke test that imports `Storage` and `Indexer` inside the container to verify the image works.

### Quality: 5/5
Complete answer — the entire CI file was read and understood.

### Precision: 95%
All returned content was directly relevant. The pyproject.toml grep added minor noise but confirmed test dependencies.

---

## Round 2 — Arrow (`get_context`)

**Start:** 1774010951450
**End:** 1774010961018
**Duration:** 9,568 ms

### Tool calls: 1
1. `get_context(query="What does the CI pipeline do?", project="andreasmyleus/arrow", deduplicate=false)`

### Result
**No results returned.** Arrow reported 126 indexed files and 1325 chunks but found nothing matching the query.

### Tokens returned: 0

### Answer (Arrow)
Unable to answer. `get_context` returned no results for this query.

### Quality: 1/5
Complete failure — no information provided.

### Precision: N/A
No results to evaluate.

---

## Comparison

| Metric | Traditional | Arrow |
|---|---|---|
| Duration (ms) | 19,403 | 9,568 |
| Tool calls | 7 | 1 |
| Tokens consumed | ~236 | 0 |
| Quality (1-5) | 5 | 1 |
| Precision (%) | 95% | N/A |
| Answered? | Yes | No |

## Observations

1. **Arrow failed completely on this query.** The CI pipeline is defined in `.github/workflows/ci.yml`, a YAML configuration file. Arrow likely does not index YAML files (it uses tree-sitter AST chunking designed for source code), so CI/config files are invisible to it.

2. **Traditional approach worked well** despite needing multiple glob calls to locate the workflow file. Once found, a single Read of the 51-line file provided a complete answer.

3. **This is a known limitation category:** Arrow is optimized for source code search (Python, JS, etc.), not for infrastructure/config files like GitHub Actions workflows. Queries about CI, Docker, deployment, or other non-code artifacts will inherently favor the traditional approach.

4. **Speed was faster for Arrow** (9.6s vs 19.4s), but speed is irrelevant when the answer is empty.

5. **Recommendation:** For config/infra queries, Arrow could benefit from indexing common non-code files (YAML, Dockerfiles, Makefiles) or at minimum returning a hint that `.github/workflows/` exists but is not indexed.
