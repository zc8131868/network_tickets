"""
Tier 2 — Daily Memory.

One file per calendar day consolidating all session scratchpads.
Automatically loaded at session start for same-day context.
Token-budget enforced with mid-day auto-flush to weekly when exceeded.
"""

from __future__ import annotations

from datetime import datetime, timedelta
from pathlib import Path
from typing import TYPE_CHECKING, Optional

from ..config import get_config, resolve_path, workspace_root
from ..tokens import count_tokens

if TYPE_CHECKING:
    from ..session import Session


class DailyMemory:
    """Manages the daily memory file for a given date."""

    def __init__(self, session: "Session", date: Optional[datetime] = None) -> None:
        self.session = session
        self.cfg = get_config().daily
        self.date = date or datetime.now()
        self._path = resolve_path(
            self.cfg.storage_template,
            session_id=session.session_id,
            now=self.date,
        )

    @property
    def path(self) -> Path:
        return self._path

    def exists(self) -> bool:
        return self._path.exists()

    def read(self) -> str:
        if self._path.exists():
            return self._path.read_text(encoding="utf-8")
        return ""

    def write(self, content: str) -> None:
        self._path.parent.mkdir(parents=True, exist_ok=True)
        self._path.write_text(content, encoding="utf-8")

    def token_count(self) -> int:
        return count_tokens(self.read())

    # -- Creation -------------------------------------------------------------

    def ensure_file(self) -> None:
        """Create the daily file with a header if it doesn't exist."""
        if self._path.exists():
            return
        self._path.parent.mkdir(parents=True, exist_ok=True)
        date_str = self.date.strftime("%Y-%m-%d")
        self._path.write_text(
            f"# Daily Memory — {date_str}\n",
            encoding="utf-8",
        )

    # -- Appending content ----------------------------------------------------

    def append(self, content: str) -> None:
        """Append distilled session content, enforcing the token budget."""
        self.ensure_file()

        existing = self.read()
        combined_tokens = count_tokens(existing) + count_tokens(content)

        if combined_tokens > self.cfg.auto_flush_threshold_tokens:
            self._midday_autoflush(existing)
            existing = self.read()

        new_content = existing.rstrip("\n") + "\n\n" + content.strip() + "\n"
        self.write(new_content)

    def _midday_autoflush(self, daily_content: str) -> None:
        """Compress the daily file into weekly to free budget space."""
        from ..distillation.daily_to_weekly import midday_distill
        midday_distill(self.session, daily_content)

    # -- Static helpers -------------------------------------------------------

    @staticmethod
    def path_for_date(dt: datetime) -> Path:
        """Return the daily file path for a given date."""
        cfg = get_config()
        return resolve_path(cfg.daily.storage_template, now=dt)

    @staticmethod
    def list_active(days: int = 7) -> list[Path]:
        """Return paths of daily files within the active window (last N days)."""
        memory_dir = workspace_root() / "memory"
        if not memory_dir.exists():
            return []
        cutoff = datetime.now() - timedelta(days=days)
        active: list[Path] = []
        for f in sorted(memory_dir.glob("????-??-??.md")):
            try:
                date_str = f.stem  # e.g. "2026-03-06"
                file_date = datetime.strptime(date_str, "%Y-%m-%d")
                if file_date >= cutoff:
                    active.append(f)
            except ValueError:
                continue
        return active

    @staticmethod
    def list_archivable() -> list[Path]:
        """Return daily files older than the archive threshold."""
        cfg = get_config()
        memory_dir = workspace_root() / "memory"
        if not memory_dir.exists():
            return []
        cutoff = datetime.now() - timedelta(days=cfg.daily.archive_after_days)
        archivable: list[Path] = []
        for f in sorted(memory_dir.glob("????-??-??.md")):
            try:
                date_str = f.stem
                file_date = datetime.strptime(date_str, "%Y-%m-%d")
                if file_date < cutoff:
                    archivable.append(f)
            except ValueError:
                continue
        return archivable

    @staticmethod
    def list_deletable() -> list[Path]:
        """Return archived daily files older than the deletion threshold."""
        cfg = get_config()
        archive_dir = workspace_root() / "memory" / "archive"
        if not archive_dir.exists():
            return []
        cutoff = datetime.now() - timedelta(days=cfg.daily.delete_after_days)
        deletable: list[Path] = []
        for f in sorted(archive_dir.glob("????-??-??.md")):
            try:
                date_str = f.stem
                file_date = datetime.strptime(date_str, "%Y-%m-%d")
                if file_date < cutoff:
                    deletable.append(f)
            except ValueError:
                continue
        return deletable
