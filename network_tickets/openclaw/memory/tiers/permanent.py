"""
Tier 4 — Permanent Memory.

Durable facts (MEMORY.md) and entity-specific knowledge files.
Updated via Saturday distillation from weekly memory.
"""

from __future__ import annotations

import re
from datetime import datetime
from pathlib import Path
from typing import TYPE_CHECKING, Optional

from ..config import get_config, resolve_path, workspace_root
from ..tokens import BUDGET_PERMANENT, count_tokens

if TYPE_CHECKING:
    from ..session import Session


class PermanentMemory:
    """Manages MEMORY.md and entity files."""

    def __init__(self, session: Optional["Session"] = None) -> None:
        self.cfg = get_config().permanent
        self._path = workspace_root() / self.cfg.storage_template
        self._entity_dir = workspace_root() / self.cfg.entity_dir

    @property
    def path(self) -> Path:
        return self._path

    @property
    def entity_dir(self) -> Path:
        return self._entity_dir

    def read(self) -> str:
        if self._path.exists():
            return self._path.read_text(encoding="utf-8")
        return ""

    def write(self, content: str) -> None:
        self._path.parent.mkdir(parents=True, exist_ok=True)
        self._path.write_text(content, encoding="utf-8")

    def token_count(self) -> int:
        return count_tokens(self.read())

    # -- Entity file management -----------------------------------------------

    def list_entities(self) -> list[Path]:
        """Return all entity files."""
        if not self._entity_dir.exists():
            return []
        return sorted(self._entity_dir.glob("*.md"))

    def read_entity(self, slug: str) -> str:
        """Read an entity file by slug (filename without extension)."""
        path = self._entity_dir / f"{slug}.md"
        if path.exists():
            return path.read_text(encoding="utf-8")
        return ""

    def write_entity(self, slug: str, content: str) -> None:
        """Write (create or overwrite) an entity file."""
        self._entity_dir.mkdir(parents=True, exist_ok=True)
        path = self._entity_dir / f"{slug}.md"
        path.write_text(content, encoding="utf-8")

    def read_relevant_entities(self, text: str) -> dict[str, str]:
        """Find and read entity files whose slugs appear in *text*.

        Returns a dict of {slug: content}.
        """
        entities: dict[str, str] = {}
        for path in self.list_entities():
            slug = path.stem
            slug_variants = [slug, slug.replace("-", " "), slug.replace("_", " ")]
            for variant in slug_variants:
                if variant.lower() in text.lower():
                    entities[slug] = path.read_text(encoding="utf-8")
                    break
        return entities

    # -- Budget enforcement ---------------------------------------------------

    def enforce_budget(self) -> list[str]:
        """If MEMORY.md exceeds the token budget, split sections into entity files.

        Returns a list of sections that were split out.
        """
        content = self.read()
        tokens = count_tokens(content)
        max_tokens = self.cfg.max_tokens or BUDGET_PERMANENT
        split_sections: list[str] = []

        while tokens > max_tokens:
            section_name, section_content = self._find_largest_section(content)
            if not section_name:
                break

            slug = re.sub(r"[^a-z0-9]+", "-", section_name.lower()).strip("-")
            self.write_entity(slug, section_content)

            # Replace the section in MEMORY.md with a reference
            content = re.sub(
                rf"(## {re.escape(section_name)})\n.*?(?=\n## |\Z)",
                f"\\1\nSee memory/entities/{slug}.md\n",
                content,
                flags=re.DOTALL,
            )
            split_sections.append(section_name)
            tokens = count_tokens(content)

        if split_sections:
            self.write(content)
        return split_sections

    @staticmethod
    def _find_largest_section(content: str) -> tuple[str, str]:
        """Find the largest H2 section by token count (excluding Correction History)."""
        sections = re.split(r"(?=^## )", content, flags=re.MULTILINE)
        largest_name = ""
        largest_body = ""
        largest_tokens = 0

        for section in sections:
            match = re.match(r"^## (.+?)(?:\n|$)", section)
            if not match:
                continue
            name = match.group(1).strip()
            if "Correction History" in name:
                continue
            tokens = count_tokens(section)
            if tokens > largest_tokens:
                largest_name = name
                largest_body = section
                largest_tokens = tokens

        return largest_name, largest_body

    # -- Entity file creation template ----------------------------------------

    @staticmethod
    def create_entity_template(entity_name: str, entity_type: str = "general") -> str:
        """Return an empty entity file template."""
        now = datetime.now().strftime("%Y-%m-%d")
        return (
            f"# Entity: {entity_name}\n\n"
            f"## Details\n\n"
            f"## Last Updated: {now}\n"
        )
