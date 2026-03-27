"""
Flush logic: Instant → Daily memory.

Distills the session scratchpad and appends the result to today's daily file.
Supports both LLM-based distillation and a direct-copy fallback.
"""

from __future__ import annotations

import re
from datetime import datetime
from typing import TYPE_CHECKING, Optional

from ..config import get_config, resolve_path
from ..tokens import count_tokens
from .prompts import INSTANT_TO_DAILY

if TYPE_CHECKING:
    from ..session import Session


def flush_instant_to_daily(
    session: "Session",
    instant_content: str,
    llm_callable: Optional[object] = None,
) -> bool:
    """Distill instant memory and append to today's daily file.

    Args:
        session: The active session.
        instant_content: Raw content from the instant memory file.
        llm_callable: Optional async/sync callable(prompt: str) -> str.
                      If None, uses direct-copy fallback (no compression).

    Returns:
        True on success.
    """
    if not instant_content.strip():
        return False

    cfg = get_config()
    daily_path = resolve_path(
        cfg.daily.storage_template,
        session_id=session.session_id,
        now=datetime.now(),
    )
    daily_path.parent.mkdir(parents=True, exist_ok=True)

    # Distill via LLM or fall back to direct copy
    if llm_callable is not None:
        prompt = INSTANT_TO_DAILY.format(instant_content=instant_content)
        try:
            distilled = llm_callable(prompt)  # type: ignore[operator]
        except Exception:
            distilled = _direct_copy_fallback(session, instant_content)
    else:
        distilled = _direct_copy_fallback(session, instant_content)

    # Before appending, check if doing so would exceed daily budget
    existing = daily_path.read_text(encoding="utf-8") if daily_path.exists() else ""
    combined_tokens = count_tokens(existing) + count_tokens(distilled)

    if combined_tokens > cfg.daily.auto_flush_threshold_tokens:
        _trigger_midday_flush(session, existing, daily_path)
        existing = daily_path.read_text(encoding="utf-8") if daily_path.exists() else ""

    # Append to daily file
    if not existing:
        today_str = datetime.now().strftime("%Y-%m-%d")
        existing = f"# Daily Memory — {today_str}\n"

    new_content = existing.rstrip("\n") + "\n\n" + distilled.strip() + "\n"
    daily_path.write_text(new_content, encoding="utf-8")
    return True


def _direct_copy_fallback(session: "Session", instant_content: str) -> str:
    """Extract structured sections from instant file without LLM compression."""
    now = datetime.now()
    start = session.start_time.strftime("%H:%M")
    end = now.strftime("%H:%M")
    header = f"## Session ({start}–{end})"

    # Strip the instant file header (everything before first ### heading)
    body_match = re.search(r"(### .+)", instant_content, re.DOTALL)
    body = body_match.group(0) if body_match else instant_content

    return f"{header}\n\n{body}"


def _trigger_midday_flush(
    session: "Session",
    daily_content: str,
    daily_path: object,
) -> None:
    """Trigger a mid-day daily→weekly distillation to free up daily budget.

    This is called when appending to the daily file would exceed the soft
    threshold.  The actual distillation is handled by daily_to_weekly.
    """
    from .daily_to_weekly import midday_distill
    midday_distill(session, daily_content)
