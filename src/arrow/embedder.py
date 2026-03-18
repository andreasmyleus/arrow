"""ONNX Runtime embedding pipeline with CodeRankEmbed or fallback models."""

from __future__ import annotations

import logging
import os
import threading
from pathlib import Path
from typing import Optional

import numpy as np

logger = logging.getLogger(__name__)

# Default model — small, fast, good for code
DEFAULT_MODEL_ID = "jinaai/jina-embeddings-v2-base-code"
DEFAULT_MODEL_DIR = Path.home() / ".arrow" / "models"

_embedder_lock = threading.Lock()
_embedder_instance: Optional["Embedder"] = None


class Embedder:
    """ONNX-based text embedder for code chunks."""

    def __init__(
        self,
        model_dir: Optional[str | Path] = None,
        model_id: str = DEFAULT_MODEL_ID,
    ):
        self.model_id = model_id
        self.model_dir = Path(model_dir or DEFAULT_MODEL_DIR) / model_id.replace("/", "--")
        self._session = None
        self._tokenizer = None
        self._ready = False
        self._embedding_dim: Optional[int] = None

    @property
    def ready(self) -> bool:
        return self._ready

    @property
    def embedding_dim(self) -> int:
        if self._embedding_dim is None:
            # Default for jina-embeddings-v2-base-code
            return 768
        return self._embedding_dim

    def download_model(self) -> Path:
        """Download model from HuggingFace Hub if not cached."""
        from huggingface_hub import snapshot_download

        onnx_path = self.model_dir / "model.onnx"
        if onnx_path.exists():
            logger.info("Model already cached at %s", self.model_dir)
            return self.model_dir

        logger.info("Downloading model %s...", self.model_id)
        snapshot_download(
            repo_id=self.model_id,
            local_dir=str(self.model_dir),
            allow_patterns=["*.onnx", "*.json", "*.txt", "tokenizer*"],
        )
        logger.info("Model downloaded to %s", self.model_dir)
        return self.model_dir

    def load(self) -> bool:
        """Load the ONNX model and tokenizer. Returns True if successful."""
        try:
            self.download_model()

            import onnxruntime as ort
            from tokenizers import Tokenizer

            # Find ONNX file
            onnx_files = list(self.model_dir.glob("**/*.onnx"))
            if not onnx_files:
                logger.error("No ONNX model found in %s", self.model_dir)
                return False

            onnx_path = onnx_files[0]
            logger.info("Loading ONNX model: %s", onnx_path)

            # Configure session options
            opts = ort.SessionOptions()
            opts.graph_optimization_level = ort.GraphOptimizationLevel.ORT_ENABLE_ALL
            opts.intra_op_num_threads = os.cpu_count() or 4

            # Select best available provider
            providers = []
            available = ort.get_available_providers()
            if "CoreMLExecutionProvider" in available:
                providers.append("CoreMLExecutionProvider")
            if "CUDAExecutionProvider" in available:
                providers.append("CUDAExecutionProvider")
            providers.append("CPUExecutionProvider")

            self._session = ort.InferenceSession(
                str(onnx_path), sess_options=opts, providers=providers
            )

            # Load tokenizer
            tokenizer_path = self.model_dir / "tokenizer.json"
            if not tokenizer_path.exists():
                # Try finding it in subdirs
                tokenizer_files = list(self.model_dir.glob("**/tokenizer.json"))
                if tokenizer_files:
                    tokenizer_path = tokenizer_files[0]
                else:
                    logger.error("No tokenizer.json found in %s", self.model_dir)
                    return False

            self._tokenizer = Tokenizer.from_file(str(tokenizer_path))
            self._tokenizer.enable_truncation(max_length=8192)
            self._tokenizer.enable_padding(length=None)

            # Determine embedding dimension with a test inference
            test_embed = self._embed_single("test")
            self._embedding_dim = len(test_embed)
            logger.info(
                "Embedder ready: dim=%d, provider=%s",
                self._embedding_dim,
                self._session.get_providers()[0],
            )

            self._ready = True
            return True

        except Exception:
            logger.exception("Failed to load embedding model")
            return False

    def _embed_single(self, text: str) -> np.ndarray:
        """Embed a single text string."""
        encoded = self._tokenizer.encode(text)
        input_ids = np.array([encoded.ids], dtype=np.int64)
        attention_mask = np.array([encoded.attention_mask], dtype=np.int64)

        if encoded.type_ids is not None:
            token_type_ids = np.array([encoded.type_ids], dtype=np.int64)
        else:
            token_type_ids = np.zeros_like(input_ids)

        inputs = {
            "input_ids": input_ids,
            "attention_mask": attention_mask,
            "token_type_ids": token_type_ids,
        }

        # Filter to only inputs the model expects
        model_inputs = {i.name for i in self._session.get_inputs()}
        inputs = {k: v for k, v in inputs.items() if k in model_inputs}

        outputs = self._session.run(None, inputs)

        # Mean pooling over token embeddings
        embeddings = outputs[0]  # (1, seq_len, dim)
        mask = attention_mask.astype(np.float32)
        mask_expanded = np.expand_dims(mask, -1)  # (1, seq_len, 1)
        summed = np.sum(embeddings * mask_expanded, axis=1)
        counts = np.clip(mask_expanded.sum(axis=1), a_min=1e-9, a_max=None)
        pooled = summed / counts

        # L2 normalize
        norm = np.linalg.norm(pooled, axis=-1, keepdims=True)
        normalized = pooled / np.clip(norm, a_min=1e-9, a_max=None)

        return normalized[0]

    def embed_batch(self, texts: list[str], batch_size: int = 32) -> np.ndarray:
        """Embed a batch of texts. Returns (N, dim) array."""
        if not self._ready:
            raise RuntimeError("Embedder not loaded. Call load() first.")

        all_embeddings = []
        for i in range(0, len(texts), batch_size):
            batch = texts[i : i + batch_size]

            # Encode batch
            encoded_batch = self._tokenizer.encode_batch(batch)

            max_len = max(len(e.ids) for e in encoded_batch)
            input_ids = np.zeros((len(batch), max_len), dtype=np.int64)
            attention_mask = np.zeros((len(batch), max_len), dtype=np.int64)
            token_type_ids = np.zeros((len(batch), max_len), dtype=np.int64)

            for j, encoded in enumerate(encoded_batch):
                seq_len = len(encoded.ids)
                input_ids[j, :seq_len] = encoded.ids
                attention_mask[j, :seq_len] = encoded.attention_mask
                if encoded.type_ids is not None:
                    token_type_ids[j, :seq_len] = encoded.type_ids

            inputs = {
                "input_ids": input_ids,
                "attention_mask": attention_mask,
                "token_type_ids": token_type_ids,
            }

            model_inputs = {i.name for i in self._session.get_inputs()}
            inputs = {k: v for k, v in inputs.items() if k in model_inputs}

            outputs = self._session.run(None, inputs)
            embeddings = outputs[0]

            # Mean pooling
            mask = attention_mask.astype(np.float32)
            mask_expanded = np.expand_dims(mask, -1)
            summed = np.sum(embeddings * mask_expanded, axis=1)
            counts = np.clip(mask_expanded.sum(axis=1), a_min=1e-9, a_max=None)
            pooled = summed / counts

            # L2 normalize
            norm = np.linalg.norm(pooled, axis=-1, keepdims=True)
            normalized = pooled / np.clip(norm, a_min=1e-9, a_max=None)

            all_embeddings.append(normalized)

        return np.vstack(all_embeddings)

    def embed_query(self, query: str) -> np.ndarray:
        """Embed a single query. Returns (dim,) array."""
        if not self._ready:
            raise RuntimeError("Embedder not loaded. Call load() first.")
        return self._embed_single(query)


def get_embedder() -> Embedder:
    """Get or create the global embedder singleton."""
    global _embedder_instance
    with _embedder_lock:
        if _embedder_instance is None:
            _embedder_instance = Embedder()
        return _embedder_instance
