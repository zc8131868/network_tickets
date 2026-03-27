# NetOps AIOps Solution Design

> Single OpenClaw instance with built-in subagent orchestration, integrated into the NetCare platform.

---

## 1. Design Philosophy

**One orchestrator, many specialists, start simple.**

A single OpenClaw gateway instance acts as the central AI brain. It runs one main agent that understands user intent, decomposes tasks, and spawns lightweight subagents on demand. Each subagent is scoped to a specific domain (network devices, ticketing, diagnostics) with its own skill set and a cost-appropriate LLM.

This avoids the complexity of multi-instance coordination, custom agent frameworks, or building orchestration from scratch -- while preserving the ability to scale later.

---

## 2. Architecture Overview

```
                         ┌──────────────────────────────────┐
                         │         User Interfaces          │
                         │                                  │
                         │  ┌────────────┐  ┌────────────┐  │
                         │  │  NetCare   │  │   Feishu   │  │
                         │  │  Web Chat  │  │  Channel   │  │
                         │  └─────┬──────┘  └─────┬──────┘  │
                         └───────┬────────────────┘         │
                                 │                          │
                    ┌────────────▼────────────────┐         │
                    │     OpenClaw Gateway        │         │
                    │     (single instance)       │◄────────┘
                    │                             │
                    │  ┌───────────────────────┐  │
                    │  │      Main Agent       │  │
                    │  │   (high-quality LLM)  │  │
                    │  │                       │  │
                    │  │  Understands intent,  │  │
                    │  │  decomposes tasks,    │  │
                    │  │  synthesizes results  │  │
                    │  └──┬─────────┬────────┘  │
                    │     │         │            │
                    │  ┌──▼──┐  ┌──▼──┐         │
                    │  │Sub 1│  │Sub 2│  ...     │
                    │  └──┬──┘  └──┬──┘         │
                    └─────┼────────┼────────────┘
                          │        │
               ┌──────────▼──┐  ┌──▼───────────┐
               │ pyATS MCP   │  │ NetCare MCP  │
               │ SSE Server  │  │ SSE Server   │
               │ (existing)  │  │ (to build)   │
               └──────┬──────┘  └──────┬───────┘
                      │                │
              ┌───────▼──────┐  ┌──────▼────────┐
              │   Network    │  │    Django      │
              │   Devices    │  │   Backend      │
              │  (testbed)   │  │ (EOMS / ITSR)  │
              └──────────────┘  └───────────────┘
```

---

## 3. Component Inventory

### 3.1 Already Built

| Component | Location | Status |
|---|---|---|
| OpenClaw Gateway | `196.21.5.228`, Docker | Running |
| Nginx reverse proxy | Docker, port 18443 | Running |
| Feishu channel | OpenClaw plugin | Connected |
| pyATS MCP SSE Server | `/qytclaw/pyats-mcp/`, Docker | Running, 7 tools |
| pyATS Skill (`SKILL.md`) | `/root/.openclaw/workspace/skills/pyats/` | Active |
| Behavioral rules (`TOOLS.md`) | `/root/.openclaw/workspace/` | Active |
| Model endpoint (aihubmix) | `minimax-m2.5` via `aihubmix` | Configured |
| NetCare Django platform | `/it_network/network_tickets/`, systemd | Running |
| EOMS ticket automation | `eoms_automation_2.py` | Working |
| ITSR ticket automation | ITSR tools suite | Working |
| Mercury AI (ChromaDB chat) | `/mercury_chat/` | Working |

### 3.2 To Build

| Component | Purpose | Priority |
|---|---|---|
| NetCare MCP SSE Server | Expose EOMS/ITSR/network functions to OpenClaw | Phase 1 |
| NetCare Skill (`SKILL.md`) | Tell OpenClaw how to use NetCare tools | Phase 1 |
| Chat Completions endpoint | Enable OpenClaw gateway HTTP API | Phase 1 |
| NetCare chat page | Embedded OpenClaw chat in Django UI | Phase 1 |
| Django proxy view | Bridge between browser and gateway API | Phase 1 |
| Additional LLM endpoints | Cost-tier models for subagents | Phase 2 |
| Monitoring skill | Proactive alerting via subagents | Phase 3 |

---

## 4. LLM Strategy

The main agent uses a high-quality model for reasoning, task decomposition, and user interaction. Subagents use cheaper/faster models for scoped, well-defined tasks.

```
┌─────────────────────────────────────────────────────────┐
│                    LLM Tier Strategy                    │
├────────────┬──────────────────┬─────────────────────────┤
│    Tier    │      Model       │         Role            │
├────────────┼──────────────────┼─────────────────────────┤
│ Tier 1     │ minimax-m2.5     │ Main agent: reasoning,  │
│ (strong)   │ (current)        │ orchestration, user     │
│            │                  │ interaction, synthesis  │
├────────────┼──────────────────┼─────────────────────────┤
│ Tier 2     │ TBD              │ Subagents: device       │
│ (fast,     │ (e.g. GPT-4o-   │ checks, ticket creation,│
│  cheap)    │  mini, Gemini    │ log parsing, routine    │
│            │  Flash, or a     │ diagnostics             │
│            │  smaller model   │                         │
│            │  via aihubmix)   │                         │
└────────────┴──────────────────┴─────────────────────────┘
```

