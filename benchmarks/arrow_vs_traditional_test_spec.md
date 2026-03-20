# Arrow MCP vs Traditional Claude Code — Benchmark Test Spec

## Methodology

For each use case, run two rounds on `/Users/andreas/arrow`:

**Round 1 — Normal (no Arrow):** Answer the question however you normally would — Glob, Grep, Read, Bash, Agent subagents, whatever tools you'd reach for naturally. No Arrow MCP tools. Record timestamps before/after, count tool calls, estimate tokens from file content.

**Round 2 — Arrow:** Answer the same question using **only** the designated Arrow tool(s) listed for that query. No supplemental Glob/Grep/Read. Record timestamps before/after, note tokens returned.

**Rules:**
- Actually answer the question both times (no skipping)
- Don't over-read or under-read to skew results
- Be honest about which approach gave a better answer
- Note cases where Arrow returns irrelevant context
- For Arrow round, use ONLY the designated tool(s) — don't supplement with Glob/Read

### Agent execution notes (learned from runs 1-4)

- **Do NOT run both rounds in background agents.** MCP tool calls from background agents suffer from concurrency issues (`_ensure_indexed` SQLite contention) and permission denials (`search_regex` blocked). Instead, run both rounds **sequentially in the main session**, or run Traditional in a background agent and Arrow in the main session.
- **Force re-index BEFORE starting**, then do NOT re-index during the run. The `_ensure_indexed` auto-refresh causes issues under concurrent load.
- **For `search_regex` queries**, ensure the tool is pre-approved in permissions before the run (call it once manually first).

---

## Reports

### Directory structure

All benchmark reports live under `benchmarks/reports/`:

```
benchmarks/
  reports/
    run-YYYY-MM-DDT-HHMM/       # one directory per full benchmark run
      summary.md                 # aggregate table + analysis for all queries
      01-docker-setup.md         # per-query report
      02-ci-pipeline.md
      ...
      30-dead-code.md
    run-YYYY-MM-DDT-HHMM/       # next run (e.g. after search improvements)
      ...
```

### Naming conventions

| Item | Format | Example |
|------|--------|---------|
| Run directory | `run-YYYY-MM-DDTHHMM` (24h local time) | `run-2026-03-20T1435` |
| Per-query report | `NN-slug.md` (zero-padded query number, kebab-case slug from query) | `04-hybrid-search-e2e.md` |
| Summary report | `summary.md` (always this name) | `summary.md` |

### Per-query report format

Each `NN-slug.md` should contain:

```markdown
# Query N: "<full query text>"

Category: <category name>
Arrow tool(s) under test: <tool names>

## Round 1 — Traditional

**Timestamps:** start=<epoch_ms> end=<epoch_ms>
**Wall time:** <N>ms
**Tool calls:** <N> (list: <Glob×N, Grep×N, Read×N>)
**Tokens from content:** ~<N>
**Answer quality:** <1-5>
**Precision:** <N>%

### Answer
<the actual answer>

### Files read
- <file1> (<N> lines)
- <file2> (<N> lines)

## Round 2 — Arrow

**Timestamps:** start=<epoch_ms> end=<epoch_ms>
**Wall time:** <N>ms
**Tool calls:** <N> (list which Arrow tools were called)
**Tokens from content:** <N> (Arrow-reported)
**Chunks returned:** <N>/<N> (if applicable)
**Answer quality:** <1-5>
**Precision:** <N>%

### Answer
<the actual answer>

### Observations
<which approach won, why, any Arrow relevance issues>
```

### Summary report format

`summary.md` should contain:

