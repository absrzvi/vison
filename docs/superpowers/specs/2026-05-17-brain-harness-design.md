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

### 3.7 Key Engineering Risks

1. **HEF model integration** — Hailo SDK's OpenAI-compatible endpoint is unvalidated. First test: POST `/v1/chat/completions` with 512-token prompt, assert TTFT <1s and valid JSON schema. Everything else blocked on this passing.
2. **Context assembly correctness** — every state machine path needs unit tests with fixture Redis state snapshots (not mocks — captured blobs from live Hailo-8 Vision App).
3. **SNMP trap ingestion** — validate with `snmpsim` replaying captured MIB walks. AC: trap received → Redis upserted within 200ms.

---

## 4. Landside BYOK Harness

### 4.1 Philosophy

Nomad provides the plumbing, context, and UI. ÖBB provides the reasoning engine (their own API key). The harness is a *transparent reasoning amplifier* — not an oracle. Every answer surfaces its source packets.

### 4.2 Architecture Layers

```
Train intent packets (MQTT)
          │
          ▼
  Redis Streams (ingest)
          │
          ▼
  PostgreSQL + pgvector
  (intent packet store + RAG)
          │
    ┌─────┴──────────────────────┐
    ▼                            ▼
Context hydration            Query engine
(HAFAS API, Depot API)       (FastAPI)
    │                            │
    └──────────┬─────────────────┘
               ▼
    LiteLLM abstraction layer
    (routes to ÖBB's model endpoint)
               │
               ▼
    Pydantic output validation
               │
               ▼
    Fleet manager UI (70/30 layout)
```

### 4.3 BYOK Model Gateway

ÖBB administrators configure their model endpoint via an admin panel:
- Supported providers: Azure OpenAI, AWS Bedrock, private vLLM (ChatML format)
- Abstraction: LiteLLM (single dependency, handles format differences)
- Spend guardrails: per-query token budget cap configurable per user role
- Data privacy: all token processing enforced within EU-Central region; no-training-on-data header flag required

**Implementation note (Amelia):** Build for one provider first (Azure OpenAI). Extract the LiteLLM abstraction after the second provider is added — not before.

### 4.4 Intent Packet Storage

- **Store:** PostgreSQL (structured fields) + pgvector (embedding of `incident_summary` for semantic search)
- **Ingest pipe:** Redis Streams → consumer group → Postgres insert
- **Retention:** configurable per ÖBB data policy (default 90 days)
- **Query latency AC:** packet arrives → queryable within 500ms

### 4.5 Data Freshness

Fleet manager operates on daily/weekly horizon — 40-minute-stale data is acceptable for their use cases. Every query response surfaces packet age inline (not in a tooltip — visually prominent).

### 4.6 Trust Model

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
- No provider-specific optimisation beyond LiteLLM routing
- No chat interface for on-train staff — dashboards and alerts only for conductor, technician, driver, bistro

---

## 8. Open Questions

1. Who at ÖBB owns the decision to graduate "experimental" chat to "standard"? Named sponsor + success metric needed before launch.
2. Which provider does ÖBB have an active enterprise agreement with? Determines which provider to build for first.
3. What is the depot API schema — is there an existing endpoint or does it need to be built?
4. Scheduled reports: push (email/Slack) or pull (dashboard panel only) for v1?