### Configuration

Main agent uses the default model. Subagent model is overridden per-spawn or via defaults:

```json5
// openclaw.json
{
  agents: {
    defaults: {
      subagents: {
        model: "fast-model-alias",
        runTimeoutSeconds: 300,
        maxConcurrent: 8,
        maxChildrenPerAgent: 5,
        maxSpawnDepth: 1
      }
    }
  }
}
```

Per-spawn override when a task needs the strong model:

```
sessions_spawn task="Analyze root cause of network outage across 3 sites" model="minimax-m2.5"
```

**Starting point:** Use `minimax-m2.5` for everything initially. Add a Tier 2 model once workflows are validated and cost optimization becomes relevant.

---

## 5. Skill Architecture

Each operational domain is a separate skill directory under `/root/.openclaw/workspace/skills/`. Skills are loaded on demand to keep context lean.

```
/root/.openclaw/workspace/
├── AGENTS.md
├── TOOLS.md
└── skills/
    ├── pyats/
    │   └── SKILL.md          ← existing, 7 pyATS tools via MCP
    ├── netcare-eoms/
    │   └── SKILL.md          ← to build, EOMS ticket operations
    ├── netcare-itsr/
    │   └── SKILL.md          ← to build, ITSR ticket operations
    └── netcare-ipam/
        └── SKILL.md          ← to build, IP management operations
```

### Skill Scoping per Subagent

When the main agent spawns a subagent, it assigns only the relevant skill:

| User request | Subagent skill | Tools available |
|---|---|---|
| "Check interface status on router-1" | `pyats` | `pyats_run_show_command`, `pyats_list_devices`, ... |
| "Create an EOMS Cloud ticket for this issue" | `netcare-eoms` | `eoms_create_ticket`, `eoms_check_status`, ... |
| "Raise an ITSR ticket for VPN access" | `netcare-itsr` | `itsr_create_ticket`, `itsr_submit_sms`, ... |
| "What IP range is available in VLAN 100?" | `netcare-ipam` | `ipam_lookup`, `ipam_apply`, ... |

### Cross-Domain Workflow (Main Agent Orchestrates)

For compound tasks like "Interface Gi0/0 on router-1 is down, create a ticket":

```
User: "Interface Gi0/0 on router-1 is down, create a ticket for it"

Main Agent:
  1. Spawn subagent with pyats skill
     → task: "Show interface Gi0/0 status on router-1, return details"
     → subagent runs pyats_run_show_command, announces result

  2. Main agent receives result: "Gi0/0 is down/down since 14:32, last input 2h ago"

  3. Spawn subagent with netcare-eoms skill
     → task: "Create EOMS Cloud ticket: Gi0/0 down on router-1 since 14:32..."
     → subagent runs eoms_create_ticket, announces ticket ID

  4. Main agent synthesizes and responds to user:
     "Interface Gi0/0 on router-1 is confirmed down (since 14:32, no input for 2h).
      EOMS ticket EOMS-20260305-001 has been created."
```

---

## 6. NetCare MCP Server Design

A new FastMCP SSE server (same pattern as the pyATS MCP server) that exposes NetCare Django functions as tools.

### Proposed Tools

```python
@mcp.tool()
async def eoms_create_ticket(
    username: str,
    password: str,
    target_department: str,      # "Cloud" or "SN"
    title: str,
    description: str,
    captcha_code: str = ""
) -> str:
    """Create an EOMS ticket. Returns ticket ID or captcha requirement."""

@mcp.tool()
async def itsr_create_ticket(
    username: str,
    password: str,
    ticket_data: str             # JSON: title, description, category, etc.
) -> str:
    """Create an ITSR ticket. Returns ticket ID or SMS requirement."""

@mcp.tool()
async def itsr_submit_sms(
    session_id: str,
    sms_code: str
) -> str:
    """Submit SMS verification code for an ITSR ticket in progress."""

@mcp.tool()
async def ipam_lookup(
    query: str                   # IP, subnet, or VLAN identifier
) -> str:
    """Look up IP address allocation and availability."""
```

### Credential Handling

EOMS/ITSR require user credentials. Two approaches:

1. **Pass-through (Phase 1):** The main agent asks the user for credentials in the chat, passes them to the subagent task instruction, subagent passes them to the MCP tool. Credentials are transient (not stored).

2. **Auth store (Phase 2):** Use OpenClaw's per-agent auth profiles to store encrypted credentials. The MCP server retrieves them from the auth context.

---

## 7. NetCare Web Integration

Embed an OpenClaw chat interface as a page within the existing NetCare Django platform.

### Data Flow