```markdown
# Benchmark Run: YYYY-MM-DD

Arrow version: <git commit short SHA>
Codebase: /Users/andreas/arrow (<N> files indexed)

## Results

| # | Query (short) | Arrow tool(s) | Category | Trad calls | Trad tokens | Arrow tokens | Trad time | Arrow time | Winner | Quality (T/A) |
|---|---------------|---------------|----------|------------|-------------|--------------|-----------|------------|--------|---------------|
| 1 | Docker setup  | get_context   | Targeted | ...        | ...         | ...          | ...       | ...        | ...    | .../...       |
...

## Per-tool summary

| Arrow tool | Queries tested | Wins | Losses | Ties | Avg quality | Avg token savings |
|------------|---------------|------|--------|------|-------------|-------------------|
| get_context | ... | ... | ... | ... | ... | ... |
| search_code | ... | ... | ... | ... | ... | ... |
...

## Totals

| Metric | Traditional | Arrow |
|--------|-------------|-------|
| Total tool calls | ... | ... |
| Total tokens | ... | ... |
| Total wall time | ... | ... |
| Avg answer quality | ... | ... |
| Queries won | ... | ... |

## Analysis
<observations, patterns, where each tool excels vs struggles>
```

---

## Use Cases

### Category 1: `get_context` — Primary retrieval

The main tool. Natural language query → relevant code chunks with auto token budgeting.

| # | Query | Arrow tool(s) | Report slug | What it tests |
|---|-------|---------------|-------------|---------------|
| 1 | "Review the Docker setup — how is it configured, what does it build, and how would I run it?" | `get_context` | `01-docker-setup` | Targeted lookup — files are trivially named |
| 2 | "What does the CI pipeline do?" | `get_context` | `02-ci-pipeline` | Single well-known file |
| 3 | "How does the hybrid search work end-to-end? Walk me through a query from `get_context()` to returned chunks." | `get_context` | `03-hybrid-search-e2e` | Broad — spans server.py → search.py → storage.py → vector_store.py |
| 4 | "Review error handling patterns across the codebase — where are errors caught, logged, or swallowed?" | `get_context` | `04-error-handling` | Very broad — requires reading every source file |
| 5 | "How is configuration managed — env vars, defaults, CLI flags?" | `get_context` | `05-configuration` | Cross-cutting — touches config.py, cli.py, server.py, Dockerfile |
| 6 | "How does Arrow handle multiple projects — indexing, searching, and isolation?" | `get_context` | `06-multi-project` | Cross-cutting — spans 4+ files |

### Category 2: `search_code` — Hybrid search

BM25 + vector search with frecency boost. Returns ranked results without token budgeting.

| # | Query | Arrow tool(s) | Report slug | What it tests |
|---|-------|---------------|-------------|---------------|
| 7 | "How is `frecency` calculated and where is it applied in search ranking?" | `search_code` | `07-frecency` | Cross-file concept, keyword + semantic match |
| 8 | "What does `reciprocal_rank_fusion` do and how are BM25 and vector scores combined?" | `search_code` | `08-rrf-scoring` | Specific algorithm, tests ranking quality |

### Category 3: `search_regex` — Exact pattern matching

Regex search against indexed chunks. Competes directly with Grep.

| # | Query | Arrow tool(s) | Report slug | What it tests |
|---|-------|---------------|-------------|---------------|
| 9 | "Find all places where exceptions are caught and logged" | `search_regex` pattern: `except.*:.*log` | `09-exception-logging` | Regex across codebase — direct Grep competitor |
| 10 | "Find all environment variable reads" | `search_regex` pattern: `os\.environ\|getenv\|ARROW_` | `10-env-var-reads` | Multi-pattern regex search |

### Category 4: `search_structure` — AST symbol lookup

Find functions, classes, methods by name via the AST index.

| # | Query | Arrow tool(s) | Report slug | What it tests |
|---|-------|---------------|-------------|---------------|
| 11 | "Find the `estimate_budget` function" | `search_structure` | `11-estimate-budget` | Exact function lookup |
| 12 | "Find all classes in the codebase" | `search_structure` kind=`class` | `12-all-classes` | Broad structural query — traditional needs Grep across all files |
| 13 | "Find all methods named `search`" | `search_structure` | `13-search-methods` | Common name, tests precision vs grep noise |

### Category 5: `what_breaks_if_i_change` — Impact analysis

Full dependency analysis: callers, tests, dependents, risk level. No traditional equivalent without reading everything.

