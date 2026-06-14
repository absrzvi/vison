# Critical-Alert Standard Operating Procedure (SOP)

**Status:** PoC draft — pending ÖBB ops signoff (see [pilot-kickoff-checklist.md](pilot-kickoff-checklist.md))
**Owner:** Nomad AI PM · **ÖBB ops owner:** `TBD — ÖBB signoff`
**Source story:** [E10-S3](../implementation-artifacts/10-3-critical-alert-sop-and-drill-cadence.md) · **Authority for actor model:** project memory `project-actor-model-conrad`
**Companion docs:** [alert-routing-matrix.md](alert-routing-matrix.md) · [drill-cadence.md](drill-cadence.md)

> This SOP is the written, rehearsed sequence that runs when a **critical** alert fires. It is not a UI screen — it is the human procedure that wraps the shipped mechanisms (confidence metadata 10-1, escalation lifecycle 10-6, behavioural telemetry 10-2).

---

## 1. Actor model (read first)

The PoC uses a **single-landside-actor** model. Two facts govern everything below:

1. **"Conrad" = the on-train AI platform** (fusion engine + Hailo inference on SYS2) — the **source** that *raises* alerts. Conrad is **not a human**. It does not "assess", cannot be "unreachable" as an SOP step, and has no decision role. *Platform liveness* (is Conrad up?) is a System Health concern handled by the 10-1 `INFERENCE_HEARTBEAT` / AI-pipeline-health Red state — **not** a branch in this SOP.
2. **Acknowledgement authority is train-type-conditional:**
   - **Conductorless trains** (regional / Nahverkehr) — **the default and primary PoC case**: only the **landside Fleet Manager / remote staff (Claudia)** can acknowledge and resolve. There is **no onboard human step**.
   - **Fernverkehr trains** (long-distance): an onboard **human conductor may also acknowledge** from the Conductor App; if they do not, the escalation falls through to landside after the amber window.

> **Out of PoC scope (do not follow these even if older docs mention them):** any "Conrad assesses → escalates" two-actor sequence; any ÖBB police/station security-handoff; the "ÖBB security notified" outcome tag. The single landside actor is the Fleet Manager.

---

## 2. What counts as a "critical" alert

An alert is **critical** when **either** condition holds:

- **By class** — the alert is one of the critical alert codes (see [alert-routing-matrix.md](alert-routing-matrix.md)), **regardless of score**. This covers sensor-basis alerts that carry no `confidence_score` (e.g. a TCMS fire alarm). The shipped per-door-fault logic already escalates `door_obstruction` / `door_fault` to **`critical`** severity when the train is moving (`speed_kmh > 0`, or unknown speed — fail-closed) — see `_severity_for` at [enrichment.py:61-76](../../fusion/src/fusion/enrichment.py).
- **By confidence** — a model- or fused-basis alert whose `confidence_score >= 0.85`.

**Critical alert codes (this PoC):**

| Class | Shipped `alert_code` | Producer | Notes |
|---|---|---|---|
| Door-at-speed (live) | `door_obstruction` | fusion ([door_obstruction.py:74](../../fusion/src/fusion/door_obstruction.py)) | Critical only while moving; advisory at standstill |
| Door-at-speed (anticipated) | `door_fault` | *not yet emitted* — severity-mapped only ([enrichment.py:69](../../fusion/src/fusion/enrichment.py)) | No shipped producer; routes identically to `door_obstruction` once live |
| Fall / slip | `slip_fall` | fusion ([health.py:218](../../fusion/src/fusion/health.py)) | |
| Fire | *not yet emitted* | — | Forward-looking; no shipped producer. TCMS/sensor-basis when it lands (no `confidence_score`) |
| Unattended item | `unattended_bag` *(not yet emitted)* | — | Forward-looking; no shipped producer. Class named in [confidence_thresholds.py:9](../../cloud-backend/src/cloud_backend/config/confidence_thresholds.py) |

> `alert_code` is a **producer-defined string, not an enum**. An alert with an unrecognised code is handled as **advisory-only** (the default), not as a critical alert. `fire` and `unattended_bag` are listed for completeness but have **no shipped producer** — they become live only when inference/fusion emit them.

> **`confidence_score` may be `None`** (when `confidence_basis == "sensor"`). The 0.85 gate applies **only when a score is present**. A sensor-basis critical-class alert (e.g. a fire alarm) is critical **by class** and is **never** downgraded for lacking a score.

---

## 3. The procedure — branches

When a critical alert fires, follow the branch that matches the train type. The **amber window** is **10 minutes** (PoC default — `pending ÖBB confirm`): the period an alert may sit `unacknowledged` before fall-through/paging.

### 3.1 Conductorless-train branch — DEFAULT / PRIMARY
*(routing-matrix decision: `landside-immediate`)*

```
Conrad (on-train platform) raises critical alert
        │
        ▼
Escalation row created server-side, status = unacknowledged   (10-6 AC2)
        │
        ▼
Landside Fleet Manager (Claudia) sees it in the Control Centre escalations inbox
        │
        ├─ Acknowledges  → status = acknowledged (t_ack, ack_operator_id)   (10-6 AC3)
        │       │
        │       ▼
        │   Takes the required action, then Resolves with an outcome + one
        │   of the four action tags (§4)                                     (10-6 AC4)
        │
        └─ NOT acknowledged within the amber window (10 min)
                │
                ▼
            → go to §3.3 (landside-unreachable branch)
```

