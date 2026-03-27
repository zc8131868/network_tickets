"""
Search index management.

Maintains vector embeddings and keyword indices for all searchable memory files.
Stores the index as a JSON + numpy binary pair on disk for persistence.
"""

from __future__ import annotations

import json
import re
from collections import Counter
from dataclasses import dataclass, field
from math import log
from pathlib import Path
from typing import Optional

import numpy as np

from ..config import workspace_root
from .embeddings import embed, embed_batch


@dataclass
class IndexEntry:
    file_path: str
    chunk_text: str
    vector: Optional[np.ndarray] = field(default=None, repr=False)


class MemoryIndex:
    """In-memory search index with persistence to disk."""

    def __init__(self) -> None:
        self.entries: list[IndexEntry] = []
        self._vectors: Optional[np.ndarray] = None  # (N, dim)
        self._idf: dict[str, float] = {}
        self._index_path = workspace_root() / "memory" / ".search_index.json"
        self._vectors_path = workspace_root() / "memory" / ".search_vectors.npy"

    @property
    def size(self) -> int:
        return len(self.entries)

    # -- Building the index ---------------------------------------------------

    def build(self, file_paths: list[Path]) -> None:
        """Build/rebuild the index from a list of memory files."""
        self.entries = []
        texts: list[str] = []

        for path in file_paths:
            if not path.exists():
                continue
            content = path.read_text(encoding="utf-8")
            chunks = self._chunk_file(content)
            rel_path = str(path.relative_to(workspace_root()))
            for chunk in chunks:
                self.entries.append(IndexEntry(file_path=rel_path, chunk_text=chunk))
                texts.append(chunk)

        if texts:
            self._vectors = embed_batch(texts)
            self._build_idf(texts)
        else:
            self._vectors = None
            self._idf = {}

    def update_file(self, path: Path) -> None:
        """Re-index a single file (on create/update)."""
        rel_path = str(path.relative_to(workspace_root()))
        self.remove_file(path)

        if not path.exists():
            return

        content = path.read_text(encoding="utf-8")
        chunks = self._chunk_file(content)
        new_texts: list[str] = []

        for chunk in chunks:
            self.entries.append(IndexEntry(file_path=rel_path, chunk_text=chunk))
            new_texts.append(chunk)

        if new_texts:
            new_vectors = embed_batch(new_texts)
            if self._vectors is not None and self._vectors.shape[0] > 0:
                self._vectors = np.vstack([self._vectors, new_vectors])
            else:
                self._vectors = new_vectors

        all_texts = [e.chunk_text for e in self.entries]
        self._build_idf(all_texts)

    def remove_file(self, path: Path) -> None:
        """Remove all entries for a file from the index."""
        rel_path = str(path.relative_to(workspace_root()))
        keep_indices = [
            i for i, e in enumerate(self.entries)
            if e.file_path != rel_path
        ]
        self.entries = [self.entries[i] for i in keep_indices]
        if self._vectors is not None and keep_indices:
            self._vectors = self._vectors[keep_indices]
        elif not keep_indices:
            self._vectors = None

    # -- Chunking strategy ----------------------------------------------------

    @staticmethod
    def _chunk_file(content: str, max_chunk_tokens: int = 200) -> list[str]:
        """Split a file into chunks by H2/H3 sections.

        Falls back to paragraph splitting for unstructured content.
        """
        sections = re.split(r"(?=^##+ )", content, flags=re.MULTILINE)
        chunks: list[str] = []
        for section in sections:
            stripped = section.strip()
            if not stripped:
                continue
            words = stripped.split()
            if len(words) > max_chunk_tokens:
                for i in range(0, len(words), max_chunk_tokens):
                    sub = " ".join(words[i : i + max_chunk_tokens])
                    if sub.strip():
                        chunks.append(sub)
            else:
                chunks.append(stripped)
        return chunks if chunks else [content.strip()]

    # -- IDF computation (for BM25) -------------------------------------------

    def _build_idf(self, documents: list[str]) -> None:
        """Build IDF table from all chunks."""
        n = len(documents)
        if n == 0:
            self._idf = {}
            return
        doc_freq: Counter = Counter()
        for doc in documents:
            tokens = set(re.findall(r"[a-z0-9_]+", doc.lower()))
            doc_freq.update(tokens)
        self._idf = {
            token: log((n - freq + 0.5) / (freq + 0.5) + 1)
            for token, freq in doc_freq.items()
        }

    def bm25_score(self, query_tokens: list[str], doc_text: str, k1: float = 1.5, b: float = 0.75) -> float:
        """Compute BM25 score for a document against query tokens."""
        doc_tokens = re.findall(r"[a-z0-9_]+", doc_text.lower())
        dl = len(doc_tokens)
        if dl == 0:
            return 0.0
        avgdl = max(1, sum(len(e.chunk_text.split()) for e in self.entries) / max(1, len(self.entries)))
        tf_map = Counter(doc_tokens)
        score = 0.0
        for qt in query_tokens:
            tf = tf_map.get(qt, 0)
            idf = self._idf.get(qt, 0.0)
            numerator = tf * (k1 + 1)
            denominator = tf + k1 * (1 - b + b * dl / avgdl)
            score += idf * numerator / denominator
        return score

    # -- Persistence ----------------------------------------------------------

    def save(self) -> None:
        """Persist the index to disk."""
        self._index_path.parent.mkdir(parents=True, exist_ok=True)
        meta = [
            {"file_path": e.file_path, "chunk_text": e.chunk_text}
            for e in self.entries
        ]
        self._index_path.write_text(json.dumps(meta, ensure_ascii=False), encoding="utf-8")
        if self._vectors is not None:
            np.save(str(self._vectors_path), self._vectors)

    def load(self) -> bool:
        """Load the index from disk. Returns True on success."""
        if not self._index_path.exists():
            return False
        try:
            meta = json.loads(self._index_path.read_text(encoding="utf-8"))
            self.entries = [
                IndexEntry(file_path=m["file_path"], chunk_text=m["chunk_text"])
                for m in meta
            ]
            if self._vectors_path.exists():
                self._vectors = np.load(str(self._vectors_path))
            all_texts = [e.chunk_text for e in self.entries]
            self._build_idf(all_texts)
            return True
        except Exception:
            return False

    @property
    def vectors(self) -> Optional[np.ndarray]:
        return self._vectors