| # | Query | Arrow tool(s) | Report slug | What it tests |
|---|-------|---------------|-------------|---------------|
| 14 | "If I change the `Storage` class constructor, what breaks?" | `what_breaks_if_i_change` | `14-storage-impact` | High-impact class, many dependents |
| 15 | "What's the blast radius of changing `chunk_file` in chunker.py?" | `what_breaks_if_i_change` | `15-chunker-impact` | Core function in indexing pipeline |

### Category 6: `trace_dependencies` — Import graph

What a file imports and what imports it.

| # | Query | Arrow tool(s) | Report slug | What it tests |
|---|-------|---------------|-------------|---------------|
| 16 | "What files import from `storage.py` and what do they use?" | `trace_dependencies` | `16-storage-imports` | Central module with many importers |
| 17 | "What does `search.py` depend on?" | `trace_dependencies` | `17-search-deps` | Forward dependency tracing |

### Category 7: `get_tests_for` — Test discovery

Find tests for a function via import tracing + naming conventions.

| # | Query | Arrow tool(s) | Report slug | What it tests |
|---|-------|---------------|-------------|---------------|
| 18 | "Find all tests that exercise the search pipeline" | `get_tests_for` function=`search` | `18-search-tests` | Broad test discovery |
| 19 | "What tests cover the `authenticate` function?" | `get_tests_for` function=`authenticate` | `19-auth-tests` | Specific function test mapping |

### Category 8: `get_diff_context` — Changed code analysis

Shows changed functions + all callers/dependents. Requires uncommitted changes.

| # | Query | Arrow tool(s) | Report slug | What it tests |
|---|-------|---------------|-------------|---------------|
| 20 | "What functions changed in search.py and who calls them?" | `get_diff_context` | `20-search-diff` | Changed code + caller analysis (run with uncommitted changes to search.py) |

### Category 9: `resolve_symbol` — Cross-repo symbol resolution

Find definitions across all indexed repos.

| # | Query | Arrow tool(s) | Report slug | What it tests |
|---|-------|---------------|-------------|---------------|
| 21 | "Where is `Storage` defined and which repos have it?" | `resolve_symbol` | `21-resolve-storage` | Cross-repo lookup (requires multiple indexed projects) |
| 22 | "Find all definitions of `search` across indexed repos" | `resolve_symbol` | `22-resolve-search` | Common name, cross-repo noise |

### Category 10: `file_summary` — Per-file breakdown

Functions, classes, imports, token counts for one file.

| # | Query | Arrow tool(s) | Report slug | What it tests |
|---|-------|---------------|-------------|---------------|
| 23 | "Give me an overview of server.py — what functions does it have, how big is it?" | `file_summary` | `23-server-summary` | Large file overview vs reading the whole file |
| 24 | "What's in storage.py — structure, classes, methods?" | `file_summary` | `24-storage-summary` | Largest file in codebase |

### Category 11: `project_summary` — Project overview

Language distribution, file structure, entry points.

| # | Query | Arrow tool(s) | Report slug | What it tests |
|---|-------|---------------|-------------|---------------|
| 25 | "Give me a high-level overview of this project — languages, structure, entry points" | `project_summary` | `25-project-overview` | Whole-project understanding vs manual exploration |

### Category 12: `find_dead_code` — Unreferenced code

Functions/methods with zero callers.

| # | Query | Arrow tool(s) | Report slug | What it tests |
|---|-------|---------------|-------------|---------------|
| 26 | "Are there any unused functions or dead code in this project?" | `find_dead_code` | `26-dead-code` | Codebase-wide analysis — no practical traditional equivalent |

### Category 13: Needle-in-Haystack (tests precision)

The answer is in a small, specific place but you don't know where.

| # | Query | Arrow tool(s) | Report slug | What makes it hard |
|---|-------|---------------|-------------|-------------------|
| 27 | "Where and how is the embedding model downloaded, and what model is it?" | `get_context` | `27-embedding-model` | Could be in embedder.py, config.py, Dockerfile, or cli.py |
| 28 | "How does the healthcheck work in Docker?" | `get_context` | `28-docker-healthcheck` | 1 line in Dockerfile, easy to miss with broad reads |
| 29 | "What hash algorithm is used for content dedup and why?" | `get_context` | `29-hash-algorithm` | Buried in hasher.py, referenced elsewhere |

