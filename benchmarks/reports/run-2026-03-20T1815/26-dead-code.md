# Query 26: Dead Code Detection

**Category:** Dead code detection
**Query:** "Are there any unused functions or dead code in this project?"
**Arrow tool:** `find_dead_code`

## Round 1 — Traditional (Glob + Grep + Read)

- **Start:** 1774009974280
- **End:** 1774010052103
- **Duration:** 77.8s
- **Tool calls:** 12 (1 Glob, 11 Grep)
- **Lines read:** ~350
- **Estimated tokens:** ~1,400

### Approach
1. Globbed all Python files in `src/arrow/`.
2. Grepped for all function/method definitions (~170 functions found).
3. Systematically grepped for function names across the codebase to find callers.
4. Could only check ~30 of ~170 functions due to time/call constraints.

### Findings
Identified 2 likely dead code items:
- `get_session_chunks_detail` in `storage.py` (line 1196) — only appears at its definition, zero callers anywhere.
- `get_project_meta` in `storage.py` (line 872) — marked as "Legacy method", only appears at its definition, zero callers.

### Limitations
Fundamentally incomplete approach. Checking all ~170 functions would require 170+ grep calls. Only ~18% of functions were checked. Many private/internal functions were skipped manually but not systematically.

**Quality: 3/5** — Found real dead code but coverage is very incomplete.
**Precision: 80%** — The 2 findings are likely correct but the recall is poor.

## Round 2 — Arrow (`find_dead_code`)

- **Start:** 1774010057574
- **End:** 1774010069635
- **Duration:** 12.1s
- **Tool calls:** 1
- **Tokens returned:** ~30 (minimal JSON response)

### Findings
Returned `{"dead_code": [], "total": 0}` — zero dead code found.

### Analysis
The tool's algorithm (in `storage.py:1401-1450`):
1. Queries all symbols of kind `function` or `method`.
2. Skips names starting with `_`, `test`, or matching `main`/`setup`/`teardown`.
3. For remaining symbols, checks if any other chunk's `content_text` contains the name via `LIKE %name%`.
4. If no other chunk references the name, it's flagged as dead.

The zero result likely means `get_session_chunks_detail` and `get_project_meta` are being matched by `LIKE %name%` in some chunk content (e.g., benchmark reports, comments, or documentation chunks that have been indexed). This is a false-negative issue with the `LIKE` approach — substring matches in comments/docs satisfy the check even when there are no actual code callers.

**Quality: 2/5** — Missed the dead code that manual analysis found. The `LIKE %name%` approach is too permissive, producing false negatives.
**Precision: N/A** — No results returned to evaluate precision on.

## Comparison

| Metric | Traditional | Arrow |
|---|---|---|
| Duration | 77.8s | 12.1s |
| Tool calls | 12 | 1 |
| Tokens consumed | ~1,400 | ~30 |
| Dead code found | 2 | 0 |
| Quality | 3/5 | 2/5 |
| Precision | 80% | N/A |

## Verdict

**Traditional wins on quality.** Despite being slow and incomplete, the manual grep approach found 2 genuine dead code items (`get_session_chunks_detail`, `get_project_meta`) that Arrow missed. Arrow was dramatically faster (12s vs 78s, 1 call vs 12) and cheaper in tokens, but its `LIKE %name%` reference-checking heuristic is too broad — substring matches in indexed documentation or benchmark report chunks cause false negatives. The tool would benefit from checking actual import/call references rather than substring content matching.
