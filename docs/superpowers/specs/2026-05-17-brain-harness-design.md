# Brain + BYOK Harness — Design Spec

**Date:** 2026-05-17  
**Branch:** brain  
**Status:** Approved for implementation planning  

---

## 1. Overview

Two new components extending the ÖBB Smart Rail platform beyond the existing Hailo-8 Vision pipeline:

1. **Onboard Brain App** — a local agentic diagnostic container running on a dedicated Hailo-10H M.2 slot, correlating SNMP telemetry with vision state and producing plain-language crew guidance plus a structured intent packet for landside.
2. **Landside BYOK Harness** — an LLM-agnostic orchestration layer that accumulates intent packets from the fleet, hydrates them with external rail data, and exposes a natural language query interface alongside structured dashboards for the fleet manager.

These two components are coupled by a single versioned contract: the **intent packet JSON schema**.

---

## 2. Hardware Foundation

### Onboard — Hailo-10H M.2
- **Slot:** Dedicated M.2 Key M slot (separate from Hailo-8 M.2 used by Vision App)
- **Performance:** 40 TOPS INT4, 2.5W typical, 4–8GB on-module LPDDR4
- **LLM capability:** >10 tokens/sec, <1s first-token latency on 1–2B parameter models
- **SDK:** OpenAI-compatible REST API + Ollama integration (pre-built)
- **Supported models (pre-compiled HEF):** Llama-3.2-1B-Instruct, DeepSeek-R1-Distill-Qwen-1.5B

### Landside
- Cloud/datacenter hosted (ÖBB infrastructure)
- No GPU requirement — inference offloaded to ÖBB's own model endpoint

---

## 3. Onboard Brain App

### 3.1 Architecture: Structured Pipeline

**Decision:** Structured pipeline, not a ReAct agentic loop.

**Rationale:** 1–2B models lack the reliability to self-direct tool call iteration safely. ReAct loops risk runaway inference, malformed JSON, and unbounded latency. A deterministic Python state machine assembles context and fires the LLM exactly once — predictable latency, testable transitions, writable safety argument.

### 3.2 Pipeline Stages

```
SNMP trap (VLAN 7)          Vision state (Redis from Hailo-8)
       │                              │
       ▼                              ▼
  im-poller container          hailo-inference container
       │                              │
       └──────────┬───────────────────┘
                  ▼
         local Redis (loopback)
                  │
                  ▼
         Python state machine
         (deterministic correlator)
                  │
         ┌────────┴────────┐
         │  context bundle  │
         │  assembled here  │
         └────────┬────────┘
                  ▼
         Hailo-10H LLM call
         (single inference, OpenAI-compatible REST)
                  │
         Pydantic output validation
                  │
         ┌────────┴────────────────┐
         ▼                         ▼
  Crew screen output         2KB intent packet
  (plain-language)           (JSON → MQTT → landside)
```

### 3.3 State Machine

The Python correlator evaluates Redis state on every update. Defined states:

| State | Trigger condition | LLM fired? |
|---|---|---|
| `NOMINAL` | No overlapping fault signals | No |
| `DEGRADED_DWELL_RISK` | Door IM fault + vision obstruction overlap | Yes |
| `HARDWARE_PORT_DISCONNECT` | Camera DEAD + switch port LINK_DOWN | Yes |
| `BLIND_SPOT_PRM` | Camera DEAD covering PRM zone | Yes |
| `VESTIBULE_CONGESTION` | Occupancy >85% sustained >60s | Yes |

Additional states added as fault types are validated in field testing.

### 3.4 LLM Context Bundle

When the state machine fires, it assembles:
- Current state name + trigger signals
- Relevant Redis key values (occupancy count, door status, switch port alias)
- RAG retrieval result from local vector store (Stadler technical manuals, top-3 chunks)
- Train metadata (ID, speed, next stop, GPS)

Passed as a single structured system prompt. The model is instructed to return a fixed JSON schema — no freeform prose at the root level.

### 3.5 Output Schema (Pydantic-validated)

