# Network AIOps — Skill Structure

> One OpenClaw instance, built-in subagents. Each domain maps to a skill scope; each skill set lists the concrete skills (capabilities) required.

---

## 1. Domain → Skill Set Mapping

| Domain | Skill set | Purpose |
|--------|-----------|--------|
| **Syslog collection** | `syslog` | Ingest, parse, store, and query device/syslog streams |
| **Monitoring alarm** | `monitoring` | Receive alerts, correlate, classify, and trigger response |
| **Config backup & comparison** | `config-mgmt` | Backup device configs, version, diff, and drift detection |
| **Change establishment, review & validation** | `change-control` | Create change requests, review, approve, validate (dry-run) |
| **Execution** | `execution` | Apply approved changes, rollback, audit |

```
workspace/skills/
├── syslog/           # Syslog collection
├── monitoring/       # Monitoring alarm
├── config-mgmt/      # Config backup & comparison
├── change-control/   # Change establishment, review, validation
├── execution/        # Execution (apply, rollback, audit)
├── pyats/            # (existing) Device show/configure
├── netcare-eoms/     # (existing) EOMS tickets
├── netcare-itsr/     # (existing) ITSR tickets
└── netcare-ipam/     # (existing) IPAM
```

---

## 2. Skill Sets and Required Skills

### 2.1 Syslog (`syslog`)

| # | Skill | Description | Tools / capabilities |
|---|--------|--------------|----------------------|
| 1 | **syslog-ingest** | Receive and normalize syslog from devices/collectors | Ingest from file/stream/API; parse RFC5424/BSD; normalize fields (host, facility, severity, message, timestamp); write to store |
| 2 | **syslog-store** | Persist and index logs for query | Store in DB or search engine; index by time, host, severity, facility; retention policy |
| 3 | **syslog-query** | Search and filter logs | Query by time range, host, severity, keyword; return matches; optional aggregation (count by host, by severity) |

**Subagent scope:** When the user asks to “check device logs”, “show syslog for router-X”, “find errors in the last hour”, the main agent assigns the `syslog` skill set; the subagent uses syslog-query (and optionally ingest/store if integrating a new source).

---

### 2.2 Monitoring alarm (`monitoring`)

| # | Skill | Description | Tools / capabilities |
|---|--------|--------------|----------------------|
| 1 | **alarm-ingest** | Receive alerts from monitoring system | Ingest from webhook/API/poll (e.g. Prometheus, Zabbix, custom); normalize to common alarm schema (source, severity, metric, message, timestamp) |
| 2 | **alarm-correlate** | Correlate alarms with topology and logs | Match alarm to device/interface; optionally correlate with syslog; deduplicate; link to recent changes |
| 3 | **alarm-classify** | Severity and type classification | Classify severity (critical/warning/info); suggest category (link down, high CPU, config change, etc.) |
| 4 | **alarm-response** | Trigger actions on alarm | Create ticket (EOMS/ITSR); notify channel (Feishu); trigger runbook or subagent (e.g. “check device”, “backup config”); acknowledge / mute |

**Subagent scope:** “Why is this alarm firing?”, “Create a ticket for this alert”, “Which devices are in alarm?” → `monitoring` skill set.

---

### 2.3 Config backup & comparison (`config-mgmt`)

| # | Skill | Description | Tools / capabilities |
|---|--------|--------------|----------------------|
| 1 | **config-backup** | Backup device running/startup config | Trigger backup (via pyATS or NetCare); store with timestamp and device ID; schedule or on-demand |
| 2 | **config-version** | List and retrieve historical configs | List backups by device, date; retrieve a specific version; diff two versions |
| 3 | **config-diff** | Compare two configs | Compare two files or two versions (by device, by date); output line-by-line diff; highlight added/removed/changed |
| 4 | **config-drift** | Detect drift from baseline | Compare current (or last backup) to a baseline/golden config; report drift; optional threshold (e.g. “only report if &gt; N lines”) |

**Subagent scope:** “Backup config for router-1”, “Compare today’s config to last week”, “Has router-2 drifted from baseline?” → `config-mgmt` skill set. May call `pyats` for actual device read.

---

### 2.4 Change establishment, review & validation (`change-control`)

| # | Skill | Description | Tools / capabilities |
|---|--------|--------------|----------------------|
| 1 | **change-create** | Create a change request | Capture: target device(s), change type (config push, command run), content (patch or command list), requested time, requester; store as change request (draft); link to ticket if needed |
| 2 | **change-review** | Review for compliance and risk | Check change against policy (allowed commands, change window); risk level; approval workflow (e.g. require approver); add comments or reject |
| 3 | **change-validate** | Pre-execution validation | Syntax check (for config); dry-run or “show” equivalent; pre-check (device reachable, no conflict with other changes); output validation result (pass/fail + details) |

**Subagent scope:** “Create a change to add ACL on switch-1”, “Review pending changes”, “Validate change CHG-001” → `change-control` skill set. No execution yet; that is `execution`.

---

### 2.5 Execution (`execution`)

| # | Skill | Description | Tools / capabilities |
|---|--------|--------------|----------------------|
| 1 | **change-apply** | Execute an approved change | Apply config or run commands on device(s) (via pyATS or NetCare); record start/end time and output; update change status to executed |
| 2 | **rollback** | Rollback on failure or request | Restore previous config or run rollback commands; mark change as rolled back; optional auto-rollback on apply failure |
| 3 | **audit** | Audit trail for changes | Log who, what, when, outcome; list history for device or change ID; export for compliance |

**Subagent scope:** “Execute approved change CHG-001”, “Rollback CHG-001”, “Show change history for router-1” → `execution` skill set. Depends on `change-control` for approval state and `pyats` (or similar) for device access.

---

## 3. Cross-Domain Flow (Example)

End-to-end flow with one main agent and skill-scoped subagents:

```
User: "Router-1 has an alarm; backup its config, create a change to add a log filter, and after review execute it."

Main agent:
  1. Spawn subagent [monitoring] → alarm-correlate: confirm router-1 alarm, get details.
  2. Spawn subagent [config-mgmt] → config-backup: backup router-1 now.
  3. Spawn subagent [change-control] → change-create: create change (add log filter on router-1).
  4. Spawn subagent [change-control] → change-review: run review (e.g. policy check).
  5. (User or policy approves.)
  6. Spawn subagent [change-control] → change-validate: dry-run / syntax check.
  7. Spawn subagent [execution] → change-apply: execute approved change.
  8. Spawn subagent [execution] → audit: record and report.
  → Main agent synthesizes and replies to user.
```

---

## 4. Summary Table

| Skill set | Skills (capabilities) |
|-----------|------------------------|
| **syslog** | syslog-ingest, syslog-store, syslog-query |
| **monitoring** | alarm-ingest, alarm-correlate, alarm-classify, alarm-response |
| **config-mgmt** | config-backup, config-version, config-diff, config-drift |
| **change-control** | change-create, change-review, change-validate |
| **execution** | change-apply, rollback, audit |

Each skill set is implemented as one (or more) OpenClaw skill directories under `workspace/skills/<skill-set>/` with a `SKILL.md` that describes when to use it and which MCP tools to call. The “skills” in the table are the capabilities that the skill set must expose (as tools or documented procedures) for the subagent to fulfill the domain.
