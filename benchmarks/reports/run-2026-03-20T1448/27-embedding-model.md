# Query 27: Embedding Model Download

**Category:** Needle
**Query:** "Where and how is the embedding model downloaded, and what model is it?"
**Arrow tool(s) under test:** `get_context`

## Expected Answer

The embedding model is **jinaai/jina-embeddings-v2-base-code** (768-dim). It is downloaded via `huggingface_hub.snapshot_download()` in the `Embedder.download_model()` method in `src/arrow/embedder.py`. The download is triggered lazily by `Embedder.load()`, caches to `~/.arrow/models/jinaai--jina-embeddings-v2-base-code/`, and filters to only `*.onnx`, `*.json`, `*.txt`, and `tokenizer*` files. The model is then loaded with ONNX Runtime.

---

## Round 1 — Traditional (Glob + Grep + Read)

| Metric | Value |
|---|---|
| Wall time | 9,787 ms |
| Tool calls | 5 (3 Grep + 1 Read + 1 Bash) |
| Tokens (approx.) | ~400 |
| Quality | 5/5 |
| Precision | 95% |

**Steps:**
1. Grepped for `model.*download|onnx.*model` patterns — found `embedder.py` immediately.
2. Grepped for `jina|embedding.*model|ONNX` — confirmed model identity and ONNX usage.
3. Grepped for `huggingface|snapshot_download` — confirmed download mechanism.
4. Read `embedder.py` lines 1-100 — got full picture: model ID, download method, cache path, load flow.

**Answer quality:** Complete answer found. Model identity (`jinaai/jina-embeddings-v2-base-code`), download mechanism (`huggingface_hub.snapshot_download`), cache location (`~/.arrow/models/`), and ONNX loading were all clearly visible.

---

## Round 2 — Arrow (`get_context`)

| Metric | Value |
|---|---|
| Wall time | 8,860 ms |
| Tool calls | 1 |
| Tokens returned | 0 |
| Chunks returned | 0 |
| Quality | 0/5 |
| Precision | 0% |

**Result:** `get_context` returned **no results** for this query. The relevance threshold filtered out all chunks despite the codebase having 1,427 indexed chunks and `embedder.py` being the exact file containing the answer.

**Likely cause:** The query is natural-language heavy ("Where and how is the embedding model downloaded") and the target code uses technical identifiers (`snapshot_download`, `DEFAULT_MODEL_ID`, `jinaai/jina-embeddings-v2-base-code`). The semantic/BM25 hybrid search likely did not score `embedder.py` chunks above the relevance cutoff, possibly because keyword overlap is weak — the code says "download_model" and "snapshot_download" rather than phrasing that closely matches the query.

---

## Comparison

| Dimension | Traditional | Arrow |
|---|---|---|
| Wall time | 9,787 ms | 8,860 ms |
| Tool calls | 5 | 1 |
| Quality | 5/5 | 0/5 |
| Precision | 95% | 0% |
| Tokens consumed | ~400 | ~0 |

**Winner: Traditional**

Arrow returned zero results for a straightforward needle query about a specific subsystem. Traditional search found the answer on the first grep. This is a significant failure case for `get_context` — the query is reasonable and the answer lives in a single, well-named file. The aggressive relevance threshold appears to be too strict for natural-language questions about implementation details.
