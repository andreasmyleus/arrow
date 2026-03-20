# Query 09: Find all places where exceptions are caught and logged

**Category:** search_regex — Regex
**Arrow tool under test:** `search_regex`
**Query:** "Find all places where exceptions are caught and logged"

---

## Round 1 — Traditional (Glob + Grep + Read)

**Timestamps:** 1774012315852 - 1774012332694
**Duration:** 16,842 ms
**Tool calls:** 3 (1 Grep files_with_matches, 1 Grep content with -A3, 1 Grep multiline)

### Results

Found 13 locations where exceptions are caught AND logged across 8 files:

| # | File | Line | Exception | Log call |
|---|------|------|-----------|----------|
| 1 | `embedder.py` | 129 | `except Exception` | `logger.exception("Failed to load embedding model")` |
| 2 | `search.py` | 472 | `except Exception` | `logger.warning("Vector search failed, using BM25 only")` |
| 3 | `indexer.py` | 66 | `except Exception` | `logger.exception("Embedding generation failed")` |
| 4 | `indexer.py` | 144 | `except OSError` | `logger.warning("Cannot hash %s")` |
| 5 | `indexer.py` | 157 | `except OSError` | `logger.warning("Cannot read %s")` |
| 6 | `vector_store.py` | 39 | `except Exception` | `logger.warning("Could not load index, starting fresh")` |
| 7 | `chunker.py` | 270 | `except Exception` | `logger.debug("No tree-sitter grammar for: %s")` |
| 8 | `chunker.py` | 521 | `except Exception` | `logger.warning("tree-sitter parse error for %s")` |
| 9 | `server.py` | 152 | `except Exception` | `logger.exception("Background re-index failed")` |
| 10 | `server.py` | 277 | `except Exception` | `logger.debug("Incremental refresh failed")` |
| 11 | `server.py` | 307 | `except Exception` | `logger.exception("Auto-index failed")` |
| 12 | `server.py` | 1119 | `except Exception` | `logger.exception("Auto-warm failed")` |
| 13 | `tools_data.py` | 454 | `except Exception` | `logger.debug("recall_memory FTS error")` |

**Tokens (estimated):** ~1,800 tokens input from grep output
**Quality:** 5/5 — comprehensive, precise, all matches verified
**Precision:** 100% — each result manually confirmed as except + log

---

## Round 2 — Arrow (`search_regex`)

**Timestamps:** 1774012341418 - 1774012350963
**Duration:** 9,545 ms (tool call + response)
**Tool calls:** 2 (tried two regex patterns)

### Attempt 1: `except.*:[\s\S]*?log`
- **Matches:** 50 (hit limit), all from `tests/test_search_regex.py`
- **Problem:** The `[\s\S]*?` pattern in multiline mode matched from an `except` in a test fixture string all the way to the word "log" in "logging" much later. Returned test fixture data, not actual source code exception handlers.
- **Precision:** 0% — none of the 13 real locations found; all results were false positives from test fixtures.

### Attempt 2: `except.*:\n\s+logger\.`
- **Matches:** 50 (hit limit), from `src/arrow/tools_data.py`
- **Problem:** Same greedy multiline issue. The first match was `except OSError: continue` at line 65 (NOT followed by a logger call), but the `\n` matched across dozens of lines until a `logger` reference appeared much later. All subsequent "matches" were continuation context.
- **Precision:** ~0% — the match boundary was incorrect; it matched across unrelated code.

**Tokens:** ~2,500 tokens returned (mostly irrelevant context)
**Quality:** 1/5 — failed to find any of the 13 actual locations
**Precision:** 0%

---

## Comparison

| Metric | Traditional | Arrow |
|--------|-------------|-------|
| Duration | 16.8s | 9.5s |
| Tool calls | 3 | 2 |
| Results found | 13/13 | 0/13 |
| Precision | 100% | 0% |
| Quality | 5/5 | 1/5 |
| Tokens consumed | ~1,800 | ~2,500 |

**Winner:** Traditional

## Analysis

Arrow's `search_regex` with multiline mode has a fundamental problem for this query pattern. The `[\s\S]*?` (or `\n`) in multiline/DOTALL mode matches across arbitrary amounts of code, causing the regex to span from an `except` on one line to any occurrence of "log" potentially hundreds of lines later. This produces massive false-positive matches.

The root cause is that `search_regex` operates on pre-indexed chunks (not raw files), and the multiline regex matching spans the entire chunk content. When a chunk contains multiple except blocks or the word "log" appears anywhere later, the non-greedy `*?` still matches across many lines.

Traditional grep with `-A3` (show 3 lines after match) was far more effective because it let me see the immediate handler body and manually verify which exceptions had logging. The Grep tool's multiline mode had the same greedy matching issue but returned all results, allowing manual filtering.

**Potential improvement:** `search_regex` could benefit from a max-span parameter for multiline matches (e.g., limit match to N lines) or a two-pass approach: find `except` lines first, then check the next 1-3 lines for `log`.
