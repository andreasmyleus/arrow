# Benchmark 12: Find All Classes in the Codebase

**Category:** search_structure — AST symbol lookup
**Date:** 2026-03-20T15:30
**Codebase:** /Users/andreas/arrow (andreasmyleus/arrow)

---

## Round 1 — Traditional (Glob + Grep + Read)

| Metric | Value |
|---|---|
| Start | 1774007830207 |
| End | 1774007836844 |
| Duration | 6637 ms |
| Tool calls | 1 (Grep) |
| Classes found | 76 |
| Quality | 5/5 |
| Precision | 95% |

### Method
Single `Grep` call with pattern `^class \w+` across all Python files.

### Results (76 classes)
**Source classes (19):**
- `VectorStore` (vector_store.py)
- `_IndexHandler`, `FileWatcher` (watcher.py)
- `Embedder` (embedder.py)
- `Chunk` (chunker.py)
- `SearchResult`, `QueryClassification`, `HybridSearcher` (search.py)
- `SearchConfig`, `IndexConfig`, `ArrowConfig` (config.py)
- `ProjectRecord`, `FileRecord`, `ChunkRecord`, `SymbolRecord`, `ImportRecord`, `Storage` (storage.py)
- `Indexer` (indexer.py)

**Test classes (55):**
- TestVectorStore, TestFileWatcher, TestAutoWarm, TestWhatBreaksIfIChange,
  TestQueryAwareBudget, TestChunkerEdgeCases, TestDiscoveryEdgeCases,
  TestStorageEdgeCases, TestIndexerEdgeCases, TestSearchEdgeCases,
  TestLongTermMemory, TestParseRemoteUrl, TestIsGitRepo, TestGetGitInfo,
  TestHasNewCommits, TestResolveCommit, TestListFilesAtCommit,
  TestGetFileAtCommit, TestGetCommitInfo, TestMergeBase,
  TestChangedFilesBetween, TestDeadCode, TestMultiLangImports,
  TestServerTools, TestMultiProject, TestProjectAutoDetection,
  TestHasher, TestChunker, TestDiscovery, TestStorage, TestIndexer,
  TestSearch, TestQueryConceptExtraction, TestFilenameMatchBoost,
  TestExportImport, TestConversationContext, TestSearchRegexOutput,
  TestSearchRegexHelpers, TestNonCodeDetection, TestTomlChunking,
  TestYamlChunking, TestJsonChunking, TestMarkdownChunking,
  TestDockerfileChunking, TestNonCodeIndexing, TestFilterByRelevance,
  TestSearchPrecision, TestFilterByRelevanceEdgeCases, TestFrecency,
  TestGetTestsFor, TestStaleIndex, TestResolveSymbol, TestToolAnalytics,
  TestGetDiffContext, TestDocQueryDetection, TestDocPathDetection,
  TestDocSearchRanking, TestStorageNewMethods

**Inline/embedded classes (2):**
- `MyClass` (JS class in test string, test_edge_cases.py)

### Notes
- Simple, complete, one tool call. Grep handles "find all X" patterns very well.
- Minor false positive: `MyClass` is a JavaScript class inside a Python test string literal, not a real Python class. Hence 95% precision.

---

## Round 2 — Arrow (search_structure)

| Metric | Value |
|---|---|
| Start | 1774007840202 |
| End | 1774007872599 |
| Duration | 32397 ms |
| Tool calls | 27 (one per letter A-Z plus `_`) |
| Classes found | ~39 (incomplete) |
| Quality | 2/5 |
| Precision | 100% |

### Method
`search_structure` does not support wildcard or "list all" queries. Empty string returns an error ("symbol is required"), and `*` returns empty results. The workaround was to issue 27 prefix queries (A-Z, `_`), one per starting letter.

### Results (~39 classes found, ~37 missing)
**Found (source classes: 19/19 complete):**
ArrowConfig, Chunk, ChunkRecord, Embedder, FileRecord, FileWatcher,
HybridSearcher, ImportRecord, IndexConfig, Indexer, Inner, MyClass,
ProjectRecord, QueryClassification, SearchConfig, SearchResult,
Storage, SymbolRecord, VectorStore

**Found (test classes: 20/55 — truncated):**
TestAutoWarm, TestChangedFilesBetween, TestChunker, TestChunkerEdgeCases,
TestConversationContext, TestDeadCode, TestDiscovery, TestDiscoveryEdgeCases,
TestDocPathDetection, TestDocQueryDetection, TestDocSearchRanking,
TestDockerfileChunking, TestExportImport, TestFileWatcher,
TestFilenameMatchBoost, TestFilterByRelevance, TestFilterByRelevanceEdgeCases,
TestFrecency, TestGetCommitInfo, TestGetDiffContext

**Missing (~37 classes):**
The `T` prefix query was truncated at 20 results. All remaining Test* classes were lost:
TestGetFileAtCommit, TestGetGitInfo, TestGetTestsFor, TestHasNewCommits,
TestHasher, TestImpactAnalysis, TestIndexer, TestIndexerEdgeCases,
TestIsGitRepo, TestJsonChunking, TestListFilesAtCommit,
TestLongTermMemory, TestMarkdownChunking, TestMergeBase,
TestMultiLangImports, TestMultiProject, TestNonCodeDetection,
TestNonCodeIndexing, TestParseRemoteUrl, TestProjectAutoDetection,
TestQueryAwareBudget, TestQueryConceptExtraction, TestResolveCommit,
TestResolveSymbol, TestSearch, TestSearchEdgeCases, TestSearchPrecision,
TestSearchRegexHelpers, TestSearchRegexOutput, TestServerTools,
TestStaleIndex, TestStorage, TestStorageEdgeCases, TestStorageNewMethods,
TestSymbolResolution, TestTomlChunking, TestToolAnalytics,
TestVectorStore, TestWhatBreaksIfIChange, TestYamlChunking,
_IndexHandler

### Enrichment
Arrow returns source code with each result, including line ranges and docstrings. This is richer than Grep's single-line output.

### Notes
- `search_structure` is designed for targeted symbol lookup, not enumeration.
- No wildcard/glob support means "find all classes" requires brute-force prefix iteration.
- The 20-result limit per query causes silent truncation for the `T` prefix (55 Test* classes).
- 27 MCP tool calls is extremely expensive for this use case.

---

## Comparison

| Dimension | Traditional | Arrow |
|---|---|---|
| Duration | 6637 ms | 32397 ms |
| Tool calls | 1 | 27 |
| Classes found | 76 | ~39 |
| Completeness | 100% | ~51% |
| Quality | 5/5 | 2/5 |
| Precision | 95% | 100% |
| Source included | Line only | Full source |

### Verdict
**Traditional wins decisively.** This query — "find all classes" — is a pure enumeration task. Grep handles it in a single call with complete results. Arrow's `search_structure` is not designed for exhaustive enumeration: it requires a symbol prefix, has a 20-result limit per query, and offers no wildcard support. The workaround of iterating through all letter prefixes is expensive (27 tool calls), slow (5x slower), and still incomplete (misses ~37 classes due to truncation on the `T` prefix).

Arrow's advantage — returning full source code per result — is irrelevant when the goal is just listing all classes. For targeted lookups ("find the Storage class"), `search_structure` excels. For enumeration, Grep is the correct tool.

**Winner: Traditional (Grep)**
**Margin: Large** — fewer calls, faster, complete results.
