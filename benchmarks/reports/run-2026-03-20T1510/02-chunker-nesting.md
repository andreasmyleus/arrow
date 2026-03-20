# Query 2: "How does the chunker handle nested classes and inner functions?"

Category: get_context — Primary retrieval
Arrow tool(s) under test: get_context

## Round 1 — Traditional
**Timestamps:** start=1774012281574 end=1774012318175
**Wall time:** 36601ms
**Tool calls:** 8 (Grep×4, Read×4)
**Tokens from content:** ~920
**Answer quality:** 5
**Precision:** 95%

### Answer
The chunker handles nested classes and inner functions through two parallel implementations that both support recursive nesting:

**1. Recursive method (`_collect_chunks`, line 348):**
- When a node matches a chunk type (e.g., `function_definition`, `class_definition`), it extracts the chunk and then recurses into that node's children to find nested definitions.
- The `parent_name` parameter tracks nesting: for a method `bar` inside class `Foo`, the scope becomes `filepath::Foo.bar`.
- Special handling for `decorated_definition`: if the current node is a decorated definition, it skips recursing into children because the inner function/class content is already captured in the decorator chunk, avoiding near-duplicate chunks (lines 383-392).

**2. Cursor-based method (`_collect_chunks_cursor`, line 403):**
- Uses a depth-first TreeCursor walk instead of recursion (more reliable across tree-sitter versions).
- Maintains a `parent_stack` and `depth_stack` to track nesting scope at each depth level.
- When a chunk node is found, its name is pushed onto the parent stack with dot-separated scope (e.g., `Outer.Inner.method`).
- The `depth_stack` is trimmed when backtracking to ensure correct scope context at each level (lines 464-467).
- Same `decorated_definition` skip logic: when encountered, it skips children entirely by jumping to the next sibling or going back up (lines 478-492).

**Scope context format:** Nested items get scope like `filepath::OuterClass.InnerClass.method`, built by concatenating parent names with dots.

**Tested in** `tests/test_edge_cases.py::TestChunkerEdgeCases::test_nested_classes` which verifies that both `Outer` and `Inner` class names are extracted from a nested class structure.

### Files read
- `/Users/andreas/arrow/src/arrow/chunker.py` (lines 80-510, ~310 lines across 3 reads)
- `/Users/andreas/arrow/tests/test_edge_cases.py` (lines 55-245, ~130 lines across 2 reads)

## Round 2 — Arrow
**Timestamps:** start=1774012320675 end=1774012330662
**Wall time:** 9987ms
**Tool calls:** 1 (get_context)
**Tokens from content:** 0 (Arrow-reported: no results)
**Chunks returned:** 0
**Answer quality:** 0
**Precision:** 0%

### Answer
Arrow returned no results for the query "How does the chunker handle nested classes and inner functions?". The tool suggested trying broader keywords or using `search_structure()` instead.

No answer could be produced from Arrow alone.

### Observations
**Traditional won decisively.** Arrow returned zero results for this query, making it completely unable to answer the question. The traditional approach required 8 tool calls and ~37 seconds but produced a comprehensive, high-quality answer covering both chunker implementations, the scope tracking mechanism, decorated definition handling, and relevant test coverage.

The failure mode is notable: Arrow has 835 chunks indexed for this project, and the query is directly about one of Arrow's own core files (`chunker.py`). The relevant functions (`_collect_chunks`, `_collect_chunks_cursor`) contain keywords like "nested", "children", "parent", and "depth" that should be searchable. The natural language query may have failed to match because the code comments use phrases like "Recurse into children for nested definitions" rather than exact query terms, or the relevance threshold may be too aggressive for this type of conceptual/behavioral query.

This is a case where a conceptual "how does X work" query about internal behavior fails under Arrow's relevance-first retrieval, while traditional grep-based exploration easily locates the relevant code.
