"""
Distillation logic: Weekly → Permanent.

Runs every Saturday after the nightly daily→weekly distillation completes.
Extracts durable facts and routes them to MEMORY.md and/or entity files.
"""

from __future__ import annotations

import re
from datetime import datetime
from typing import TYPE_CHECKING, Optional

from ..config import get_config, resolve_path
from ..tiers.permanent import PermanentMemory
from ..tokens import count_tokens
from .prompts import WEEKLY_TO_PERMANENT

if TYPE_CHECKING:
    from ..session import Session


def saturday_distill(
    session: Optional["Session"] = None,
    llm_callable: Optional[object] = None,
    target_date: Optional[datetime] = None,
) -> bool:
    """Run Saturday distillation: weekly → permanent.

    Returns True on success.
    """
    cfg = get_config()
    now = target_date or datetime.now()

    weekly_path = resolve_path(cfg.weekly.storage_template, now=now)
    if not weekly_path.exists():
        return False

    weekly_content = weekly_path.read_text(encoding="utf-8")
    perm = PermanentMemory(session)
    permanent_content = perm.read()
    relevant_entities = perm.read_relevant_entities(weekly_content)

    entity_text = ""
    if relevant_entities:
        entity_text = "\n\n".join(
            f"### {slug}.md\n{content}"
            for slug, content in relevant_entities.items()
        )
    else:
        entity_text = "(no relevant entity files)"

    if llm_callable is not None:
        prompt = WEEKLY_TO_PERMANENT.format(
            weekly_content=weekly_content,
            permanent_content=permanent_content,
            entity_content=entity_text,
            max_tokens=cfg.permanent.max_tokens,
        )
        try:
            result = llm_callable(prompt)  # type: ignore[operator]
            updated_permanent, entity_updates = _parse_response(result)
        except Exception:
            updated_permanent = _merge_fallback(weekly_content, permanent_content, now)
            entity_updates = {}
    else:
        updated_permanent = _merge_fallback(weekly_content, permanent_content, now)
        entity_updates = {}

    # Write pre-distillation backup
    from ..recovery.backup import backup_file
    backup_file(perm.path)

    perm.write(updated_permanent)
    perm.enforce_budget()

    for slug, content in entity_updates.items():
        backup_entity_path = perm.entity_dir / f"{slug}.md"
        if backup_entity_path.exists():
            backup_file(backup_entity_path)
        perm.write_entity(slug, content)

    return True


# ---------------------------------------------------------------------------
# Response parsing
# ---------------------------------------------------------------------------

def _parse_response(response: str) -> tuple[str, dict[str, str]]:
    """Parse the LLM's Saturday distillation response."""
    perm_match = re.search(
        r"<updated_permanent>\s*(.*?)\s*</updated_permanent>",
        response,
        re.DOTALL,
    )
    if not perm_match:
        raise ValueError("Could not parse permanent memory from response")

    updated_permanent = perm_match.group(1).strip()

    entity_updates: dict[str, str] = {}
    for entity_match in re.finditer(
        r'<entity\s+file="([^"]+)">\s*(.*?)\s*</entity>',
        response,
        re.DOTALL,
    ):
        filename = entity_match.group(1)
        slug = filename.replace(".md", "")
        entity_updates[slug] = entity_match.group(2).strip()

    return updated_permanent, entity_updates


# ---------------------------------------------------------------------------
# Fallback: no-LLM merge
# ---------------------------------------------------------------------------

def _merge_fallback(
    weekly_content: str,
    permanent_content: str,
    now: datetime,
) -> str:
    """Merge weekly into permanent without LLM — structural append of new bullets.

    Maps weekly sections to permanent sections and deduplicates.
    """
    section_map = {
        "Key Decisions": "Architecture Decisions",
        "Patterns Observed": "User Preferences",
        "Corrections [PINNED]": "Correction History",
        "Corrections": "Correction History",
        "Technical Context": None,  # Route to matching project section or create one
        "Unresolved": None,  # Only promote architectural questions
    }

    existing_bullets = set()
    for line in permanent_content.splitlines():
        if line.strip().startswith("- "):
            existing_bullets.add(line.strip())

    additions_by_section: dict[str, list[str]] = {}
    current_section = None

    for line in weekly_content.splitlines():
        heading_match = re.match(r"^##\s+(.+)", line)
        if heading_match:
            current_section = heading_match.group(1).strip()
        elif line.strip().startswith("- ") and current_section:
            bullet = line.strip()
            if bullet in existing_bullets:
                continue

            target = section_map.get(current_section)
            if target is None:
                continue

            if target == "Correction History":
                date_str = now.strftime("%Y-%m-%d")
                text = re.sub(r"^\[PINNED\]\s*", "", bullet.lstrip("- ")).strip()
                bullet = f"- [{date_str}] {text}"

            additions_by_section.setdefault(target, []).append(bullet)

    for section, bullets in additions_by_section.items():
        heading = f"## {section}"
        insert_text = "\n".join(bullets)

        if heading in permanent_content:
            idx = permanent_content.index(heading) + len(heading)
            next_heading = permanent_content.find("\n## ", idx)
            if next_heading == -1:
                permanent_content = (
                    permanent_content.rstrip("\n") + "\n" + insert_text + "\n"
                )
            else:
                permanent_content = (
                    permanent_content[:next_heading].rstrip("\n")
                    + "\n"
                    + insert_text
                    + "\n"
                    + permanent_content[next_heading:]
                )
        else:
            permanent_content = (
                permanent_content.rstrip("\n") + f"\n\n{heading}\n{insert_text}\n"
            )

    return permanent_content
