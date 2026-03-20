# Benchmark 21: Resolve Storage

**Category:** resolve_symbol — Cross-repo symbol resolution
**Query:** "Where is Storage defined and which repos have it?"
**Date:** 2026-03-20

## Round 1 — Traditional (Glob + Grep + Read)

| Metric | Value |
|--------|-------|
| Wall time | 10,715 ms |
| Tool calls | 4 (2x Grep, 1x Read, timestamps excluded) |
| Result | `class Storage` at `src/arrow/storage.py:240`. No matches in `~/.arrow/clones/`. |
| Quality | 4/5 |
| Precision | 85% |

**Notes:** Found the definition and checked cloned repos. Required manual construction of search paths — had to guess that `~/.arrow/clones` is where indexed repos live. Could miss repos indexed from other locations. No cross-repo awareness beyond what the filesystem search covers.

## Round 2 — Arrow (resolve_symbol)

| Metric | Value |
|--------|-------|
| Wall time | 7,385 ms |
| Tool calls | 1 (resolve_symbol, timestamps excluded) |
| Result | `class Storage` at `src/arrow/storage.py:240-241` in project `andreasmyleus/arrow`. 1 result across all indexed projects. |
| Quality | 5/5 |
| Precision | 100% |

**Notes:** Single call searched all indexed projects automatically. Returned the definition with docstring, file location, line numbers, and project name. No need to guess filesystem paths or manually search multiple directories.

## Comparison

| Metric | Traditional | Arrow | Delta |
|--------|------------|-------|-------|
| Wall time (ms) | 10,715 | 7,385 | -31% |
| Tool calls | 4 | 1 | -75% |
| Quality | 4/5 | 5/5 | +1 |
| Precision | 85% | 100% | +15pp |

## Verdict

Arrow wins on all metrics. The `resolve_symbol` tool is purpose-built for this query type: it searches across all indexed projects in a single call, returns structured results with project attribution, and requires no knowledge of where repos are stored on disk. The traditional approach required guessing the clone directory and still lacked awareness of any projects indexed from other paths.
