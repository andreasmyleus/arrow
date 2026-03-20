# Query 27: Embedding Model Download

**Query:** "Where and how is the embedding model downloaded, and what model is it?"
**Category:** get_context — Needle
**Arrow tool under test:** get_context

---

## Expected Answer

The embedding model is `jinaai/jina-embeddings-v2-base-code` (768-dimensional). It is downloaded in `src/arrow/embedder.py` via the `download_model()` method of the `Embedder` class, which calls `huggingface_hub.snapshot_download()`. The model files (ONNX weights, tokenizer JSON, etc.) are cached at `~/.arrow/models/jinaai--jina-embeddings-v2-base-code`. The download is triggered lazily when `load()` is called (which calls `download_model()` first), and it skips re-downloading if `model.onnx` already exists in the cache directory.

---

## Round 1 — Traditional (Glob + Grep + Read)

| Metric | Value |
|---|---|
| Wall time | 9,540 ms |
| Tool calls | 4 (2 Grep + 1 Read + 1 Glob implicit) |
| Estimated tokens | ~4,500 (file read ~3,800 + search results ~700) |
| Quality | 5/5 |
| Precision | 100% |

### Process
1. Grep for `model.*download|onnx|jina|embedding.*model` and `huggingface|snapshot_download` — both pointed to `embedder.py`.
2. Read `embedder.py` (235 lines) — found everything: model ID, download mechanism, cache path, ONNX runtime loading, embedding dimension.

### Answer
- **Model:** `jinaai/jina-embeddings-v2-base-code` (line 16)
- **Download method:** `huggingface_hub.snapshot_download()` called in `Embedder.download_model()` (lines 49-65)
- **Cache location:** `~/.arrow/models/<model_id>` (line 17, 32)
- **Triggered by:** `Embedder.load()` which calls `download_model()` first (line 70)
- **Skip condition:** Skips if `model.onnx` already exists (line 54)

---

## Round 2 — Arrow (get_context)

| Metric | Value |
|---|---|
| Wall time | 10,199 ms |
| Tool calls | 1 |
| Tokens returned | 0 |
| Chunks returned | 0 |
| Quality | 1/5 |
| Precision | 0% |

### Process
1. Called `get_context(query="Where and how is the embedding model downloaded, and what model is it?", project="andreasmyleus/arrow")`.
2. Received **no results** — the tool reported "No results" despite the codebase being indexed (63 files, 835 chunks).

### Answer
No answer could be derived from Arrow's response. The tool failed to surface any chunks from `embedder.py`.

---

## Comparison

| Metric | Traditional | Arrow |
|---|---|---|
| Wall time | 9,540 ms | 10,199 ms |
| Tool calls | 4 | 1 |
| Tokens consumed | ~4,500 | ~50 |
| Quality | 5/5 | 1/5 |
| Precision | 100% | 0% |
| Winner | **Traditional** | |

## Notes

- **Arrow failure:** `get_context` returned zero results for a straightforward needle query about embedding model downloads. The relevant code in `embedder.py` contains obvious keywords (`download_model`, `huggingface_hub`, `snapshot_download`, `jina-embeddings-v2-base-code`) that should have matched. This suggests the relevance threshold may be too aggressive, or the query's natural-language phrasing did not match the BM25/vector representation of the `embedder.py` chunks.
- Traditional approach was efficient — two targeted greps immediately narrowed to the single relevant file, and one read provided the complete answer.
- This is a clear regression case for Arrow: a single-file needle query that the tool should handle well but completely missed.