### Category 14: Documentation (tests both)

The answer is literally in markdown files.

| # | Query | Arrow tool(s) | Report slug | What it tests |
|---|-------|---------------|-------------|---------------|
| 30 | "What MCP tools does Arrow expose and what does each do?" | `get_context` | `30-mcp-tools` | README has the full table — traditional just reads README |

---

## Arrow Tools Coverage

| Arrow tool | Queries | Notes |
|------------|---------|-------|
| `get_context` | 1-6, 27-30 | Primary retrieval, tested across targeted/broad/needle-in-haystack |
| `search_code` | 7-8 | Hybrid search without token budgeting |
| `search_regex` | 9-10 | Direct Grep competitor |
| `search_structure` | 11-13 | AST-based symbol lookup |
| `what_breaks_if_i_change` | 14-15 | Impact analysis (no traditional equivalent) |
| `trace_dependencies` | 16-17 | Import graph traversal |
| `get_tests_for` | 18-19 | Test discovery |
| `get_diff_context` | 20 | Changed code + callers (requires uncommitted changes) |
| `resolve_symbol` | 21-22 | Cross-repo symbol resolution (requires multiple indexed projects) |
| `file_summary` | 23-24 | Per-file structural overview |
| `project_summary` | 25 | Whole-project overview |
| `find_dead_code` | 26 | Dead code detection |

**Not benchmarked** (operational tools without meaningful traditional comparison):
`index_codebase`, `index_github_repo`, `index_github_content`, `index_git_commit`, `index_pr`, `list_projects`, `remove_project`, `export_index`, `import_index`, `context_pressure`, `tool_analytics`, `store_memory`, `recall_memory`, `list_memories`, `delete_memory`, `detect_stale_index`

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

| Category | Arrow tool | Expected Winner | Why |
|----------|-----------|----------------|-----|
| `get_context` targeted | `get_context` | Traditional | Glob finds known files instantly |
| `get_context` broad | `get_context` | Arrow | Traditional needs 5-15 Read calls across large files |
| `get_context` needle | `get_context` | Depends | Arrow if it chunks well, traditional if grep finds it |
| `get_context` docs | `get_context` | Traditional | Just read the README |
| `search_code` | `search_code` | Arrow | Hybrid search returns ranked relevant results |
| `search_regex` | `search_regex` | Close | Direct Grep competitor — Arrow adds structure, Grep is raw |
| `search_structure` | `search_structure` | Arrow | AST index vs noisy grep for `def search` |
| `what_breaks_if_i_change` | `what_breaks_if_i_change` | Arrow | No traditional equivalent without reading everything |
| `trace_dependencies` | `trace_dependencies` | Arrow | Manual grep for imports is tedious and error-prone |
| `get_tests_for` | `get_tests_for` | Arrow | Name-based grep misses indirect references |
| `get_diff_context` | `get_diff_context` | Arrow | Traditional needs git diff + manual caller tracing |
| `resolve_symbol` | `resolve_symbol` | Arrow | Cross-repo grep is impractical |
| `file_summary` | `file_summary` | Arrow | Structured overview vs reading 500+ line file |
| `project_summary` | `project_summary` | Arrow | Instant overview vs Glob + count + Read multiple files |
| `find_dead_code` | `find_dead_code` | Arrow | No practical traditional equivalent |

---

## Running the Benchmark

### Prerequisites

1. Arrow MCP server running and index up to date: `arrow index /Users/andreas/arrow`
2. For `resolve_symbol` queries (21-22): at least one other repo indexed (e.g. `index_github_repo`)
3. For `get_diff_context` query (20): have uncommitted changes in search.py

### Execution

Prompt Claude Code with each query, specifying the round. Example:

```
Round 1 — Traditional: "What files import from storage.py and what do they use?"
Use ONLY Glob, Grep, Read. Timestamp before/after. Count calls and tokens.

Round 2 — Arrow: Same question, use ONLY trace_dependencies("storage.py").
Timestamp before/after.

Write the report to benchmarks/reports/run-YYYY-MM-DDTHHMM/16-storage-imports.md
```

After completing all 30 use cases, generate `summary.md` in the same run directory.
