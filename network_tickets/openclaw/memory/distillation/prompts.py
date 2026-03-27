"""
All distillation prompt templates.

Each prompt is a plain string with {placeholders} for `.format()` calls.
The actual LLM invocation happens in the caller — these are just templates.
"""

# ---------------------------------------------------------------------------
# Instant → Daily
# ---------------------------------------------------------------------------

INSTANT_TO_DAILY = """\
You are distilling a session scratchpad into a daily memory log.

INPUT: The contents of the instant memory file for this session.

<instant_memory>
{instant_content}
</instant_memory>

RULES:
1. Extract decisions, facts, errors resolved, corrections, and open questions.
2. Drop routine commands, dead-end explorations, and repetitive exchanges.
3. Preserve exact values (versions, config keys, error messages) — do not paraphrase technical details.
4. Append the output to today's daily memory file under a session heading.
5. Use concise bullet points. Each bullet should be independently understandable.

OUTPUT: Markdown to append to the daily memory file. Use this format:

## Session (HH:MM–HH:MM)

### Decisions
- ...

### Facts Learned
- ...

### Errors Resolved
- ...

### Corrections
- ...

### Open Questions
- ...

Only include sections that have content. Omit empty sections.
"""

# ---------------------------------------------------------------------------
# Daily → Weekly (nightly distillation)
# ---------------------------------------------------------------------------

DAILY_TO_WEEKLY = """\
You are distilling a daily memory log into a weekly summary.

INPUT:
- Today's daily memory file:
<daily_memory>
{daily_content}
</daily_memory>

- The current weekly memory file (may be empty if this is the first day of the week):
<weekly_memory>
{weekly_content}
</weekly_memory>

RULES:
1. Merge today's content into the weekly file.
2. Deduplicate: if a fact already exists in the weekly file, do not add it again.
3. Compress: combine related bullets into single, richer bullets where possible.
4. Preserve all [PINNED] items verbatim — do not compress or remove them.
5. Auto-pin any item that has appeared in 3 or more daily files this week.
6. Auto-pin all corrections (where the user overrode a previous assumption).
7. Keep decisions, patterns, corrections, technical context, and unresolved questions as separate sections.
8. Drop session-level structure (session 1, session 2) — weekly memory is thematic, not chronological.
9. Stay within {max_tokens} tokens.

OUTPUT: The complete updated weekly memory file in Markdown.
"""

# ---------------------------------------------------------------------------
# Daily → Weekly (mid-day auto-flush)
# ---------------------------------------------------------------------------

DAILY_TO_WEEKLY_MIDDAY = """\
You are performing a mid-day distillation because the daily memory file has exceeded its token budget.

INPUT:
- The current daily memory file (over budget):
<daily_memory>
{daily_content}
</daily_memory>

- The current weekly memory file:
<weekly_memory>
{weekly_content}
</weekly_memory>

RULES:
1. Distill the daily file into the weekly file using the standard daily → weekly rules (merge, deduplicate, compress, preserve [PINNED] items, auto-pin corrections and 3+ occurrences).
2. Produce a carry-forward summary (target: under {carry_forward_tokens} tokens) containing only items from today that are NOT yet represented in the updated weekly file — typically the most recent session's content and any open questions specific to the current work-in-progress.
3. Replace the daily file with the carry-forward summary under a "## Carry-Forward" heading.
4. The weekly file must still stay within its {weekly_max_tokens}-token budget. If merging would exceed this, compress more aggressively.

OUTPUT FORMAT — return exactly two sections separated by the delimiter:

<updated_weekly>
(complete updated weekly memory file in Markdown)
</updated_weekly>

<carry_forward>
(replacement daily memory file — carry-forward summary only)
</carry_forward>
"""

# ---------------------------------------------------------------------------
# Weekly → Permanent (Saturday distillation)
# ---------------------------------------------------------------------------

WEEKLY_TO_PERMANENT = """\
You are distilling a weekly memory summary into permanent memory.

INPUT:
- This week's weekly memory file:
<weekly_memory>
{weekly_content}
</weekly_memory>

- The current MEMORY.md:
<permanent_memory>
{permanent_content}
</permanent_memory>

- Relevant entity files:
<entity_files>
{entity_content}
</entity_files>

RULES:
1. Extract only facts with month-or-longer durability. Ask: "Will this still be true and useful 30 days from now?"
2. Drop time-bound context (sprint goals, daily tasks, in-progress work).
3. Merge into existing sections in MEMORY.md. Do not create duplicate entries.
4. If a new fact contradicts an existing entry in MEMORY.md, replace the old entry and add a dated correction to the Correction History section.
5. If a fact clearly belongs to a specific entity (person, server, project), route it to the appropriate file in memory/entities/. Create the entity file if it doesn't exist.
6. Keep MEMORY.md under {max_tokens} tokens. If it would exceed this, split the least-accessed section into an entity file.
7. Preserve the section structure: User Preferences, Project sections, Architecture Decisions, Correction History.
8. Unresolved questions from weekly memory should only be promoted to permanent if they represent ongoing architectural decisions, not transient debugging questions.

OUTPUT FORMAT — return the updated files separated by delimiters:

<updated_permanent>
(complete updated MEMORY.md in Markdown)
</updated_permanent>

For each entity file that was created or updated, include:
<entity file="entity-slug.md">
(complete entity file content in Markdown)
</entity>

If no entity files were changed, omit the entity sections.
"""
