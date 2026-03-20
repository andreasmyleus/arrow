# Query 30: Token Budgeting in get_context

**Query:** "How does get_context decide how many tokens to return and which chunks to pick?"
**Category:** get_context — Documentation
**Arrow tool under test:** get_context
**Date:** 2026-03-20

---

## Round 1 — Traditional (Glob + Grep + Read)

**Timestamps:** 1774012397890 → 1774012432146 (34.3s)

### Process
1. Grep for `token_budget|budget` across `src/arrow/` — found references in server.py, search.py, config.py, cli.py (1 call)
2. Grep for `get_context` in server.py — located the MCP tool wrapper (1 call)
3. Read server.py L798-907 — the `get_context` MCP tool: budget resolution priority (caller arg > config > auto), auto-estimation via `estimate_budget()`, dedup strategy, session tracking (1 call)
4. Read search.py L295-324 — `QueryClassification` dataclass and start of `classify_query()` (1 call)
5. Read search.py L324-403 — full `classify_query()`: targeted vs broad signals (file patterns, symbol calls, query length, broad indicators), budget/limit suggestions per classification (1 call)
6. Read search.py L650-785 — `estimate_budget()` (targeted=4000t, broad=8000t ceilings) and `HybridSearcher.get_context()`: relevance-first assembly with per-file cap of 3, hard token ceiling stop, no truncation (1 call)
7. Grep for `filter_by_relevance` — found at L206 (1 call)
8. Read search.py L206-294 — `filter_by_relevance()`: min score ratio (0.25), score drop-off cliff detection (0.4), floor of 5 results (1 call)
9. Grep for threshold constants `_MIN_SCORE_RATIO`, `_SCORE_DROP_RATIO`, `_MIN_RESULTS_FLOOR` — confirmed values (1 call)

### Answer (Traditional)
The token budgeting pipeline works in three stages:

1. **Budget resolution** (server.py `get_context`): Priority is caller argument > config file > auto-estimation. If auto (budget=0), `estimate_budget()` classifies the query and sets a ceiling.

2. **Query classification** (search.py `classify_query`): Scores targeted vs broad signals. Targeted queries (mentions file, symbol, short) get 1000-2000t suggested budget; broad queries (architecture, long, "how does") get 3000-6000t. `estimate_budget()` then maps to final ceilings: targeted=4000t, broad=8000t.

3. **Chunk selection** (search.py `HybridSearcher.get_context`): Relevance-first — `filter_by_relevance()` already ran inside `search()` using min score ratio (0.25 of top score) and cliff detection (0.4 drop between consecutive results), with a floor of 5 results. Assembly then iterates ranked results with: max 3 chunks per file, hard token ceiling stop (no truncation), 15-token header overhead per chunk.

### Metrics
| Metric | Value |
|--------|-------|
| Tool calls | 9 (3 Grep + 6 Read) |
| Estimated tokens consumed | ~8,500 |
| Wall time | 34.3s |
| Quality | 5/5 — complete understanding of all three stages |
| Precision | 95% — all reads were targeted and relevant |

---

## Round 2 — Arrow (get_context)

**Timestamps:** 1774012435159 → 1774012448534 (13.4s)

### Process
1. `get_context("How does get_context decide how many tokens to return and which chunks to pick?")` — returned 0 results (natural language query too broad/vague for search index).
2. `get_context("token budget estimate_budget get_context relevance filtering chunk selection")` — returned 14 chunks across 6 files (6076 tokens used, 8000t auto budget). Included: `get_context` in server.py, `estimate_budget` and `HybridSearcher.get_context` in search.py, relevant tests from test_budget.py and test_precision.py, CLI context handler, and benchmark/demo code.

### Answer (Arrow)
Arrow's second call returned all the core functions needed to answer the question:
- `get_context` MCP wrapper (server.py) — budget resolution chain
- `estimate_budget` (search.py) — query classification → ceiling mapping
- `HybridSearcher.get_context` (search.py) — relevance-first assembly with token ceiling

It also surfaced tests (test_budget.py) that document the design intent: budget is a ceiling not a target, relevance cutoff stops before budget exhaustion, no truncation. The benchmark and demo code added context but was not essential.

**Missing from Arrow results:** `filter_by_relevance()` and `classify_query()` were not returned as chunks (likely excluded by dedup from first call or ranked lower). These are critical to fully understanding chunk selection. The constants `_MIN_SCORE_RATIO=0.25`, `_SCORE_DROP_RATIO=0.4`, `_MIN_RESULTS_FLOOR=5` were also absent.

### Metrics
| Metric | Value |
|--------|-------|
| Tool calls | 2 (1 failed + 1 successful get_context) |
| Tokens consumed | ~6,076 (from Arrow metadata) |
| Wall time | 13.4s |
| Quality | 4/5 — covered budget resolution and assembly well, but missed filter_by_relevance details |
| Precision | 70% — 4 of 14 chunks were tests/benchmarks/demo code, not directly needed |

---

## Comparison

| Metric | Traditional | Arrow | Winner |
|--------|------------|-------|--------|
| Tool calls | 9 | 2 | Arrow |
| Tokens consumed | ~8,500 | ~6,076 | Arrow |
| Wall time | 34.3s | 13.4s | Arrow |
| Quality | 5/5 | 4/5 | Traditional |
| Precision | 95% | 70% | Traditional |

## Analysis

**Arrow strengths:** Significantly faster (2.6x) and lower token cost. Single call surfaced the three core functions plus supporting tests that validate the design philosophy. Good for getting a rapid overview.

**Arrow weaknesses:** The initial natural-language query returned zero results — had to reformulate with keywords. The successful call missed `filter_by_relevance()` and `classify_query()`, which are essential for a complete answer about how chunks are "picked." Some token budget was spent on test and demo code that added limited value. The dedup from the failed first call may have excluded relevant chunks from the second call.

**Traditional strengths:** Methodical search-then-read approach found every relevant function and constant. Grep for specific identifiers (`filter_by_relevance`, `_MIN_SCORE_RATIO`) allowed precise navigation to exactly the right code.

**Verdict:** Arrow wins on efficiency but Traditional wins on completeness for this documentation-style query. Arrow's result would give a developer ~85% of the answer; the Traditional approach gave 100%. For a query specifically about token budgeting internals, the keyword-based Arrow query worked well for the main functions but missed supporting functions that are called indirectly.