```python
class CrewGuidance(BaseModel):
    crew_summary: str          # plain-language, max 80 words, for crew screen
    severity: Literal["INFO", "WARNING", "CRITICAL"]
    recommended_action: str    # one imperative sentence

class IntentPacket(BaseModel):
    schema_version: str        # semver, e.g. "1.0.0"
    train_id: str
    timestamp: datetime
    agent_state: str
    severity: Literal["INFO", "WARNING", "CRITICAL"]
    incident_summary: str      # max 300 chars
    local_action_taken: str | None
    downstream_impact: str | None
    request_landside_tasking: bool
    source_signals: list[str]  # which Redis keys triggered this
```

### 3.6 MQTT Transport

- Protocol: MQTT over TLS (QoS 1)
- Heartbeat: every 10 seconds (empty ping, no inference)
- Incident packet: fired on state transition, ~1.5–2KB
- Offline resilience: MQTT client queues packets in local memory during tunnel/no-signal periods; flushes on reconnect

### 3.7 Architecture Decision — Hybrid Hermes Pattern Deferred

**Decision:** Option A (current structured pipeline) now. Hybrid Skills + MCP pattern deferred.

**Rationale:** The hot path is identical between both options — same state machine trigger, same single LLM call, same Pydantic validation, same MQTT output. The hybrid adds abstraction at two seams (fault procedure storage + Redis/SNMP access) without changing latency or safety properties. Adding that abstraction before the landside Rail MCP Server pattern is proven in production would be premature on constrained hardware.

**MCP boundary stub:** The Brain App container should stub the MCP interface boundary now — a thin, non-functional adapter layer marking where local Redis and SNMP tool wrappers would attach. No implementation behind it in v1.

**Migration gate:** Once the landside Rail MCP Server ships and the MCP tool interface is proven stable, evaluate migrating onboard fault procedures to Markdown Skills and Redis/SNMP access to local MCP tool wrappers. Trigger: landside Rail MCP Server running in production for ≥30 days with zero interface breaking changes.

### 3.8 Key Engineering Risks

1. **HEF model integration** — Hailo SDK's OpenAI-compatible endpoint is unvalidated. First test: POST `/v1/chat/completions` with 512-token prompt, assert TTFT <1s and valid JSON schema. Everything else blocked on this passing.
2. **Context assembly correctness** — every state machine path needs unit tests with fixture Redis state snapshots (not mocks — captured blobs from live Hailo-8 Vision App).
3. **SNMP trap ingestion** — validate with `snmpsim` replaying captured MIB walks. AC: trap received → Redis upserted within 200ms.

---

## 4. Landside BYOK Harness

### 4.1 Philosophy

Nomad provides the plumbing, context, and UI. ÖBB provides the reasoning engine (their own API key). The harness is a *transparent reasoning amplifier* — not an oracle. Every answer surfaces its source packets.

The orchestration runtime is **Hermes Agent** (Nous Research, MIT licence, released Feb 2026). Rather than building a custom query engine, tool registry, and session state layer from scratch, we use Hermes as the agent runtime and expose all rail data as MCP tools it can call. This eliminates the FastAPI query engine and LiteLLM abstraction as custom-built components — Hermes handles both natively.

### 4.2 Architecture Layers

```
Train intent packets (MQTT)
          │
          ▼
  Redis Streams (ingest)
          │
          ▼
  PostgreSQL + pgvector
  (intent packet store + embeddings)
          │
          ▼
  Rail MCP Server (Nomad-built)
  exposes PostgreSQL + HAFAS + Depot API
  as typed MCP tools
          │
          ▼
  Hermes Agent runtime
  (conversation loop, persistent memory,
   skills, MCP client, BYOK model endpoint)
          │
          ▼
  Fleet manager UI (70/30 layout)
  — chat sidebar = Hermes frontend
```

### 4.3 Hermes Agent Runtime

Hermes Agent is the landside orchestration engine. **Version pinning required** — pin to a specific release tag in CI; add a compatibility test that asserts all 6 Rail MCP tools are discoverable and schema-valid after any Hermes upgrade. The Hermes Function Calling standard is Nous Research's own spec, not IETF — breakage at the contract layer is a real upgrade risk.

Key capabilities used:

| Hermes capability | How we use it |
|---|---|
| **BYOK model endpoint** | Point Hermes at ÖBB's Azure OpenAI / Bedrock / vLLM endpoint — Hermes handles the rest |
| **MCP client** | Connects to our Rail MCP Server at startup, auto-discovers rail tools, makes them first-class callable in every conversation |
| **Persistent memory (SQLite + FTS5)** | Fleet manager session memory — Hermes remembers prior queries cross-session without custom state management |
| **Skills system** | Markdown skill docs describe scheduled report procedures (weekly fleet health, fault frequency, occupancy trends) — portable, version-controlled alongside the codebase |
| **Structured function calling** | Hermes Function Calling standard (`<tools>` / `<tool_call>` / `<tool_response>`) ensures typed, validated tool invocations against our MCP schema |
| **Spend guardrails** | Per-role token budget caps configured in Hermes — ÖBB's key is charged only for actual queries |

### 4.4 Rail MCP Server (Nomad-built)

The one component Nomad builds from scratch is a **Rail MCP Server** — an HTTP MCP endpoint that exposes fleet data as typed tools Hermes can call:

| Tool | Description |
|---|---|
| `get_fleet_events(train_id?, time_range, severity?)` | Query intent packets from PostgreSQL |
| `get_fleet_summary(time_range)` | Aggregated fleet health across all trains |
| `get_hafas_timetable(train_id, stop)` | Live ÖBB HAFAS timetable lookup |
| `get_depot_schedule(depot_id, date)` | Depot slot and parts availability |
| `search_fleet_events(query)` | Semantic search over intent packet embeddings (pgvector) |
| `schedule_report(report_type, cadence, delivery)` | Register a recurring report (stored in Postgres, executed by Hermes skill) |

All tools return structured JSON. Pydantic models enforce schema at the MCP server boundary — Hermes never receives untyped responses.

**Implementation note (Amelia):** Build the MCP server for one provider (Azure OpenAI) first. Hermes' built-in provider routing handles additional providers without MCP server changes — no premature abstraction needed on our side.

### 4.5 Hermes Pre-Build Spike Tests

These four unknowns must be resolved via spikes before the Hermes integration is committed to the implementation plan. Each spike produces a pass/fail result and a documented finding.

| Spike | Test | Pass criteria |
|---|---|---|
| **MCP startup behaviour** | Start Hermes with Rail MCP Server intentionally down | Hard error surfaced in logs — silent failure is a showstopper |
| **SQLite concurrency** | 10 concurrent fleet manager sessions against one Hermes SQLite instance | No lock contention errors; session isolation confirmed |
| **Skills async model** | Trigger `schedule_report` skill, measure loop block time | Skill dispatches async — UI does not stall >500ms |
| **BYOK 429 handling** | Inject HTTP 429s from a mock provider mid-session | Error surfaces to fleet manager UI; no silent degradation |

Spike 1 (MCP startup) and Spike 4 (429 handling) are highest priority — either failure forces an architectural rethink. Run those first.

### 4.5 BYOK Model Gateway

ÖBB administrators configure their model endpoint in Hermes' config (`~/.hermes/config.yaml`), surfaced via a Nomad-built admin panel:
- Supported providers: Azure OpenAI, AWS Bedrock, private vLLM — Hermes handles format normalisation natively
- Spend guardrails: per-query token budget cap per user role (Hermes config)
- Data privacy: EU-Central region enforcement + no-training-on-data header required — configured at the provider endpoint level

### 4.6 Intent Packet Storage

- **Store:** PostgreSQL (structured fields) + pgvector (embedding of `incident_summary` for semantic search via `search_fleet_events` MCP tool)
- **Ingest pipe:** Redis Streams → consumer group → Postgres insert
- **Retention:** configurable per ÖBB data policy (default 90 days)
- **Query latency AC:** packet arrives → queryable within 500ms

### 4.7 Data Freshness

Fleet manager operates on daily/weekly horizon — 40-minute-stale data is acceptable for their use cases. Every query response surfaces packet age inline (not in a tooltip — visually prominent).

### 4.8 Trust Model

- Every LLM response shows: source packet count, oldest packet timestamp, anomaly flags present in source data
- Zero-source responses (hallucination risk): hard visual interrupt — different UI state, not a warning badge
- No LLM output triggers direct action — all suggestions surface as HITL approval cards

---

## 5. Fleet Manager UI

### 5.1 Layout

70% primary panel (left) / 30% AI chat sidebar (right).