There is **no onboard human** on a conductorless train. The Fleet Manager / remote staff are the only actors.

### 3.2 Fernverkehr-train branch
*(routing-matrix decision: `fernverkehr-onboard-first`)*

```
Conrad raises critical alert → escalation row unacknowledged
        │
        ├─ Onboard conductor acknowledges from the Conductor App
        │       → status = acknowledged; conductor handles onboard, resolves with tag
        │
        └─ Onboard conductor does NOT acknowledge within the amber window (10 min)
                │  (NOTE: merely VIEWING the alert is not acknowledging — a viewed-but-
                │   unacknowledged alert that is navigated away from is a silent dismissal,
                │   logged by 10-2, and STILL falls through)
                ▼
            → falls through to landside; Fleet Manager acknowledges + resolves
                │
                └─ if landside also unreachable → §3.3
```

### 3.3 Landside-unreachable branch

```
No landside acknowledgement within the amber window (primary operator)
        │
        ▼
A SECONDARY Control Centre operator is paged   (manual page in PoC — see note)
        │
        ├─ Secondary operator acknowledges + resolves
        │
        └─ still no acknowledgement → escalate per ÖBB ops on-call (TBD — ÖBB signoff)
```

> **Automation note (D4):** the PoC does **not** ship an automatic timed pager or auto-fall-through job. The amber-window fall-through is an **operational expectation** enforced by the team watching the inbox, not by code. An automatic timed escalation is a **Phase 2 / Epic 11** follow-up. Do not assume a pager fires on its own.

### 3.4 Dead-zone branch (connectivity loss during a critical alert)

```
Critical alert fires while the train has NO landside connectivity (tunnel, dead zone)
        │
        ▼
Event is queued ONBOARD in the event-store (sync cursor holds the prefix)
        │
        ▼
On reconnect, the queued ALERT_RAISED syncs landside and the escalation
SURFACES in the inbox — within the onboard retention window it is NOT lost, and
the amber window starts ON SURFACING, not at the original fire time (the amber
window does not "expire" the alert during the outage — but see the retention
caveat below for the >3-journey silent-drop edge)
        │
        ▼
        → resume §3.1 / §3.2 from the point of surfacing
```

This is the behaviour the event-store sync cursor already provides (queued events are delivered in order on reconnect, no gap-drop) **within the onboard retention window**. The SOP's contract: **a critical alert raised in a dead zone is never silently dropped, provided the outage does not exceed the onboard retention window.**

> **⚠ Retention-window caveat (shipped behaviour).** The onboard event-store keeps only the **most recent 3 journeys** — `truncate_old_journeys(retain=3)` runs on every sync-cursor advance ([cursor.py:22-44](../../event-store/src/event_store/sync/cursor.py)), purging by journey *recency*, not by what cloud-sync has already pulled. Cloud-sync pulls oldest-first ([pull_loop.py](../../cloud-sync/src/cloud_sync/pull_loop.py)) but acks only the contiguous *published* prefix ([ack_loop.py](../../cloud-sync/src/cloud_sync/ack_loop.py)); these two gates diverge on a long backlog. So an outage spanning **more than 3 journeys** before cloud-sync drains the backlog can age out an un-pulled `ALERT_RAISED` — a genuine silent-drop edge. Sizing the retention window against the worst-case dead-zone duration is a **pilot-kickoff dependency** (see [pilot-kickoff-checklist.md](pilot-kickoff-checklist.md)).

---

## 4. Resolution — the four action tags

When an operator resolves a critical escalation, they record an outcome text plus **exactly one** of the four shipped landside action tags ([10-6 AC9](../implementation-artifacts/10-6-escalation-lifecycle-persistence.md)). Canonical key → UI label:

| Canonical key | UI label | Meaning |
|---|---|---|
| `resolved_remotely` | Resolved remotely | Handled from the Control Centre without dispatch |
| `field_team_dispatched` | Field team dispatched | A field team was sent to the train/location |
| `false_alarm` | False alarm | The alert was wrong (feeds FP-rate signal, deferred E10-S5) |
| `no_action_needed` | No action needed | Real but required no intervention |

> The stale tags `Police alerted` / `Station notified` / `Conrad instructed` / `Passenger assisted` were **removed** in 10-6 — they describe actors and hops that do not exist in the PoC. Do not reintroduce them. `false_alarm` + `no_action_needed` together are the false-positive signal.

---

## 5. Roles summary

| Role | Who | Branch |
|---|---|---|
| Alert source | Conrad (on-train AI platform) | all — raises, never acknowledges |
| Primary acknowledger (conductorless) | Landside Fleet Manager / remote staff | §3.1 |
| Primary acknowledger (Fernverkehr) | Onboard conductor (else landside) | §3.2 |
| Fall-through acknowledger | Secondary Control Centre operator | §3.3 |
| ÖBB ops on-call escalation | `TBD — ÖBB signoff` | §3.3 final |

---

## 6. Drills & signoff

This SOP is exercised on the cadence in [drill-cadence.md](drill-cadence.md) (monthly tabletop, quarterly live) and must carry named ÖBB ops signoff before pilot kickoff — tracked in [pilot-kickoff-checklist.md](pilot-kickoff-checklist.md).

*Closes Gap 1 of [owning-the-gap-ai-pm-analysis.md](../planning-artifacts/owning-the-gap-ai-pm-analysis.md) (the SOP half).*
