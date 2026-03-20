# Query 12: Find all classes in the codebase

**Category:** Symbol
**Query:** "Find all classes in the codebase"
**Arrow tool(s) under test:** `search_structure` with kind="class"

## Round 1 — Traditional (Glob + Grep + Read)

| Metric | Value |
|--------|-------|
| Wall time | 7138 ms |
| Tool calls | 1 |
| Tokens (est.) | ~1240 (76 lines x ~4 tokens x ~4 words/line) |
| Quality | 4/5 |
| Precision | 96% |

**Method:** Single `Grep` call with pattern `^class \w+` across all Python files.

**Result:** 76 matching lines across `src/arrow/` and `tests/`. Found all top-level class definitions.

**Limitations:**
- Pattern `^class` only matches classes at column 0, missing the nested `class Inner` in `tests/test_edge_cases.py` (indented).
- Includes `MyClass` from a JavaScript string literal inside `test_edge_cases.py` line 95 (false positive from non-Python code embedded in a Python test).
- No source code or structural metadata returned, just the matching lines.

## Round 2 — Arrow (`search_structure`)

| Metric | Value |
|--------|-------|
| Wall time | 8720 ms |
| Tool calls | 1 |
| Tokens (est.) | ~4800 (72 results with source snippets) |
| Chunks returned | 72 |
| Quality | 5/5 |
| Precision | 99% |

**Method:** Single `search_structure(symbol="*", kind="class", project="andreasmyleus/arrow")` call.

**Result:** 72 class definitions with full metadata: file path, line ranges, and source code snippets.

**Strengths:**
- Found the nested `class Inner` in `test_edge_cases.py` that traditional grep missed (AST-based, indentation-aware).
- Each result includes file, line range, and source code preview.
- Properly categorized by kind via tree-sitter AST parsing.

**Weaknesses:**
- `MyClass` from JavaScript string literal is still returned (indexed as a class by tree-sitter when written to a `.js` temp file in the test).
- `ImportRecord` result includes the entire SQL schema string that follows the class definition (chunker over-captured the end_line range: lines 68-237 vs the actual class at lines 68-72).
- Higher token output (~4800 vs ~1240) due to included source snippets.

## Comparison

| Dimension | Traditional | Arrow | Winner |
|-----------|------------|-------|--------|
| Wall time | 7138 ms | 8720 ms | Traditional |
| Tool calls | 1 | 1 | Tie |
| Tokens consumed | ~1240 | ~4800 | Traditional |
| Classes found | 76 lines (75 unique, missed 1 nested) | 72 (found nested class) | Arrow |
| False positives | 1 (JS in string literal) | 1 (JS in string literal) + 1 over-captured chunk | Tie |
| Metadata richness | Line content only | File, lines, source preview | Arrow |
| Precision | 96% | 99% | Arrow |
| Quality | 4/5 | 5/5 | Arrow |

## Verdict

**Marginal Arrow win on completeness; Traditional wins on speed and token efficiency.**

For this enumeration-style query, both approaches work well with a single tool call. Arrow's AST-based approach correctly finds the nested `Inner` class that grep's `^class` pattern misses, and returns richer metadata (file paths, line ranges, source code). However, Arrow is slightly slower (8.7s vs 7.1s) and returns ~4x more tokens due to source snippets. The `ImportRecord` chunk over-capture (68-237 for a 5-line class) inflates token usage unnecessarily.

Traditional grep is the pragmatic choice when you just need a list of class names. Arrow is better when you need structured results with source context, or when nested/indented class definitions matter.
