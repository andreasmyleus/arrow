# Query 27: Embedding Model Download

**Category:** Needle-in-Haystack
**Query:** "Where and how is the embedding model downloaded, and what model is it?"
**Timestamp:** 2026-03-20T15:30

## Answer

The embedding model is `jinaai/jina-embeddings-v2-base-code` (768-dimensional), defined as `DEFAULT_MODEL_ID` in `src/arrow/embedder.py`.

It is downloaded via `huggingface_hub.snapshot_download()` in the `Embedder.download_model()` method. The download:
- Checks if `model.onnx` already exists in `~/.arrow/models/jinaai--jina-embeddings-v2-base-code/`
- If not cached, calls `snapshot_download(repo_id=self.model_id, local_dir=..., allow_patterns=["*.onnx", "*.json", "*.txt", "tokenizer*"])`
- The `load()` method calls `download_model()` first, then loads the ONNX file with `onnxruntime`

Key file: `src/arrow/embedder.py` lines 16-65.

---

## Round 1 — Traditional (Glob + Grep + Read)

| Metric | Value |
|---|---|
| Wall time | 24,170 ms |
| Tool calls | 4 (2 Grep, 1 Read, 1 timestamp) |
| Quality | 5/5 |
| Precision | 100% |

**Process:** Two Grep searches (one for model/download/onnx/jina patterns, one for huggingface/snapshot_download/onnx) immediately surfaced `embedder.py`. A Read of lines 1-70 confirmed all details: model ID, download mechanism, caching logic, and ONNX loading.

---

## Round 2 — Arrow (`get_context`)

| Metric | Value |
|---|---|
| Wall time | 6,113 ms |
| Tool calls | 1 |
| Chunks returned | 0 |
| Quality | 0/5 |
| Precision | 0% |

**Process:** `get_context` returned "No results" despite the answer existing in indexed chunks. The natural-language query failed to match any chunks above the relevance threshold.

---

## Comparison

| Metric | Traditional | Arrow |
|---|---|---|
| Wall time | 24,170 ms | 6,113 ms |
| Tool calls | 4 | 1 |
| Quality | 5/5 | 0/5 |
| Precision | 100% | 0% |
| Answer found | Yes | No |

**Winner: Traditional**

Arrow was faster in wall time but returned zero results, making it a complete miss. The natural-language query "Where and how is the embedding model downloaded" apparently did not produce sufficient similarity scores against the `embedder.py` chunks. This is a significant needle-in-haystack failure -- the answer lives in a single well-defined file (`embedder.py`) with clear keywords (download, model, ONNX, HuggingFace) that Grep found immediately.

This suggests the vector/BM25 hybrid search has a relevance threshold that is too aggressive for certain query formulations, or that the embedding model does not represent meta/self-referential queries well (asking about the embedding model using the embedding model).
