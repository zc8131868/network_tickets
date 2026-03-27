"""
Distillation logic: Daily → Weekly.

Two entry points:
  - nightly_distill()  — end-of-day compression into weekly
  - midday_distill()   — mid-day auto-flush when daily exceeds budget
"""

from __future__ import annotations

import re
from datetime import datetime
from typing import TYPE_CHECKING, Optional

from ..config import get_config, resolve_path, workspace_root
from ..tokens import count_tokens
from .prompts import DAILY_TO_WEEKLY, DAILY_TO_WEEKLY_MIDDAY

if TYPE_CHECKING:
    from ..session import Session


def nightly_distill(
    session: "Session",
    llm_callable: Optional[object] = None,
    target_date: Optional[datetime] = None,
) -> bool:
    """Run end-of-day distillation: merge today's daily into weekly.

    Returns True on success.
    """
    cfg = get_config()
    now = target_date or datetime.now()

    daily_path = resolve_path(cfg.daily.storage_template, now=now)
    weekly_path = resolve_path(cfg.weekly.storage_template, now=now)

    if not daily_path.exists():
        return False

    daily_content = daily_path.read_text(encoding="utf-8")
    weekly_content = ""
    if weekly_path.exists():
        weekly_content = weekly_path.read_text(encoding="utf-8")

    if llm_callable is not None:
        prompt = DAILY_TO_WEEKLY.format(
            daily_content=daily_content,
            weekly_content=weekly_content,
            max_tokens=cfg.weekly.max_tokens,
        )
        try:
            updated_weekly = llm_callable(prompt)  # type: ignore[operator]
        except Exception:
            updated_weekly = _merge_fallback(daily_content, weekly_content, now)
    else:
        updated_weekly = _merge_fallback(daily_content, weekly_content, now)

    weekly_path.parent.mkdir(parents=True, exist_ok=True)
    weekly_path.write_text(updated_weekly, encoding="utf-8")
    return True


def midday_distill(
    session: "Session",
    daily_content: str,
    llm_callable: Optional[object] = None,
) -> bool:
    """Mid-day auto-flush: compress daily into weekly, replace daily with carry-forward.

    Called when appending to the daily file would exceed its token budget.
    """
    cfg = get_config()
    now = datetime.now()

    daily_path = resolve_path(cfg.daily.storage_template, now=now)
    weekly_path = resolve_path(cfg.weekly.storage_template, now=now)

    weekly_content = ""
    if weekly_path.exists():
        weekly_content = weekly_path.read_text(encoding="utf-8")

    if llm_callable is not None:
        prompt = DAILY_TO_WEEKLY_MIDDAY.format(
            daily_content=daily_content,
            weekly_content=weekly_content,
            carry_forward_tokens=cfg.daily.carry_forward_max_tokens,
            weekly_max_tokens=cfg.weekly.max_tokens,
        )
        try:
            result = llm_callable(prompt)  # type: ignore[operator]
            updated_weekly, carry_forward = _parse_midday_response(result)
        except Exception:
            updated_weekly = _merge_fallback(daily_content, weekly_content, now)
            carry_forward = _carry_forward_fallback(daily_content, now)
    else:
        updated_weekly = _merge_fallback(daily_content, weekly_content, now)
        carry_forward = _carry_forward_fallback(daily_content, now)

    weekly_path.parent.mkdir(parents=True, exist_ok=True)
    weekly_path.write_text(updated_weekly, encoding="utf-8")
    daily_path.write_text(carry_forward, encoding="utf-8")
    return True


# ---------------------------------------------------------------------------
# Response parsing
# ---------------------------------------------------------------------------

def _parse_midday_response(response: str) -> tuple[str, str]:
    """Extract the two sections from the LLM's mid-day response."""
    weekly_match = re.search(
        r"<updated_weekly>\s*(.*?)\s*</updated_weekly>",
        response,
        re.DOTALL,
    )
    carry_match = re.search(
        r"<carry_forward>\s*(.*?)\s*</carry_forward>",
        response,
        re.DOTALL,
    )

    if not weekly_match or not carry_match:
        raise ValueError("Could not parse mid-day distillation response")

    return weekly_match.group(1).strip(), carry_match.group(1).strip()


# ---------------------------------------------------------------------------
# Fallback: no-LLM merge
# ---------------------------------------------------------------------------

def _merge_fallback(daily_content: str, weekly_content: str, now: datetime) -> str:
    """Merge daily into weekly without LLM — simple structural append.

    Extracts bullet points from daily sections and appends them to
    matching weekly sections. Creates the weekly header if needed.
    """
    iso_year, iso_week, _ = now.isocalendar()
    week_start = now.strftime("%b %-d")

    if not weekly_content.strip():
        weekly_content = (
            f"# Weekly Memory — {iso_year}-W{iso_week:02d} ({week_start})\n\n"
            "## Key Decisions\n\n"
            "## Patterns Observed\n\n"
            "## Corrections [PINNED]\n\n"
            "## Technical Context\n\n"
            "## Unresolved\n"
        )

    section_map = {
        "Decisions": "Key Decisions",
        "Facts Learned": "Technical Context",
        "Errors Resolved": "Technical Context",
        "Corrections": "Corrections [PINNED]",
        "Open Questions": "Unresolved",
    }

    bullets_by_section: dict[str, list[str]] = {}
    current_section = None
    for line in daily_content.splitlines():
        heading_match = re.match(r"^###\s+(.+)", line)
        if heading_match:
            current_section = heading_match.group(1).strip()
        elif line.strip().startswith("- ") and current_section:
            weekly_section = section_map.get(current_section, "Technical Context")
            bullets_by_section.setdefault(weekly_section, []).append(line.strip())

    existing_bullets = set()
    for line in weekly_content.splitlines():
        if line.strip().startswith("- "):
            existing_bullets.add(line.strip())

    for section, bullets in bullets_by_section.items():
        heading = f"## {section}"
        new_bullets = [b for b in bullets if b not in existing_bullets]
        if not new_bullets:
            continue
        insert_text = "\n".join(new_bullets)
        if heading in weekly_content:
            idx = weekly_content.index(heading) + len(heading)
            next_section = weekly_content.find("\n## ", idx)
            if next_section == -1:
                weekly_content = weekly_content.rstrip("\n") + "\n" + insert_text + "\n"
            else:
                weekly_content = (
                    weekly_content[:next_section].rstrip("\n")
                    + "\n"
                    + insert_text
                    + "\n"
                    + weekly_content[next_section:]
                )
        else:
            weekly_content = weekly_content.rstrip("\n") + f"\n\n{heading}\n{insert_text}\n"

    return weekly_content


def _carry_forward_fallback(daily_content: str, now: datetime) -> str:
    """Build a carry-forward summary by keeping only the last session's content."""
    date_str = now.strftime("%Y-%m-%d")
    header = f"# Daily Memory — {date_str}\n\n## Carry-Forward\n"

    sessions = re.split(r"(?=^## Session )", daily_content, flags=re.MULTILINE)
    if len(sessions) > 1:
        last_session = sessions[-1].strip()
        return header + "\n" + last_session + "\n"

    # If there's no session structure, keep the last 500 tokens worth of content
    from ..tokens import count_tokens as _ct, BUDGET_CARRY_FORWARD
    lines = daily_content.splitlines()
    kept: list[str] = []
    for line in reversed(lines):
        kept.insert(0, line)
        if _ct("\n".join(kept)) > BUDGET_CARRY_FORWARD:
            kept.pop(0)
            break
    return header + "\n" + "\n".join(kept) + "\n"
