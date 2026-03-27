"""
Archive management — scheduled moves and deletions.

Policies:
  Daily files:  day +7  → move to archive/    day +30 → delete from archive/
  Weekly files: month +1 → move to archive/   month +3 → delete from archive/
"""

from __future__ import annotations

import shutil
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Optional

from ..config import workspace_root
from ..tiers.daily import DailyMemory
from ..tiers.weekly import WeeklyMemory


@dataclass
class CleanupReport:
    """Summary of a cleanup run."""
    daily_archived: list[str]
    daily_deleted: list[str]
    weekly_archived: list[str]
    weekly_deleted: list[str]

    @property
    def total_actions(self) -> int:
        return (
            len(self.daily_archived)
            + len(self.daily_deleted)
            + len(self.weekly_archived)
            + len(self.weekly_deleted)
        )


def run_cleanup(dry_run: bool = False) -> CleanupReport:
    """Execute all archive and deletion policies.

    Args:
        dry_run: If True, report what *would* happen without actually moving/deleting.

    Returns:
        CleanupReport summarizing all actions taken.
    """
    archive_dir = workspace_root() / "memory" / "archive"
    archive_dir.mkdir(parents=True, exist_ok=True)

    report = CleanupReport(
        daily_archived=[],
        daily_deleted=[],
        weekly_archived=[],
        weekly_deleted=[],
    )

    # -- Daily: archive (day +7) --
    for path in DailyMemory.list_archivable():
        dest = archive_dir / path.name
        report.daily_archived.append(str(path.name))
        if not dry_run:
            shutil.move(str(path), str(dest))

    # -- Daily: delete from archive (day +30) --
    for path in DailyMemory.list_deletable():
        report.daily_deleted.append(str(path.name))
        if not dry_run:
            path.unlink(missing_ok=True)

    # -- Weekly: archive (month +1) --
    for path in WeeklyMemory.list_archivable():
        dest = archive_dir / path.name
        report.weekly_archived.append(str(path.name))
        if not dry_run:
            shutil.move(str(path), str(dest))

    # -- Weekly: delete from archive (month +3) --
    for path in WeeklyMemory.list_deletable():
        report.weekly_deleted.append(str(path.name))
        if not dry_run:
            path.unlink(missing_ok=True)

    return report
