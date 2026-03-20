# Query 9: Find all places where exceptions are caught and logged

**Category:** Regex
**Arrow tool(s) under test:** `search_regex` with pattern `except.*:.*log`
**Date:** 2026-03-20

## Round 1 — Traditional (Glob + Grep + Read)

**Approach:** Used Grep with pattern `except\s+\w.*:` and `-A 3` context to find all except blocks and inspect the following lines for logging calls.

**Findings:** 13 locations where exceptions are caught AND logged across `src/arrow/`:

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
| 9 | `server.py` | 149 | `except Exception` | `logger.exception("Background re-index failed for %s")` |
| 10 | `server.py` | 270 | `except Exception` | `logger.debug("Incremental refresh failed for %s")` |
| 11 | `server.py` | 298 | `except Exception` | `logger.exception("Auto-index failed for %s")` |
| 12 | `server.py` | 1110 | `except Exception` | `logger.exception("Auto-warm failed for %s")` |
| 13 | `tools_data.py` | 454 | `except Exception` | `logger.debug("recall_memory FTS error for query %r")` |

Additionally identified 18+ silent exception handlers (catch + pass/return without logging) across `storage.py`, `tools_github.py`, `server.py`, `vector_store.py`, `discovery.py`, and `tools_data.py`.

**Tools used:** 2 (Grep x2: src + tests)
**Lines returned:** ~160 lines of content
**Tokens (est.):** ~640
**Elapsed:** 9,220 ms
**Quality:** 5/5 — Complete coverage, full context, able to distinguish logged vs silent exceptions.
**Precision:** 100% — Every match manually verified with context.

## Round 2 — Arrow (`search_regex`)

**Approach:** Called `search_regex` with pattern `except.*:.*log`, project `andreasmyleus/arrow`.

**Result:** Permission denied. The MCP tool call was blocked.

**Tools used:** 1 (failed)
**Tokens (est.):** 0 (no results returned)
**Elapsed:** 7,308 ms (including tool fetch + failed call)
**Quality:** 0/5 — No results produced.
**Precision:** N/A

## Comparison

| Metric | Traditional | Arrow |
|--------|------------|-------|
| Tools called | 2 | 1 (failed) |
| Elapsed (ms) | 9,220 | 7,308 |
| Tokens (est.) | ~640 | 0 |
| Results found | 13 logged + 18 silent | 0 |
| Quality (1-5) | 5 | 0 |
| Precision (%) | 100% | N/A |

## Notes

- **Arrow tool was blocked by permission denial**, so no meaningful comparison can be made for this query.
- The single-line regex pattern `except.*:.*log` would only match cases where `except` and `log` appear on the same line. Since Python exception handling puts the `except` clause and the `logger` call on separate lines, this pattern would require `multiline=True` to work correctly. The traditional approach sidestepped this by using `-A 3` context lines after each `except` match.
- This query highlights a pattern where multiline regex is essential — the `search_regex` tool does support a `multiline` parameter, but we could not verify its effectiveness due to the permission error.
- The traditional approach found both logged and silently-caught exceptions, providing a more complete picture of exception handling practices in the codebase.
