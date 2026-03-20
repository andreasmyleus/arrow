# Query 9: "Find all places where exceptions are caught and logged"

Category: Regex
Arrow tool(s) under test: search_regex

## Round 1 — Traditional

**Timestamps:** start=1774009885216 end=1774009897204
**Wall time:** 11988ms
**Tool calls:** 2 (Grep x2)
**Tokens from content:** ~620 (155 lines of grep output x ~4 tokens)
**Answer quality:** 5
**Precision:** 100%

### Answer

Found 13 locations across 8 files where exceptions are caught and logged via `logger.*`:

1. **embedder.py:129** — `except Exception: logger.exception("Failed to load embedding model")`
2. **search.py:472** — `except Exception: logger.warning("Vector search failed, using BM25 only")`
3. **indexer.py:66** — `except Exception: logger.exception("Embedding generation failed")`
4. **indexer.py:144** — `except OSError: logger.warning("Cannot hash %s")`
5. **indexer.py:157** — `except OSError: logger.warning("Cannot read %s")`
6. **vector_store.py:39** — `except Exception: logger.warning("Could not load index, starting fresh")`
7. **chunker.py:270** — `except Exception: logger.debug("No tree-sitter grammar for: %s")`
8. **chunker.py:521** — `except Exception: logger.warning("tree-sitter parse error for %s")`
9. **server.py:149** — `except Exception: logger.exception("Background re-index failed for %s")`
10. **server.py:270** — `except Exception: logger.debug("Incremental refresh failed for %s")`
11. **server.py:298** — `except Exception: logger.exception("Auto-index failed for %s")`
12. **server.py:1110** — `except Exception: logger.exception("Auto-warm failed for %s")`
13. **tools_data.py:454** — `except Exception: logger.debug("recall_memory FTS error for query %r")`

Additionally, there are ~20 other `except` blocks that silently handle errors (with `pass`, `return`, or inline handling) without logging, which were correctly excluded from the results.

### Files read
- All .py files in src/arrow/ searched via Grep (no files read individually)

## Round 2 — Arrow

**Timestamps:** start=1774009906867 end=1774009924681
**Wall time:** 17814ms
**Tool calls:** 2 (search_regex x2, both denied)
**Tokens from content:** 0
**Chunks returned:** 0
**Answer quality:** 0
**Precision:** 0%

### Answer

Arrow's `search_regex` tool was denied permission (both with and without explicit project parameter). No results were returned.

### Observations

**Traditional wins by default.** The Arrow `search_regex` tool could not be invoked due to permission denial, so this round cannot provide a fair comparison.

The traditional approach using Grep was effective for this task. A single Grep call with `-A 3` context lines on `except\s+\w+` across `src/arrow/*.py` returned all exception handlers with enough context to determine which ones included logging. The manual filtering step (identifying which `except` blocks actually call `logger.*`) was straightforward from the grep output.

The regex pattern `except.*:.*log` (the Arrow test pattern) would only match cases where the except and the log call are on the same line, which is never the case in this codebase — the `except` line and the `logger.*` call are always on separate lines. This means Arrow's `search_regex` in single-line mode would return zero results for this pattern. The `multiline=True` flag would be required for meaningful results.

**Key takeaway:** Even if Arrow had been accessible, this query highlights the importance of multiline regex support for cross-line pattern matching. The traditional Grep tool with `-A` context lines is naturally suited for this kind of "pattern A followed by pattern B on the next line" search.
