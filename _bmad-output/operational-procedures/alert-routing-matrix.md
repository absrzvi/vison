# Critical-Alert Routing / Priority Decision Matrix

**Status:** PoC draft — pending ÖBB ops signoff
**Source story:** [E10-S3](../implementation-artifacts/10-3-critical-alert-sop-and-drill-cadence.md) · **Companion:** [critical-alert-sop.md](critical-alert-sop.md)

> Per `alert_code`, this matrix binds **(confidence bucket × speed bucket × location × train type)** to a routing/priority decision. It is the lookup the SOP (§3) and the Control Centre operator use to decide *how fast* and *to whom* a critical alert routes.

---

## Dimensions

| Dimension | Buckets | Source |
|---|---|---|
| `alert_code` | producer-defined string (not an enum) | [payloads.py:102](../../shared/src/oebb_shared/events/payloads.py) |
| `confidence_score` | `high` (≥0.85) · `medium` (0.60–0.85) · `low` (<0.60) · `n/a` (sensor basis, no score) | [payloads.py:116-120](../../shared/src/oebb_shared/events/payloads.py) |
| speed | `in-transit` (speed_kmh > 0) · `in-station` (speed_kmh = 0) | fusion `ContextState.speed_kmh` |
| location | `in-transit` · `in-station` (mirrors speed for the PoC; distinct only if a stationary-in-transit case arises) | — |
| train type | `conductorless` · `Fernverkehr` | `TBD — ÖBB fleet-config source` (see note) |

**Routing decisions (outputs):**
- `landside-immediate` — Fleet Manager acknowledges now; primary conductorless path.
- `fernverkehr-onboard-first` — onboard conductor may ack first; falls through to landside after the amber window.
- `advisory-only` — surfaced as advisory, not a critical escalation (no paging, normal inbox).

> There is **no** `police` / `station` / `security-handoff` output — out of PoC scope (single landside actor).

> **Train-type column is structural, data is pending (D6).** The per-vehicle "conductorless vs Fernverkehr" flag needs an ÖBB fleet-config metadata source that is **not yet confirmed**. Rows below carry the train-type logic, but the live mapping of vehicle → train type is `TBD — ÖBB fleet-config source`. This blocks *populating* real fleet data, not the matrix structure.

---

## Matrix — live alert codes

### `slip_fall` (fall / slip — fusion, [health.py:218](../../fusion/src/fusion/health.py))

| confidence | speed / location | train type | Decision | ÖBB owner | Signoff |
|---|---|---|---|---|---|
| high (≥0.85) | any | conductorless | `landside-immediate` | `TBD` | `TBD` |
| high (≥0.85) | any | Fernverkehr | `fernverkehr-onboard-first` | `TBD` | `TBD` |
| medium | any | conductorless | `landside-immediate` | `TBD` | `TBD` |
| medium | any | Fernverkehr | `fernverkehr-onboard-first` | `TBD` | `TBD` |
| low (<0.60) | any | any | `advisory-only` | `TBD` | `TBD` |

### `door_obstruction` / `door_fault` (door-at-speed — fusion, [enrichment.py:30-45](../../fusion/src/fusion/enrichment.py))

> Severity is already speed-correlated in code: `critical` when `speed_kmh > 0` **or** speed unknown (fail-closed); `warning` at standstill. The matrix mirrors that.

| confidence | speed / location | train type | Decision | ÖBB owner | Signoff |
|---|---|---|---|---|---|
| any / n/a | in-transit (>0) **or speed unknown** | conductorless | `landside-immediate` | `TBD` | `TBD` |
| any / n/a | in-transit (>0) **or speed unknown** | Fernverkehr | `fernverkehr-onboard-first` | `TBD` | `TBD` |
| any / n/a | in-station (speed = 0) | any | `advisory-only` | `TBD` | `TBD` |

### `fire` — *forward-looking, NO shipped producer*

> Listed for completeness. **No fusion/inference producer emits `fire` today.** When it lands it is expected to be **sensor/TCMS basis** (`confidence_basis = "sensor"`, `confidence_score = None`) — critical **by class**, never downgraded for lacking a score.

| confidence | speed / location | train type | Decision | ÖBB owner | Signoff |
|---|---|---|---|---|---|
| n/a (sensor) | any | conductorless | `landside-immediate` | `TBD` | `TBD` |
| n/a (sensor) | any | Fernverkehr | `fernverkehr-onboard-first` | `TBD` | `TBD` |

### `unattended_item` — *forward-looking, NO shipped producer*

> Listed for completeness. No producer emits it today. Expected model-basis (carries `confidence_score`) when implemented.

| confidence | speed / location | train type | Decision | ÖBB owner | Signoff |
|---|---|---|---|---|---|
| high (≥0.85) | any | conductorless | `landside-immediate` | `TBD` | `TBD` |
| high (≥0.85) | any | Fernverkehr | `fernverkehr-onboard-first` | `TBD` | `TBD` |
| < 0.85 | any | any | `advisory-only` | `TBD` | `TBD` |

---

## Default rule

Any `alert_code` **not** listed above (unknown / new producer string) → **`advisory-only`**. An unrecognised code is never auto-routed as critical. New critical classes must be added to this matrix (and signed off) before they route as critical.

*Closes Gap 1 of [owning-the-gap-ai-pm-analysis.md](../planning-artifacts/owning-the-gap-ai-pm-analysis.md) (the decision-matrix half).*
