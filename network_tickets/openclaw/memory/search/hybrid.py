"""
Hybrid search engine — combines vector similarity with BM25 text matching.

Search priority order:
  1. Instant memory  — already in context (no search needed)
  2. Daily (today)   — already in context (no search needed)
  3. Weekly memory   — hybrid search on demand
  4. MEMORY.md       — already in context (no search needed)
  5. Entity files    — hybrid search when entity mentioned
  6. Archived files  — hybrid search on explicit query
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from pathlib import Path
from typing import Optional

import numpy as np

from ..config import get_config, workspace_root
from .embeddings import cosine_similarity, embed
from .index import MemoryIndex


@dataclass
class SearchResult:
    file_path: str
    chunk_text: str
    score: float
    vector_score: float
    text_score: float


class HybridSearch:
    """Hybrid (vector + BM25) search over memory files."""

    def __init__(self, index: Optional[MemoryIndex] = None) -> None:
        self.cfg = get_config().search
        self.index = index or MemoryIndex()

    def search(
        self,
        query: str,
        top_k: int = 5,
        file_filter: Optional[list[str]] = None,
    ) -> list[SearchResult]:
        """Search across indexed memory files.

        Args:
            query: The search query string.
            top_k: Number of results to return.
            file_filter: Optional list of relative file path prefixes to restrict search.

        Returns:
            Sorted list of SearchResult (highest score first).
        """
        if self.index.size == 0:
            return []

        query_vec = embed(query)
        query_tokens = re.findall(r"[a-z0-9_]+", query.lower())

        candidate_count = top_k * self.cfg.candidate_multiplier
        candidates: list[SearchResult] = []

        for i, entry in enumerate(self.index.entries):
            if file_filter:
                if not any(entry.file_path.startswith(prefix) for prefix in file_filter):
                    continue

            # Vector similarity
            if self.index.vectors is not None and i < self.index.vectors.shape[0]:
                vec_score = cosine_similarity(query_vec, self.index.vectors[i])
            else:
                vec_score = 0.0

            # BM25 text score
            text_score = self.index.bm25_score(query_tokens, entry.chunk_text)

            combined = (
                self.cfg.vector_weight * vec_score
                + self.cfg.text_weight * _normalize_bm25(text_score)
            )

            candidates.append(SearchResult(
                file_path=entry.file_path,
                chunk_text=entry.chunk_text,
                score=combined,
                vector_score=vec_score,
                text_score=text_score,
            ))

        candidates.sort(key=lambda r: r.score, reverse=True)
        return candidates[:top_k]

    # -- Convenience methods --------------------------------------------------

    def search_weekly(self, query: str, top_k: int = 5) -> list[SearchResult]:
        """Search only weekly memory files."""
        return self.search(query, top_k, file_filter=["memory/week-"])

    def search_entities(self, query: str, top_k: int = 5) -> list[SearchResult]:
        """Search only entity files."""
        return self.search(query, top_k, file_filter=["memory/entities/"])

    def search_archive(self, query: str, top_k: int = 5) -> list[SearchResult]:
        """Search only archived files."""
        return self.search(query, top_k, file_filter=["memory/archive/"])

    def search_all(self, query: str, top_k: int = 5) -> list[SearchResult]:
        """Search across all indexed files."""
        return self.search(query, top_k)

    # -- Index lifecycle helpers ----------------------------------------------

    def build_index(self) -> None:
        """Build the search index from all searchable memory files."""
        paths = self._collect_searchable_files()
        self.index.build(paths)
        self.index.save()

    def refresh_file(self, path: Path) -> None:
        """Update the index for a single changed file."""
        self.index.update_file(path)
        self.index.save()

    def load_index(self) -> bool:
        """Load persisted index from disk."""
        return self.index.load()

    @staticmethod
    def _collect_searchable_files() -> list[Path]:
        """Collect all files that should be indexed (tiers 3-6)."""
        root = workspace_root()
        files: list[Path] = []

        # Weekly files
        memory_dir = root / "memory"
        if memory_dir.exists():
            files.extend(memory_dir.glob("week-????-W??.md"))

        # Entity files
        entity_dir = root / "memory" / "entities"
        if entity_dir.exists():
            files.extend(entity_dir.glob("*.md"))

        # Archived files
        archive_dir = root / "memory" / "archive"
        if archive_dir.exists():
            files.extend(archive_dir.glob("*.md"))

        return sorted(files)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _normalize_bm25(score: float, scale: float = 10.0) -> float:
    """Normalize BM25 score to roughly [0, 1] range for combination with cosine."""
    if score <= 0:
        return 0.0
    return min(1.0, score / scale)
