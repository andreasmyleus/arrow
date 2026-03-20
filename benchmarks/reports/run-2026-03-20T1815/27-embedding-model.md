# Query 27: "Where and how is the embedding model downloaded, and what model is it?"

Category: Needle-in-haystack
Arrow tool(s) under test: get_context

## Round 1 — Traditional

**Timestamps:** start=1774009979654 end=1774009990324
**Wall time:** 10670ms
**Tool calls:** 4 (Grep x1, Glob x1, Read x1, Bash x1)
**Tokens from content:** ~940 (235 lines x ~4 tokens)
**Answer quality:** 5
**Precision:** 100%

### Answer

The embedding model is **jinaai/jina-embeddings-v2-base-code** (768-dimensional), defined as `DEFAULT_MODEL_ID` in `/Users/andreas/arrow/src/arrow/embedder.py` (line 16).

**Download mechanism:**
- The `Embedder.download_model()` method (line 49) uses `huggingface_hub.snapshot_download()` to fetch the model from HuggingFace Hub.
- It downloads only the files needed for inference: `*.onnx`, `*.json`, `*.txt`, and `tokenizer*` files (via `allow_patterns`).
- Models are cached locally at `~/.arrow/models/jinaai--jina-embeddings-v2-base-code/`. If `model.onnx` already exists there, the download is skipped.

**Loading:**
- The `load()` method (line 67) calls `download_model()` first, then creates an ONNX Runtime `InferenceSession` with the best available provider (CoreML > CUDA > CPU).
- The tokenizer is loaded from `tokenizer.json` with truncation at 8192 tokens.
- A singleton pattern via `get_embedder()` (line 228) ensures one global instance.

### Files read
- /Users/andreas/arrow/src/arrow/embedder.py (235 lines)

## Round 2 — Arrow

**Timestamps:** start=1774009992792 end=1774010002086
**Wall time:** 9294ms
**Tool calls:** 1 (get_context x1)
**Tokens from content:** 0 (Arrow-reported)
**Chunks returned:** 0
**Answer quality:** 0
**Precision:** 0%

### Answer

Arrow returned no results. It could not answer the question.

### Observations

**Traditional wins decisively.** This is a classic needle-in-haystack query where the answer lives entirely in one file (`embedder.py`). The traditional approach found it quickly via a single grep for model/download/onnx/jina keywords, then read the full file to provide a comprehensive answer.

Arrow returned zero results despite the query being about core source code (Python) that should be indexed. The `embedder.py` file contains 235 lines with the embedding model definition, download logic via `huggingface_hub.snapshot_download()`, and ONNX runtime loading — all clearly relevant. This suggests the hybrid search (BM25 + vector) failed to match the natural language query to chunks in this file, possibly because the query terms ("embedding model downloaded") don't overlap well with the code vocabulary, or the relevance threshold was too aggressive.

Traditional tools required 4 calls and ~10.7 seconds. Arrow was slightly faster in wall time (9.3s) but returned nothing useful — a case where speed is irrelevant without accuracy.
