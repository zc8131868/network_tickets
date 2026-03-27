"""
Tier 3 — Weekly Memory.

One file per ISO calendar week.  Distilled patterns, recurring themes, and
significant decisions.  Acts as a buffer between daily context and permanent.

Includes the pinning mechanism to protect important-but-infrequent facts.
"""

from __future__ import annotations

import re
from collections import Counter
from datetime import datetime, timedelta
from pathlib import Path
from typing import TYPE_CHECKING, Optional

from ..config import get_config, resolve_path, workspace_root
from ..tokens import count_tokens

if TYPE_CHECKING:
    from ..session import Session


class WeeklyMemory:
    """Manages the weekly memory file for a given ISO week."""

    def __init__(self, session: "Session", date: Optional[datetime] = None) -> None:
        self.session = session
        self.cfg = get_config().weekly
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
        """Create the weekly file with a skeleton if it doesn't exist."""
        if self._path.exists():
            return
        iso_year, iso_week, _ = self.date.isocalendar()
        week_label = f"{iso_year}-W{iso_week:02d}"
        month_day = self.date.strftime("%b %-d")
        self._path.parent.mkdir(parents=True, exist_ok=True)
        self._path.write_text(
            f"# Weekly Memory — {week_label} ({month_day})\n\n"
            "## Key Decisions\n\n"
            "## Patterns Observed\n\n"
            "## Corrections [PINNED]\n\n"
            "## Technical Context\n\n"
            "## Unresolved\n",
            encoding="utf-8",
        )

    # -- Pinning mechanism ----------------------------------------------------

    def apply_pins(self, daily_files_this_week: list[Path]) -> str:
        """Scan weekly content and auto-pin items that meet pin criteria.

        Pin rules:
          1. Explicit [PIN] tag — already in the text, no action needed.
          2. Auto-pin corrections — items under "## Corrections" heading.
          3. Auto-pin patterns — items appearing in 3+ daily files this week.

        Returns the updated weekly content with new [PINNED] tags applied.
        """
        content = self.read()
        if not content:
            return content

        # Rule 2: Auto-pin corrections (mark the section heading)
        content = re.sub(
            r"^(## Corrections)\s*$",
            r"\1 [PINNED]",
            content,
            flags=re.MULTILINE,
        )

        # Rule 3: Count bullet occurrences across daily files
        if len(daily_files_this_week) >= self.cfg.pin_after_occurrences:
            bullet_counts = self._count_cross_day_bullets(daily_files_this_week)
            threshold = self.cfg.pin_after_occurrences

            for bullet_text, count in bullet_counts.items():
                if count >= threshold and bullet_text in content:
                    pinned_bullet = bullet_text.replace("- ", "- [PINNED] ", 1)
                    if "[PINNED]" not in bullet_text:
                        content = content.replace(bullet_text, pinned_bullet, 1)

        self.write(content)
        return content

    @staticmethod
    def _count_cross_day_bullets(daily_files: list[Path]) -> Counter:
        """Count how many different daily files each bullet point appears in."""
        bullet_counter: Counter = Counter()
        for path in daily_files:
            if not path.exists():
                continue
            text = path.read_text(encoding="utf-8")
            seen_in_file: set[str] = set()
            for line in text.splitlines():
                stripped = line.strip()
                if stripped.startswith("- "):
                    normalized = re.sub(r"\[PIN(NED)?\]\s*", "", stripped)
                    if normalized not in seen_in_file:
                        seen_in_file.add(normalized)
                        bullet_counter[stripped] += 1
        return bullet_counter

    # -- Static helpers -------------------------------------------------------

    @staticmethod
    def path_for_date(dt: datetime) -> Path:
        cfg = get_config()
        return resolve_path(cfg.weekly.storage_template, now=dt)

    @staticmethod
    def list_active() -> list[Path]:
        """Return weekly files within the current month (active window)."""
        memory_dir = workspace_root() / "memory"
        if not memory_dir.exists():
            return []
        now = datetime.now()
        current_year = now.year
        current_month = now.month

        active: list[Path] = []
        for f in sorted(memory_dir.glob("week-????-W??.md")):
            match = re.match(r"week-(\d{4})-W(\d{2})", f.stem)
            if not match:
                continue
            year = int(match.group(1))
            week = int(match.group(2))
            # Approximate: keep if same year and within ~4 weeks
            file_date = datetime.strptime(f"{year}-W{week:02d}-1", "%G-W%V-%u")
            if (now - file_date).days <= 31:
                active.append(f)
        return active

    @staticmethod
    def list_archivable() -> list[Path]:
        """Return weekly files older than 1 month."""
        memory_dir = workspace_root() / "memory"
        if not memory_dir.exists():
            return []
        cutoff = datetime.now() - timedelta(days=31)
        archivable: list[Path] = []
        for f in sorted(memory_dir.glob("week-????-W??.md")):
            match = re.match(r"week-(\d{4})-W(\d{2})", f.stem)
            if not match:
                continue
            year = int(match.group(1))
            week = int(match.group(2))
            try:
                file_date = datetime.strptime(f"{year}-W{week:02d}-1", "%G-W%V-%u")
                if file_date < cutoff:
                    archivable.append(f)
            except ValueError:
                continue
        return archivable

    @staticmethod
    def list_deletable() -> list[Path]:
        """Return archived weekly files older than 3 months."""
        archive_dir = workspace_root() / "memory" / "archive"
        if not archive_dir.exists():
            return []
        cutoff = datetime.now() - timedelta(days=92)
        deletable: list[Path] = []
        for f in sorted(archive_dir.glob("week-????-W??.md")):
            match = re.match(r"week-(\d{4})-W(\d{2})", f.stem)
            if not match:
                continue
            year = int(match.group(1))
            week = int(match.group(2))
            try:
                file_date = datetime.strptime(f"{year}-W{week:02d}-1", "%G-W%V-%u")
                if file_date < cutoff:
                    deletable.append(f)
            except ValueError:
                continue
        return deletable
