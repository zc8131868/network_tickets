"""
Tier 1 — Instant Memory.

Session-scoped scratchpad that captures actionable context and flushes it
to daily memory before compaction, at session end, or on token threshold.
"""

from __future__ import annotations

import re
from datetime import datetime
from enum import Enum
from pathlib import Path
from typing import TYPE_CHECKING, Optional

from ..config import get_config
from ..tokens import BUDGET_INSTANT, count_tokens

if TYPE_CHECKING:
    from ..session import Session


# ---------------------------------------------------------------------------
# Entry categories (map to Markdown headings in the instant file)
# ---------------------------------------------------------------------------

class Category(str, Enum):
    DECISIONS = "Decisions"
    FACTS = "Facts Learned"
    ERRORS = "Errors Resolved"
    CORRECTIONS = "Corrections"
    OPEN_QUESTIONS = "Open Questions"


# ---------------------------------------------------------------------------
# Capture / skip classifier
# ---------------------------------------------------------------------------

# Patterns that indicate skippable content
_SKIP_PATTERNS: list[re.Pattern[str]] = [
    re.compile(r"^\s*(ls|cd|pwd|git\s+status|git\s+log|cat|head|tail)\b", re.IGNORECASE),
    re.compile(r"^(hi|hello|hey|thanks|thank you|ok|okay|sure|np|no problem)", re.IGNORECASE),
    re.compile(r"^(reading|read) file", re.IGNORECASE),
]


def should_capture(text: str) -> bool:
    """Return True if the text represents meaningful content worth storing."""
    stripped = text.strip()
    if not stripped:
        return False
    for pat in _SKIP_PATTERNS:
        if pat.search(stripped):
            return False
    return True


# ---------------------------------------------------------------------------
# InstantMemory
# ---------------------------------------------------------------------------

class InstantMemory:
    """Manages a single session's instant memory file."""

    def __init__(self, session: "Session") -> None:
        self.session = session
        self.cfg = get_config().instant
        self._path: Path = session.instant_path
        self._created = False

    @property
    def path(self) -> Path:
        return self._path

    def exists(self) -> bool:
        return self._path.exists()

    def read(self) -> str:
        if self._path.exists():
            return self._path.read_text(encoding="utf-8")
        return ""

    def token_count(self) -> int:
        return count_tokens(self.read())

    # -- Writing entries ------------------------------------------------------

    def add_entry(self, category: Category, text: str, pin: bool = False) -> None:
        """Append a bullet point under *category* in the instant file.

        If *pin* is True the entry is tagged [PIN] for weekly retention.
        """
        if not should_capture(text):
            return

        self._ensure_file()

        prefix = "[PIN] " if pin else ""
        bullet = f"- {prefix}{text.strip()}\n"

        content = self.read()
        heading = f"### {category.value}"

        if heading in content:
            # Append under existing heading
            pos = content.index(heading) + len(heading)
            next_heading = content.find("\n### ", pos)
            if next_heading == -1:
                content = content.rstrip("\n") + "\n" + bullet
            else:
                content = content[:next_heading] + bullet + content[next_heading:]
        else:
            content = content.rstrip("\n") + f"\n\n{heading}\n{bullet}"

        self._write(content)
        self._check_threshold()

    def add_decision(self, text: str, pin: bool = False) -> None:
        self.add_entry(Category.DECISIONS, text, pin)

    def add_fact(self, text: str, pin: bool = False) -> None:
        self.add_entry(Category.FACTS, text, pin)

    def add_error(self, text: str) -> None:
        self.add_entry(Category.ERRORS, text)

    def add_correction(self, text: str) -> None:
        self.add_entry(Category.CORRECTIONS, text, pin=True)

    def add_open_question(self, text: str) -> None:
        self.add_entry(Category.OPEN_QUESTIONS, text)

    # -- File management ------------------------------------------------------

    def _ensure_file(self) -> None:
        """Create the instant file with its header if it doesn't exist."""
        if self._created or self._path.exists():
            return
        self._path.parent.mkdir(parents=True, exist_ok=True)
        header = (
            f"# Instant Memory — Session {self.session.session_id}\n\n"
            f"## Timestamp: {datetime.now().isoformat()}Z\n"
        )
        self._path.write_text(header, encoding="utf-8")
        self._created = True

    def _write(self, content: str) -> None:
        self._path.write_text(content, encoding="utf-8")

    def delete_file(self) -> None:
        """Remove the instant file (called after final flush on session end)."""
        if self._path.exists():
            self._path.unlink()

    # -- Flush triggers -------------------------------------------------------

    def _check_threshold(self) -> None:
        """Auto-flush when instant memory exceeds its token budget."""
        if self.token_count() > (self.cfg.max_tokens or BUDGET_INSTANT):
            self.flush(reason="threshold")

    def flush(self, reason: str = "manual") -> bool:
        """Flush instant memory to daily memory.

        Returns True if content was flushed, False if there was nothing to flush.
        """
        content = self.read()
        if not content.strip():
            return False

        from ..distillation.instant_to_daily import flush_instant_to_daily
        success = flush_instant_to_daily(self.session, content)

        if success:
            if reason == "session_end":
                self.delete_file()
            else:
                # Mid-session flush (compact / threshold): clear file, keep header
                header = (
                    f"# Instant Memory — Session {self.session.session_id}\n\n"
                    f"## Timestamp: {datetime.now().isoformat()}Z\n"
                )
                self._write(header)
        return success
