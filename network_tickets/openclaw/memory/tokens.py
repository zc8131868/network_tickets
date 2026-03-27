"""
Token counting utility used by every tier to enforce budgets.

Supports two backends:
  - tiktoken (accurate, requires the library)
  - heuristic (fast, no dependencies: word_count * 1.3)
"""

from __future__ import annotations

import re
from typing import Optional

_tokenizer = None
_BACKEND: Optional[str] = None


def _init_backend() -> str:
    """Lazy-initialize the token counting backend."""
    global _tokenizer, _BACKEND
    if _BACKEND is not None:
        return _BACKEND
    try:
        import tiktoken
        _tokenizer = tiktoken.get_encoding("cl100k_base")
        _BACKEND = "tiktoken"
    except (ImportError, Exception):
        _BACKEND = "heuristic"
    return _BACKEND


def count_tokens(text: str) -> int:
    """Return the estimated token count for *text*."""
    if not text:
        return 0
    backend = _init_backend()
    if backend == "tiktoken" and _tokenizer is not None:
        return len(_tokenizer.encode(text))
    return _heuristic_count(text)


def _heuristic_count(text: str) -> int:
    """Word-count * 1.3 heuristic — reasonable for English + code mixed content."""
    words = re.findall(r"\S+", text)
    return int(len(words) * 1.3)


# -- Tier budget constants (tokens) ------------------------------------------

BUDGET_INSTANT = 1_500
BUDGET_DAILY = 3_000
BUDGET_WEEKLY = 2_000
BUDGET_PERMANENT = 3_000
BUDGET_CARRY_FORWARD = 500
