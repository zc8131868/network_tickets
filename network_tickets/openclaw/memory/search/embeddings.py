"""
Embedding generation for memory search.

Uses sentence-transformers with ``all-MiniLM-L6-v2`` when available,
falls back to a simple TF-IDF bag-of-words representation.
"""

from __future__ import annotations

import hashlib
import math
import re
from collections import Counter
from typing import Optional

import numpy as np

_model = None
_BACKEND: Optional[str] = None


def _init_backend() -> str:
    global _model, _BACKEND
    if _BACKEND is not None:
        return _BACKEND
    try:
        from sentence_transformers import SentenceTransformer
        from ..config import get_config
        model_name = get_config().search.embedding_model
        _model = SentenceTransformer(model_name)
        _BACKEND = "sentence_transformers"
    except (ImportError, Exception):
        _BACKEND = "tfidf"
    return _BACKEND


def embed(text: str) -> np.ndarray:
    """Return a normalized embedding vector for *text*."""
    backend = _init_backend()
    if backend == "sentence_transformers" and _model is not None:
        vec = _model.encode(text, normalize_embeddings=True)
        return np.array(vec, dtype=np.float32)
    return _tfidf_embed(text)


def embed_batch(texts: list[str]) -> np.ndarray:
    """Embed multiple texts efficiently. Returns shape (N, dim)."""
    backend = _init_backend()
    if backend == "sentence_transformers" and _model is not None:
        vecs = _model.encode(texts, normalize_embeddings=True, batch_size=32)
        return np.array(vecs, dtype=np.float32)
    return np.array([_tfidf_embed(t) for t in texts], dtype=np.float32)


# ---------------------------------------------------------------------------
# TF-IDF fallback (dimension = 256, deterministic hashing)
# ---------------------------------------------------------------------------

_TFIDF_DIM = 256


def _tfidf_embed(text: str) -> np.ndarray:
    """Simple TF-IDF-like embedding via feature hashing (no vocabulary needed)."""
    tokens = _tokenize(text)
    if not tokens:
        return np.zeros(_TFIDF_DIM, dtype=np.float32)

    tf = Counter(tokens)
    vec = np.zeros(_TFIDF_DIM, dtype=np.float32)

    for token, count in tf.items():
        idx = int(hashlib.md5(token.encode()).hexdigest(), 16) % _TFIDF_DIM
        sign = 1 if (int(hashlib.sha1(token.encode()).hexdigest(), 16) % 2) == 0 else -1
        tf_weight = 1 + math.log(count)
        vec[idx] += sign * tf_weight

    norm = np.linalg.norm(vec)
    if norm > 0:
        vec /= norm
    return vec


def _tokenize(text: str) -> list[str]:
    """Lowercase word tokenization."""
    return re.findall(r"[a-z0-9_]+", text.lower())


def cosine_similarity(a: np.ndarray, b: np.ndarray) -> float:
    """Compute cosine similarity between two vectors."""
    dot = float(np.dot(a, b))
    norm_a = float(np.linalg.norm(a))
    norm_b = float(np.linalg.norm(b))
    if norm_a == 0 or norm_b == 0:
        return 0.0
    return dot / (norm_a * norm_b)