**Primary panel (70%):**
- Alert rail along top (critical → warning → info, colour-coded)
- Fleet status grid (train-by-train, last intent packet state)
- Occupancy and fault trend charts (daily/weekly toggle)
- Scheduled report panel (auto-generated from accumulated intent packets)

**AI chat sidebar (30%):**
- Visual break from primary panel (background tone shift, not a modal)
- Header: "AI Query · Experimental" — secondary text weight
- Tooltip on hover: "Answers draw on data up to 40 min old. Always verify against dashboard figures."

### 5.2 Progressive Disclosure — 3 States

**State 0 — Widget Mode (default)**
- Looks like a dashboard card
- 4–6 seeded query chips in 2-column grid (refresh weekly):
  - "Occupancy last 7 days"
  - "Delayed services now"
  - "Fleet health summary"
  - "Schedule a report"
  - "Door fault frequency this month"
  - "Trains approaching depot threshold"
- Muted hint below chips: "Or type a question…"
- Input field: de-emphasised (low-contrast border, placeholder only)
- No chat history visible

**Trigger → State 1:** chip tapped OR >3 characters typed

**State 1 — Discovery Mode**
- Chip grid collapses upward
- AI response appears as structured card bubble (not a chat bubble)
- Response footer: "What else can I help with?" + 2–3 contextual follow-up chips
- Input field gains full-contrast styling — now primary

**Trigger → State 2:** freeform question typed ignoring chips, OR 2+ interactions completed

**State 2 — Conversational Mode**
- Full chat layout with scrolling history
- Chips replaced by subtle inline "Suggested:" prompt on long pauses
- "Reset view" link in sidebar header returns to State 0

**Progressive disclosure axis:** Structure → Discovery → Fluency. Each state earned by demonstrated user intent, not time.

### 5.3 Query Crystallisation

When a fleet manager asks the same ad hoc question ≥3 times, the system surfaces a prompt: "Add this as a dashboard widget?" This converts recurring queries into permanent dashboard panels — the chat sidebar becomes the product requirements engine for future iterations.

---

## 6. The Intent Packet Contract

The intent packet schema is the single shared contract between the onboard Brain App and the landside harness. It must be:

- **Versioned** with semver from day one (`schema_version` field)
- **Ratified by both sides** before either component is built
- **Tested** via contract tests asserting schema compatibility across both components

Schema drift without version bump = silent production break across potentially 50+ trains. This is the highest-priority pre-build artefact.

---

## 7. What We're Not Building (Scope Boundary)

- No ReAct agentic loop onboard
- No LLM-generated commands sent directly to train systems — all suggestions go through HITL approval
- No custom LLM training or fine-tuning
- No custom query engine or LiteLLM abstraction layer — Hermes Agent handles this natively
- No custom session state management — Hermes persistent memory (SQLite + FTS5) handles this
- No chat interface for on-train staff — dashboards and alerts only for conductor, technician, driver, bistro
- No Hermes Agent modification — we consume it as-is via its MCP client and skills system

---

## 8. Open Questions

### Product & UX
1. Who at ÖBB owns the decision to graduate "experimental" chat to "standard"? Named sponsor + success metric needed before launch.
2. Scheduled reports: push (email/Slack) or pull (dashboard panel only) for v1? Hermes supports both natively — delivery channel is a config choice, not an architecture choice.

### Technical
3. Which provider does ÖBB have an active enterprise agreement with? Determines which provider to configure in Hermes first.
4. What is the depot API schema — existing endpoint or greenfield? Determines scope of the Rail MCP Server `get_depot_schedule` tool.
5. Hermes Agent version pinning strategy — pin to a release tag, define upgrade review cadence. Who owns the Hermes upgrade decision on the Nomad side?
6. SQLite WAL mode — is Hermes handling this for concurrent sessions, or does Nomad need to configure it? Resolved by Spike 2.

### Commercial (for ÖBB sales conversation)
7. Does ÖBB's IT security function need to audit Hermes before production sign-off? Estimate timeline impact.
8. Who at ÖBB approves third-party runtime dependencies — IT, legal, or procurement?
9. Value framing: the €400/train pitch must position around **rail specialisation and integration** (the Rail MCP Server, intent packet schema, HAFAS/depot hydration), not the Hermes runtime itself. ÖBB will perceive Hermes as "free software" — Nomad's moat is the domain layer on top of it.
