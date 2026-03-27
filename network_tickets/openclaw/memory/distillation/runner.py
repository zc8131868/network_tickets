"""
Distillation orchestrator.

Coordinates the scheduling and sequencing of all distillation runs:
  - Nightly:   daily → weekly (runs every night, configurable time)
  - Saturday:  weekly → permanent (runs Saturday night after nightly completes)
  - Cleanup:   archive moves and deletions (runs daily as part of nightly)

Can be invoked directly (for manual/catch-up runs) or via a scheduler.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from datetime import datetime
from typing import Optional

from ..archive.cleanup import CleanupReport, run_cleanup
from ..config import get_config
from ..recovery.backup import backup_file
from ..tiers.daily import DailyMemory
from ..tiers.weekly import WeeklyMemory
from .daily_to_weekly import nightly_distill
from .weekly_to_permanent import saturday_distill

logger = logging.getLogger("openclaw.memory.distillation")


@dataclass
class DistillationResult:
    nightly_ok: bool = False
    saturday_ok: Optional[bool] = None  # None means not attempted (not Saturday)
    cleanup: Optional[CleanupReport] = None
    errors: list[str] = field(default_factory=list)


def run_nightly(
    llm_callable: Optional[object] = None,
    target_date: Optional[datetime] = None,
) -> DistillationResult:
    """Run the full nightly distillation pipeline.

    Sequence:
      1. Backup weekly file
      2. Distill daily → weekly
      3. If Saturday: backup MEMORY.md, distill weekly → permanent
      4. Run archive cleanup
    """
    result = DistillationResult()
    now = target_date or datetime.now()
    cfg = get_config()

    # Step 1: Backup the weekly file before distillation
    weekly_path = WeeklyMemory.path_for_date(now)
    if weekly_path.exists():
        try:
            backup_file(weekly_path)
        except Exception as e:
            logger.warning("Failed to backup weekly file: %s", e)

    # Step 2: Nightly distillation (daily → weekly)
    try:
        from ..session import Session
        temp_session = Session()
        result.nightly_ok = nightly_distill(
            temp_session,
            llm_callable=llm_callable,
            target_date=now,
        )
        if result.nightly_ok:
            logger.info("Nightly distillation completed for %s", now.strftime("%Y-%m-%d"))
            # Apply pinning after merge
            weekly_mem = WeeklyMemory(temp_session, date=now)
            daily_files = DailyMemory.list_active(days=7)
            weekly_mem.apply_pins(daily_files)
        else:
            logger.info("No daily file found for %s, skipping nightly distillation", now.strftime("%Y-%m-%d"))
    except Exception as e:
        result.errors.append(f"Nightly distillation failed: {e}")
        logger.error("Nightly distillation failed: %s", e, exc_info=True)

    # Step 3: Saturday distillation (weekly → permanent)
    if now.strftime("%A") == cfg.permanent.distill_day:
        try:
            result.saturday_ok = saturday_distill(
                llm_callable=llm_callable,
                target_date=now,
            )
            if result.saturday_ok:
                logger.info("Saturday distillation completed for %s", now.strftime("%Y-%m-%d"))
        except Exception as e:
            result.saturday_ok = False
            result.errors.append(f"Saturday distillation failed: {e}")
            logger.error("Saturday distillation failed: %s", e, exc_info=True)

    # Step 4: Archive cleanup
    try:
        result.cleanup = run_cleanup()
        if result.cleanup.total_actions > 0:
            logger.info(
                "Cleanup: archived %d daily, %d weekly; deleted %d daily, %d weekly",
                len(result.cleanup.daily_archived),
                len(result.cleanup.weekly_archived),
                len(result.cleanup.daily_deleted),
                len(result.cleanup.weekly_deleted),
            )
    except Exception as e:
        result.errors.append(f"Cleanup failed: {e}")
        logger.error("Cleanup failed: %s", e, exc_info=True)

    return result


def run_manual_saturday(
    llm_callable: Optional[object] = None,
    target_date: Optional[datetime] = None,
) -> bool:
    """Manually trigger a Saturday distillation (for catch-up after failure)."""
    try:
        return saturday_distill(llm_callable=llm_callable, target_date=target_date)
    except Exception as e:
        logger.error("Manual Saturday distillation failed: %s", e, exc_info=True)
        return False


def schedule_check() -> dict[str, bool]:
    """Check if any scheduled distillation should run based on current time.

    Returns a dict of {task_name: should_run}.
    """
    cfg = get_config()
    now = datetime.now()
    current_time = now.strftime("%H:%M")
    current_day = now.strftime("%A")

    return {
        "nightly": current_time == cfg.weekly.distill_time,
        "saturday": (
            current_day == cfg.permanent.distill_day
            and current_time == cfg.permanent.distill_time
        ),
    }