```
┌──────────────────────────────────────────────────────┐
│                    NetCare Django                     │
│                                                      │
│  ┌──────────┐    ┌──────────────┐    ┌────────────┐  │
│  │ Browser  │───▶│ Django View  │───▶│  OpenClaw   │  │
│  │ (SSE     │◀───│ /openclaw_   │◀───│  Gateway    │  │
│  │ stream)  │    │ chat_api/    │    │  :18789     │  │
│  └──────────┘    └──────────────┘    │ /v1/chat/   │  │
│                                      │ completions │  │
│                                      └────────────┘  │
└──────────────────────────────────────────────────────┘
```

### Navigation Placement

Add under the existing "Network Tools" dropdown in the navbar, next to Mercury AI:

```html
<li><a class="dropdown-item" href="/openclaw_chat/">
  <i class="fas fa-brain me-2"></i>NetOps AI
</a></li>
```

### Implementation Components

| File | Purpose |
|---|---|
| `auto_tickets/views/openclaw_chat.py` | Django view + API proxy to gateway |
| `auto_tickets/templates/openclaw_chat.html` | Chat UI with SSE streaming (based on Mercury template) |
| `network_tickets/urls.py` | Route `/openclaw_chat/` and `/openclaw_chat_api/` |
| `templates/base.html` | Add nav dropdown item |

### Key Differences from Mercury AI

| Aspect | Mercury AI | NetOps AI (OpenClaw) |
|---|---|---|
| Backend | Local `chromadb_agent` | Proxied to OpenClaw gateway |
| Response | Wait for full answer | SSE streaming (token-by-token) |
| Session | Stateless | Persistent via `user` session key |
| Capabilities | ChromaDB lookup only | Full agent: device ops, tickets, diagnostics |
| Latency | Fast (local) | Variable (agent may spawn subagents, call tools) |

### Gateway Configuration Required

Enable the Chat Completions endpoint (disabled by default):

```json5
// openclaw.json
{
  gateway: {
    http: {
      endpoints: {
        chatCompletions: { enabled: true }
      }
    }
  }
}
```

---

## 8. Deployment Topology

All services run on `196.21.5.228`. No additional servers required.

```
196.21.5.228
│
├── Docker
│   ├── openclaw-gateway    (port 18789, internal)
│   ├── openclaw-nginx      (port 18443, HTTPS)
│   ├── pyats-mcp           (port 8765, internal, openclaw_default network)
│   └── netcare-mcp         (port TBD, internal, openclaw_default network)  ← new
│
├── Systemd
│   └── network_tickets.service  (Gunicorn/Uvicorn, Django app)
│
└── Nginx (host)
    └── Reverse proxy for Django (port 443 → Django)
```

### Docker Network

All MCP servers and the gateway share the `openclaw_default` Docker network for container-to-container communication. The Django app runs outside Docker under systemd but is reachable via host networking.

---

## 9. Phased Rollout

### Phase 1: Foundation (Current Sprint)

**Goal:** OpenClaw chat accessible from NetCare, using existing pyATS capability.

- [ ] Enable Chat Completions endpoint on OpenClaw gateway
- [ ] Build Django proxy view (`openclaw_chat.py`)
- [ ] Build chat template with SSE streaming (`openclaw_chat.html`)
- [ ] Add "NetOps AI" to NetCare navigation
- [ ] Test end-to-end: user asks about a device → pyATS subagent responds

**Outcome:** Users can chat with the AI from NetCare and run device checks.

### Phase 2: Ticketing Integration

**Goal:** AI can create EOMS/ITSR tickets on user request.

- [ ] Build NetCare MCP SSE Server (wrap `eoms_automation_2.create_ticket`, ITSR functions)
- [ ] Create `netcare-eoms` and `netcare-itsr` skills (`SKILL.md`)
- [ ] Add Tier 2 LLM endpoint for subagents (cost optimization)
- [ ] Update `TOOLS.md` behavioral rules for ticket operations
- [ ] Test cross-domain: device check → automatic ticket creation

**Outcome:** AI handles full "detect and act" workflows.

### Phase 3: Proactive Operations

**Goal:** AI monitors and alerts proactively.

- [ ] Build a monitoring skill that periodically checks device health
- [ ] Use OpenClaw cron + subagent spawn for scheduled checks
- [ ] Integrate alerting to Feishu channel
- [ ] Add IPAM operations (IP lookup, allocation) as a skill
- [ ] Build persistent memory for incident history (conversation summaries, past tickets)

**Outcome:** System evolves from reactive Q&A to proactive network operations.

---

## 10. When to Outgrow This Design

This single-instance architecture has clear boundaries. Consider building a custom orchestrator when:

| Signal | Why it matters |
|---|---|
| Subagents need to talk to each other directly | Current design: all communication goes through the main agent |
| You need persistent memory across sessions | OpenClaw sessions are ephemeral; no cross-session knowledge base |
| Parallel multi-step workflows exceed 5 concurrent subagents | `maxChildrenPerAgent` cap; gateway is single-process |
| You need structured runbooks with conditional branching | OpenClaw subagents are task-oriented, not workflow-engine-oriented |
| Response latency for compound tasks exceeds user tolerance | Sequential spawn-wait-spawn adds up |

Until you hit these walls, this design gives you a working AIOps system with minimal custom code.
