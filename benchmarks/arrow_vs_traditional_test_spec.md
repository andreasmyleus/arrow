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
      01-incremental-indexing.md  # per-query report
      02-chunker-nesting.md
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
| 1 | "How does the indexer decide which files to re-index vs skip on incremental updates?" | `get_context` | `01-incremental-indexing` | Targeted — answer spans indexer.py + storage.py, pure Python |
| 2 | "How does the chunker handle nested classes and inner functions?" | `get_context` | `02-chunker-nesting` | Targeted — answer is in chunker.py, tests AST-level code retrieval |
| 3 | "How does the hybrid search work end-to-end? Walk me through a query from `get_context()` to returned chunks." | `get_context` | `03-hybrid-search-e2e` | Broad — spans server.py → search.py → storage.py → vector_store.py |
| 4 | "Review error handling patterns across the codebase — where are errors caught, logged, or swallowed?" | `get_context` | `04-error-handling` | Very broad — requires reading every source file |
| 5 | "How is configuration managed — env vars, defaults, CLI flags?" | `get_context` | `05-configuration` | Cross-cutting — touches config.py, cli.py, server.py |
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
| 9 | "Find all places where exceptions are caught and logged" | `search_regex` pattern: `except.*:[\s\S]*?log` (multiline) | `09-exception-logging` | Multiline regex — except and log often on different lines |
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
| 20 | "What functions changed in search.py and who calls them?" | `get_diff_context` | `20-search-diff` | Changed code + caller analysis |

**Setup required:** Before running Q20, make a trivial uncommitted change to `search.py` (e.g., add a comment). Revert after the query.

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
| 28 | "How does Arrow detect and skip binary files during indexing?" | `get_context` | `28-binary-detection` | Answer buried in discovery.py or indexer.py, non-obvious location |
| 29 | "What hash algorithm is used for content dedup and why?" | `get_context` | `29-hash-algorithm` | Buried in hasher.py, referenced elsewhere |

### Category 14: Token budgeting (tests `get_context` smart retrieval)

The answer requires understanding how Arrow decides what to return.

| # | Query | Arrow tool(s) | Report slug | What it tests |
|---|-------|---------------|-------------|---------------|
| 30 | "How does `get_context` decide how many tokens to return and which chunks to pick?" | `get_context` | `30-token-budgeting` | Answer spans search.py + server.py — tests self-referential retrieval |

---

## Arrow Tools Coverage

| Arrow tool | Queries | Notes |
|------------|---------|-------|
| `get_context` | 1-6, 27-30 | Primary retrieval — all queries now target Python source code (no Dockerfile/CI/README) |
| `search_code` | 7-8 | Hybrid search without token budgeting |
| `search_regex` | 9-10 | Direct Grep competitor — Q9 uses multiline pattern |
| `search_structure` | 11-13 | AST-based symbol lookup |
| `what_breaks_if_i_change` | 14-15 | Impact analysis (no traditional equivalent) |
| `trace_dependencies` | 16-17 | Import graph traversal |
| `get_tests_for` | 18-19 | Test discovery |
| `get_diff_context` | 20 | Changed code + callers (requires uncommitted changes — see setup note) |
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

## Expected Outcomes (updated after 4 runs)

| Category | Arrow tool | Expected Winner | Actual (run 4) | Why |
|----------|-----------|----------------|----------------|-----|
| `get_context` targeted (Q1-2) | `get_context` | Arrow | *Not yet tested (queries replaced)* | New queries target Python code where chunking should help |
| `get_context` broad (Q3-4) | `get_context` | Arrow | *0/2 — concurrency bug* | Should win once concurrency fix is verified |
| `get_context` cross-cutting (Q5-6) | `get_context` | Arrow | *0/2 — concurrency bug* | Requires multi-file retrieval — Arrow's sweet spot |
| `get_context` needle (Q27-29) | `get_context` | Depends | *0/3 — concurrency bug* | Arrow if chunks are relevant; grep if keyword is obvious |
| `get_context` token budgeting (Q30) | `get_context` | Arrow | *Not yet tested (query replaced)* | Self-referential query — Arrow should retrieve its own code well |
| `search_code` (Q7-8) | `search_code` | Tie/Arrow | 0W 1L 1T | Competitive — Q8 tied at quality 5, Q7 hurt by index pollution |
| `search_regex` (Q9-10) | `search_regex` | Close | *Untested — permission bug* | Direct Grep competitor — Arrow adds chunk context |
| `search_structure` (Q11-13) | `search_structure` | **Arrow** | **2W 1L** | AST-precise lookup dominates; common names can over-return |
| `what_breaks_if_i_change` (Q14-15) | `what_breaks_if_i_change` | **Arrow** | **2W 0L** | No traditional equivalent — always use Arrow |
| `trace_dependencies` (Q16-17) | `trace_dependencies` | **Arrow** | **1W 0L 1T** | Full import graph in one call — always use Arrow |
| `get_tests_for` (Q18-19) | `get_tests_for` | Arrow | **1W 1L** | Excellent for specific functions; broad queries truncate |
| `get_diff_context` (Q20) | `get_diff_context` | **Arrow** | **1W 0L** | Changed functions + callers in one call |
| `resolve_symbol` (Q21-22) | `resolve_symbol` | **Arrow** | **2W 0L** | Cross-repo lookup — always use Arrow |
| `file_summary` (Q23-24) | `file_summary` | **Arrow** | **2W 0L** | Structured JSON overview — always use Arrow |
| `project_summary` (Q25) | `project_summary` | Traditional | **0W 1L** | File count misleading (counts .md); needs LOC metric |
| `find_dead_code` (Q26) | `find_dead_code` | **Arrow** | **1W 0L** | 6.7x faster, better recall; some framework false positives |

---

## Running the Benchmark

### Prerequisites

1. Arrow MCP server running and index **force re-indexed**: `index_codebase(path="/Users/andreas/arrow", force=true)` — do NOT rely on auto-re-index during the run
2. For `resolve_symbol` queries (21-22): at least one other repo indexed (e.g. `index_github_repo`)
3. For `get_diff_context` query (20): add a trivial uncommitted change to search.py before running, revert after
4. For `search_regex` queries (9-10): pre-approve the tool by calling it once manually before the run

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
