# Arrow MCP vs Traditional Claude Code — Benchmark Test Spec

## Methodology

For each use case, run two rounds on `/Users/andreas/arrow`:

**Round 1 — Traditional (no Arrow):** Answer using ONLY Glob, Grep, and Read. Do what you'd normally do. Record timestamps before/after, count tool calls, estimate tokens from file content.

**Round 2 — Arrow:** Answer the same question using ONLY `get_context(query)` (one call, no token_budget override). Record timestamps before/after, note tokens returned.

**Rules:**
- Actually answer the question both times (no skipping)
- Don't over-read or under-read to skew results
- Be honest about which approach gave a better answer
- Note cases where Arrow returns irrelevant context

---

## Use Cases

### Category 1: Targeted Lookup (Arrow disadvantage expected)

These have clearly named files — traditional Glob/Read should be efficient.

| # | Query | Why it tests Arrow's weakness |
|---|-------|-------------------------------|
| 1 | "Review the Docker setup — how is it configured, what does it build, and how would I run it?" | Files are named `Dockerfile`, `docker-compose.yml` — trivial to find |
| 2 | "What does the CI pipeline do?" | Single file: `.github/workflows/ci.yml` |
| 3 | "What's in pyproject.toml — what are the dependencies and entry points?" | Single well-known file |

### Category 2: Broad Architecture (Arrow advantage expected)

These require reading across many files to piece together an answer.

| # | Query | Why it tests Arrow's strength |
|---|-------|-------------------------------|
| 4 | "How does the hybrid search work end-to-end? Walk me through a query from `get_context()` to returned chunks." | Spans server.py → search.py → storage.py → vector_store.py |
| 5 | "Review error handling patterns across the codebase — where are errors caught, logged, or swallowed?" | Requires reading every source file |
| 6 | "How does incremental indexing work? What determines if a file needs re-indexing?" | Spans indexer.py, hasher.py, storage.py, watcher.py |
| 7 | "What's the full data model — how are chunks stored, what metadata is tracked, and how do the SQLite tables relate to each other?" | Primarily storage.py but also indexer.py, chunker.py for context |

### Category 3: Symbol/Function Lookup (Arrow should be fast)

Finding specific definitions and their usage.

| # | Query | What it tests |
|---|-------|---------------|
| 8 | "Find the `estimate_budget` function — what heuristics does it use to auto-size token budgets?" | Targeted function lookup, Arrow's `search_structure` territory |
| 9 | "How is `frecency` calculated and where is it applied in search ranking?" | Cross-file concept that touches search.py and storage.py |
| 10 | "What does `reciprocal_rank_fusion` do and how are BM25 and vector scores combined?" | Specific algorithm spread across files |

### Category 4: Impact Analysis (Arrow unique capability)

Traditional tools can't do this well without reading everything.

| # | Query | What it tests |
|---|-------|---------------|
| 11 | "If I change the `Storage` class constructor, what breaks?" | Dependency tracing — Arrow has `what_breaks_if_i_change` |
| 12 | "Find all tests that exercise the search pipeline" | Test discovery — Arrow has `get_tests_for` |
| 13 | "What files import from `storage.py` and what do they use?" | Import graph — Arrow has `trace_dependencies` |

### Category 5: Cross-Cutting Concerns (Arrow advantage expected)

Questions that touch many files but don't have obvious entry points.

| # | Query | Why traditional struggles |
|---|-------|--------------------------|
| 14 | "How is configuration managed — env vars, defaults, CLI flags?" | Touches config.py, cli.py, server.py, Dockerfile, docker-compose.yml |
| 15 | "Review the test infrastructure — fixtures, conftest setup, how tests isolate state" | Touches conftest.py + every test file's setup patterns |
| 16 | "How does Arrow handle multiple projects — indexing, searching, and isolation?" | Spans server.py, storage.py, indexer.py, search.py |

### Category 6: Needle-in-Haystack (tests precision)

The answer is in a small, specific place but you don't know where.

| # | Query | What makes it hard |
|---|-------|-------------------|
| 17 | "Where and how is the embedding model downloaded, and what model is it?" | Could be in embedder.py, config.py, Dockerfile, or cli.py |
| 18 | "How does the healthcheck work in Docker?" | 1 line in Dockerfile, easy to miss with broad reads |
| 19 | "What hash algorithm is used for content dedup and why?" | Buried in hasher.py, referenced elsewhere |

### Category 7: Documentation/README Questions (tests both)

The answer is literally in markdown files.

| # | Query | What it tests |
|---|-------|---------------|
| 20 | "What MCP tools does Arrow expose and what does each do?" | README has the full table — traditional just reads README |

---

## Metrics to Capture

For each use case, record:

| Metric | How to measure |
|--------|----------------|
| Tool calls | Count of Glob + Grep + Read (traditional) vs Arrow MCP calls |
| Tokens from content | Estimate from lines returned × ~4 tokens/line (traditional) or from Arrow's reported token count |
| Wall time | `python3 -c "import time; print(int(time.time()*1000))"` before and after |
| Answer quality | Subjective 1-5: did the approach give a complete, accurate answer? |
| Precision | What % of returned content was actually relevant to answering the question? |

---

## Expected Outcomes

| Category | Expected Winner | Why |
|----------|----------------|-----|
| Targeted Lookup | Traditional | Glob finds known files instantly, small files = few tokens |
| Broad Architecture | Arrow | Traditional would need 5-15 Read calls across large files |
| Symbol Lookup | Arrow | Direct AST index lookup vs grep-then-read |
| Impact Analysis | Arrow | Traditional has no dependency graph |
| Cross-Cutting | Arrow | Too many files to know which to read |
| Needle-in-Haystack | Depends | Arrow if it chunks well, traditional if grep finds it |
| Documentation | Traditional | Just read the README |

---

## Running the Benchmark

Prompt Claude Code with each query, specifying the round. Example:

```
Round 1 — Traditional: "How does hybrid search work end-to-end?"
Use ONLY Glob, Grep, Read. Timestamp before/after. Count calls and tokens.

Round 2 — Arrow: Same question, use ONLY get_context(). Timestamp before/after.
```

Collect results into a summary table after all 20 use cases.

After completing all benchmarks, append the full results summary table to this file (`benchmarks/arrow_vs_traditional_test_spec.md`).
