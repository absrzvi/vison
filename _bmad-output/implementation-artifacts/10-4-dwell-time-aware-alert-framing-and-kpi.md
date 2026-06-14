---
baseline_commit: 4b4a840
---

# Story 10.4: Dwell-Time-Aware Alert Framing & Delay-Minutes-Avoided KPI

Status: ready-for-dev

<!-- Created 2026-06-14 via bmad-create-story (Amelia / Opus 4.8). P2 — fifth story in Epic 10 (Operator Adoption & Trust).
     Source of truth: E10-S4 in epics.md:2307-2338 (committed). Sprint-status names this as "Next P2: 10-4 dwell-time KPI".
     This is a MULTI-PACKAGE, CODE-BEARING story (unlike docs-only 10-3): shared/ payload (Tier 3 schema),
     vlan-pollers/ derivation, cloud-backend/ KPI endpoint, control-centre/ KPI tile, + a Conductor-App spec stub.
     PAYLOAD AUDIT surfaced FOUR epic↔shipped divergences — see Decisions D1-D4. Do NOT implement the epic text literally. -->

## Story

As an **AI PM aligning the product to ÖBB's on-time-departure KPI**,
I want **every pre-departure alert to carry a `seconds_to_departure` field derived from the shipped PIS feed, a dwell-time suffix in the alert copy, and a new Control Centre fleet KPI tracking delay-minutes-avoided**,
so that **the product speaks ÖBB's language and the business case is measurable in the metric the operator actually rewards (Business Goal 2.2 — reduce door-obstruction-attributable delayed departures)**.

## Context — why this story exists

Epic 10 closes the AI-PM "gap" between a demo and a procurement-ready product. The earlier stories made alerts *trustworthy* (10-1 confidence), *persistent* (10-6 escalation lifecycle), *measurable as behaviour* (10-2 telemetry) and *operationally wrapped* (10-3 SOP). This story makes them **speak the operator's KPI**: a pre-departure alert that says "Door obstruction · Coach 6 · **90s to departure**" is actionable in a way that a bare alert is not, and a fleet tile reading "Delay-minutes avoided (24h)" turns the product into a line item an ÖBB business case can defend (Goal 2.2, [01-Business-Goals.md](../design-artifacts/B-Trigger-Map/01-Business-Goals.md)).

The hard part of this story is **not** the code volume — it is that the epic AC text was written in BMAD Phase 3, before the relevant contracts shipped, and **four of its assumptions do not match the shipped system**. The payload audit (team STORY-CONTEXT rule) caught all four. They are resolved in the Decisions section below; the dev agent must implement the *shipped* shapes, not the epic prose.

### What the epic assumes vs what shipped (read this before the ACs)

| Epic text assumes… | Shipped reality | Resolved in |
|---|---|---|
| a train `DWELL` state at a station | **No `DWELL` state exists.** Context-state has `station_approach: bool`, `speed_kmh: float`, and a `pis` substate. "At a station, pre-departure" = `station_approach == true` (or `speed_kmh == 0` with a future `scheduled_departure`). | D1 |
| `seconds_to_departure` sourced "from ZFR/PIS" newly | **The source already exists:** `PisState.scheduled_departure` (ISO-UTC string) is already polled by `pis_poller.py` and held in context-state. Derivation = `scheduled_departure − now`, no new poller. | D1 |
| a `DWELL_FEED_DEGRADED` event on feed loss | **No such EventType.** `pis_poller` already degrades gracefully (empty string on missing field, `log.warning("pis_poll_failed")`). Adding a new EventType + payload is a Tier-3 schema change cascading to event-store + contract tests. | D2 |
| the KPI is "computed from `escalation_audit` rows where outcome_tag indicates in-time resolution" | **`escalation_audit` has no `seconds_to_departure` column** and no notion of "in-time". It has `t_fired`, `t_event`, `action_tags`, `transition`. The KPI must define "delay-minutes avoided" from columns that actually exist. | D3 |
| a Conductor-App banner + "minutes saved this shift" totaliser | **The Conductor App does not exist in this PoC** (epic AC8 itself descopes it to Phase 2). The CC KPI strip is fed by `useFleetData()` (SSE/WS), a different path from the analytics REST endpoints. | D4 |

## Acceptance Criteria

> **Scope note:** epic AC2/AC3 (Conductor-App banner colour-shift + per-shift totaliser) are **descoped to Phase 2** by the epic's own AC8 and by D4. This story ships: the payload field (AC1), its derivation + null-on-feed-loss path (AC2), the Control Centre KPI tile (AC3, AC4), the business-goals entry (AC5), unit tests (AC6), and the Conductor-App spec stub (AC7). No Conductor-App UI code.

**AC1 — `seconds_to_departure` on the alert payload (Tier 3 schema)**
Given an `ALERT_RAISED` event is built for a train that is pre-departure at a station,
when the envelope is constructed,
then `AlertRaisedPayload` ([payloads.py:94](../../shared/src/oebb_shared/events/payloads.py)) carries an **optional** field `seconds_to_departure: int | None = None`:
- `None` when the train is not pre-departure (in-transit), or the PIS `scheduled_departure` is unknown/unparseable (feed-degraded path — D2);
- a non-negative `int` (seconds until scheduled departure) when pre-departure and the feed is healthy.
The field is **additive and backward-compatible** (defaults to `None`, dropped from serialization when `None` to keep existing event consumers byte-compatible — follow the `_drop_none` pattern already used for `priority` at [payloads.py:137-139](../../shared/src/oebb_shared/events/payloads.py)). A `contract` test is added per shared/CLAUDE.md ("Add a contract test any time a field is renamed, removed, or its type changes" — here, added).

**Regression guard — both services deserialize this payload.** shared/CLAUDE.md: "cloud-backend and event-store **both** deserialise these." The additive optional field is safe, but the dev must confirm **event-store round-trips an `AlertRaisedPayload` carrying `seconds_to_departure`** without rejecting the unknown field, and that an *old* payload (field absent) still deserializes. Both directions are part of the `contract` test surface — do not ship the field on the assumption that "additive = automatically safe."

**AC2 — Derivation in fusion, with the null-on-feed-loss path**
Given fusion enriches an alert before emitting (the `enrichment.py` severity/priority path — [enrichment.py:30-45](../../fusion/src/fusion/enrichment.py)),
when the train is pre-departure (`context_state.station_approach == true` **or** `speed_kmh == 0` with a parseable future `scheduled_departure` — D1) and the PIS `scheduled_departure` is present and parseable,
then `seconds_to_departure = max(0, floor(scheduled_departure_epoch − now_epoch))` is stamped onto the `AlertRaisedPayload`;
and when `scheduled_departure` is empty/unparseable or the train is in-transit, `seconds_to_departure` is left `None` (no event is dropped, no exception raised) and a structured `log.info`/`log.warning` records the degraded/skip path (mirroring the existing `pis_poll_failed` log style — **no new EventType**, D2).

**AC3 — Control Centre "Delay-minutes avoided (24h)" KPI tile**
Given the Control Centre fleet KPI strip ([KpiStrip.jsx](../../control-centre/src/components/live/KpiStrip.jsx)),
when the daily KPI window updates,
then a new **read-only** tile "delay-min avoided (24h)" renders the fleet-wide value sourced from a new cloud-backend endpoint `GET /api/v1/kpi/delay-minutes-avoided` (D3, D4). The tile:
- follows the existing `.kpi-tile` / `.kpi-tile__value` / `.kpi-tile__label` markup and uses **only** `--obb-*` tokens (CSS-token rule — see Dev Notes); it is **non-interactive** (a `<div>`, like the `active trains` tile, not a filter button — there is no feed filter for this metric);
- renders `—` when the value is unavailable (loading/error/empty), per the three-state rule (control-centre/CLAUDE.md);
- shows the value as whole minutes (e.g. `12`), label `delay-min avoided (24h)`.

**AC4 — KPI endpoint computes from columns that exist**
Given the new endpoint `cloud-backend/src/cloud_backend/routes/kpi.py` + `services/delay_minutes_avoided.py`,
when called,
then it returns `{ "delay_minutes_avoided_24h": <number>, "window_hours": 24 }`, computed over the trailing 24h from `escalation_audit` rows, defined as (D3):
> Σ over escalations that reached `resolved` within the window, of `seconds_to_departure` (joined from the `escalations` row — see D3 for the column add), counted **only** when the resolve happened **before** scheduled departure (i.e. the alert was acted on in-time), divided by 60.
The endpoint is auth-guarded with `Security(require_api_key)` exactly like [escalations_audit.py:24-26](../../cloud-backend/src/cloud_backend/routes/escalations_audit.py), registered in [main.py](../../cloud-backend/src/cloud_backend/main.py) via `include_router`, and is **read-only** (no migration on `escalation_audit`; the one schema add is on `escalations` — D3).

**AC5 — KPI added to the business-goals doc**
Given [01-Business-Goals.md](../design-artifacts/B-Trigger-Map/01-Business-Goals.md) Goal 2 (Make ÖBB Staff Measurably More Effective),
then a measurable success criterion is added referencing "delay-minutes avoided" as the operational proxy for Objective **2.2** (reduce door-obstruction-attributable delayed departures by ≥30%), naming the KPI tile as where it is observed.

**AC6 — Unit tests cover the derivation including the null path**
Given the `seconds_to_departure` computation,
then unit tests cover: (a) healthy pre-departure → correct positive seconds; (b) `scheduled_departure` already past → clamped to `0`; (c) empty/unparseable `scheduled_departure` → `None` (feed-degraded); (d) in-transit (not pre-departure) → `None`. The `contract` test from AC1 asserts the field is optional and omitted-when-None.

**AC7 — Conductor-App spec stub (Phase-2 gate)**
Given the Conductor-App banner + per-shift totaliser are descoped (epic AC8, D4),
then a spec stub `_bmad-output/design-artifacts/D-UX-Design/conductor-app-dwell-aware-alerts.md` is authored capturing the deferred UX (the `· {N}s to departure` suffix, the amber→red shift at `< 30s`, the "minutes saved this shift" totaliser) as a Phase-2 Conductor-App requirement, explicitly marked **not built in this story**, so the design intent is not lost.

## Decisions (locked — review before dev)

- **D1 — There is no `DWELL` state; derive `seconds_to_departure` from the shipped PIS substate. (PAYLOAD/STATE AUDIT)** The epic's "in `DWELL` state at a station" does not map to any shipped state. Verified: [context_state.py:70-76](../../vlan-pollers/src/vlan_pollers/context_state.py) tracks `station_approach: bool` (set/cleared by SNMP+GPS proximity per ADR-18 Trigger 3), `speed_kmh: float`, and a `pis: PisState` substate. `PisState.scheduled_departure` ([models.py:33](../../vlan-pollers/src/vlan_pollers/models.py)) is an **already-polled ISO-UTC string** ([pis_poller.py:57](../../vlan-pollers/src/vlan_pollers/pis_poller.py)). **Decision:** "pre-departure at a station" = `station_approach == true` OR (`speed_kmh == 0` AND `scheduled_departure` parses to a future instant). Derive `seconds_to_departure` from `scheduled_departure − now`. **No new poller, no ZFR integration, no new state machine** — the data is already in context-state. This keeps the change surgical (Karpathy #3) and uses the existing ADR-18 station-approach signal.

- **D2 — No `DWELL_FEED_DEGRADED` EventType; reuse the existing graceful-degradation log path. (PAYLOAD AUDIT / ADR FRESHNESS)** The epic asks for a `DWELL_FEED_DEGRADED` event on feed loss. Verified: no such member in [types.py](../../shared/src/oebb_shared/events/types.py), and `pis_poller` **already** degrades gracefully — missing fields become `""` and a failed poll logs `log.warning("pis_poll_failed", recoverable=True)` ([pis_poller.py:57,69](../../vlan-pollers/src/vlan_pollers/pis_poller.py)). Adding a new EventType + payload class is a Tier-3 contract change that cascades to event-store ingest, the EventType registry, and contract tests — disproportionate to "the departure time was unknown for one alert." **Decision:** the feed-degraded path is simply `seconds_to_departure = None` plus a structured log line (AC2); **do not** add `DWELL_FEED_DEGRADED`. Because no EventType, payload shape, or fusion ingest endpoint changes in a way that contradicts an existing ADR, **no ADR update is required** (ADR-FRESHNESS rule checked: the additive optional field on `AlertRaisedPayload` does not contradict ADR-20/21/22; the highest existing ADR is ADR-22). If the dev disagrees and wants a new EventType, that is a scope escalation — surface it, do not just add it.

- **D3 — The KPI cannot read from `escalation_audit` as the epic claims; one additive column on `escalations` is the minimum. (PAYLOAD AUDIT)** Epic AC4 says compute "from `escalation_audit` rows where outcome_tag indicates an in-time resolution." Verified against the shipped schema: [escalation_audit](../../cloud-backend/migrations/versions/0007_escalation_audit.py) has `t_fired`, `t_event`, `action_tags`, `transition`, `confidence_*` — **no `seconds_to_departure`, no `scheduled_departure`, no "in-time" concept**, and `action_tags` are the four landside tags (`resolved_remotely`/`field_team_dispatched`/`false_alarm`/`no_action_needed`) — none of which means "in-time." **Decision:** to compute "delay-minutes avoided" we need, per resolved escalation, (i) the `seconds_to_departure` at raise time and (ii) whether resolve preceded scheduled departure. The minimum shipped-compatible change is **one additive nullable column `seconds_to_departure INTEGER NULL` on the `escalations` table** (Alembic 0008, new-column-only → safe under concurrent reads per cloud-backend/CLAUDE.md), populated from the payload at the `ALERT_RAISED → escalation upsert` (the 10-6 ingest path). The KPI then sums `seconds_to_departure / 60` over rows that reached `resolved` and whose resolve time was before `t_fired + seconds_to_departure` (the in-time test, expressed in columns that exist). **Open sub-decision for dev:** if the team prefers zero schema change, the alternative is to denormalise `seconds_to_departure` onto the `escalation_audit` `raised` row (it already denormalises `confidence_*`/`model_versions` — same pattern) and read it there. **Recommended: the `escalations` column** (single source, the upsert already writes that row; the audit table stays append-only telemetry). Pick one and note it in the Dev Agent Record — do not invent an "outcome_tag = in-time" that does not exist.

- **D4 — Conductor App is out of scope; ship the CC tile (read-only) + a spec stub. (SCOPE)** Epic AC2/AC3 describe a Conductor-App banner and a "minutes saved this shift" totaliser. The Conductor App is not part of the PoC Control Centre (epic AC8 descopes it; the actor model — memory `project-actor-model-conrad` — has no on-train human ack on the default conductorless case). The CC KPI strip is fed by `useFleetData()` (SSE/WS — [LiveMonitoring.jsx:13](../../control-centre/src/components/live/LiveMonitoring.jsx)), **not** the analytics REST path. **Decision:** ship (a) the CC "delay-min avoided (24h)" tile reading the new REST endpoint, and (b) a Conductor-App spec stub (AC7) preserving the deferred UX. The CC tile is **non-interactive** (no feed filter exists for a derived KPI). Wiring the tile's data: add a small fetch (24h KPI is a slow-changing daily value — a one-shot fetch on mount + interval refresh is sufficient; **do not** force it through the SSE `kpis` object, which is per-tick live state). If a dev wants it in the SSE payload instead, that is a backend ingest-worker change — flag it, don't assume it.

- **D5 — Honour shipped naming and the actor model.** Per memory `project-actor-model-conrad` (canonical) and 10-3/10-6: do not rename `conrad_flag`/`SOURCE_LABEL`/action-tag keys. The alert "source" is the on-train platform; the in-time-resolution actor on the default (conductorless) case is the landside Fleet Manager. The KPI copy must not imply an onboard human acted unless the train is Fernverkehr. Keep the tile label operator-neutral ("delay-min avoided").

## Tasks / Subtasks

- [ ] **T0 — Explore pass (large-codebase discipline)** — before editing, confirm the file list below by reading each UPDATE target in full (FULL-FILE-READS rule). UPDATE targets: `shared/.../payloads.py`, `fusion/src/fusion/enrichment.py` (+ the emit_alert call site), `cloud-backend/.../main.py`, `control-centre/.../KpiStrip.jsx` + `KpiStrip.css` + `LiveMonitoring.jsx`, `01-Business-Goals.md`. Document current-state / what-changes / what-must-be-preserved for each in the Dev Agent Record.

- [ ] **T1 — `shared/`: add `seconds_to_departure` to `AlertRaisedPayload`** (AC1, D1, D2)
  - [ ] Add `seconds_to_departure: int | None = None` (additive, optional, non-negative when set).
  - [ ] Extend `_serialize` `_drop_none` set so the field is omitted when `None` (byte-compat with existing consumers).
  - [ ] Add a `contract` test (`-m contract`) asserting the field is optional + omitted-when-None + accepted-when-int.
  - [ ] `python -m pytest -m "unit or contract"`, `ruff`, `mypy src/` clean in `shared/`.

- [ ] **T2 — `fusion/`: derive and stamp `seconds_to_departure`** (AC2, AC6, D1, D2)
  - [ ] In the alert-enrichment path, read `context_state` (`station_approach`, `speed_kmh`, `pis.scheduled_departure`); compute `max(0, floor(scheduled_departure_epoch − now_epoch))` when pre-departure + parseable; else `None`.
  - [ ] **Async-safety:** snapshot `context_state` values before any `await` (project-context async stale-closure rule); do not re-read after awaiting.
  - [ ] Reuse the ISO-UTC parse already validated in shared (`_validate_iso_utc` style); on parse failure → `None` + structured log (no raise, no new EventType).
  - [ ] RED first: write the four AC6 cases (healthy / past-clamped-to-0 / unparseable→None / in-transit→None) and watch them fail, then implement.
  - [ ] `python -m pytest` in `fusion/` green; coverage ≥ project bar; `mypy --strict` + `ruff` clean.

- [ ] **T3 — `cloud-backend/`: schema column + KPI endpoint** (AC4, D3)
  - [ ] Alembic **0008**: `ALTER TABLE escalations ADD COLUMN seconds_to_departure INTEGER NULL` (new-column-only; verify safe-under-concurrent-reads, no table rewrite). Down-migration drops it.
  - [ ] Populate the column in the `ALERT_RAISED → escalation upsert` (10-6 ingest path) from the payload's `seconds_to_departure`.
  - [ ] `services/delay_minutes_avoided.py`: SQL summing `seconds_to_departure/60` over escalations `resolved` in the trailing 24h whose `t_resolve < t_fired + (seconds_to_departure || ' seconds')::interval` (in-time). Use the DB clock for the window (skew-proof, like the funnel's `NOW()` pattern).
  - [ ] `routes/kpi.py`: `GET /api/v1/kpi/delay-minutes-avoided`, `Security(require_api_key)`, returns `{delay_minutes_avoided_24h, window_hours: 24}`; register in `main.py`. Define the JSON response as a Pydantic model in `api/kpi.py` (mirror the `api/escalations_audit.py` → `AlertFunnel` response-model split — routes/ hold handlers only, api/ holds the response models, per cloud-backend/CLAUDE.md). **`escalations` columns confirmed present** (0006): `t_fired`, `t_resolve` (nullable), `status`, `alert_code` — the in-time SQL below is buildable against them.
  - [ ] Unit + integration test (testcontainers Postgres): seeded in-time resolves sum correctly; out-of-time / unresolved / null-seconds rows excluded; empty window → 0.
  - [ ] `python -m pytest`, `ruff`, `mypy src/` clean in `cloud-backend/`.

- [ ] **T4 — `control-centre/`: KPI tile** (AC3, D4)
  - [ ] Add a non-interactive `delay-min avoided (24h)` tile to `KpiStrip.jsx` (mirror the `active trains` `<div>` tile; `—` on missing).
  - [ ] CSS: reuse existing `.kpi-tile*` classes; if any new rule is needed use **only** `--obb-*` tokens (no hex, no `--obb-sev-warning`/`--obb-sev-danger` — they don't exist; see Dev Notes token list).
  - [ ] Data: one-shot fetch of `/api/v1/kpi/delay-minutes-avoided` on mount + interval refresh (a hook under `src/hooks/`), passed into `KpiStrip`; **not** through the live SSE `kpis` object (D4). Handle loading/error/empty (three-state rule).
  - [ ] **Browser-verify (required, not optional — control-centre/CLAUDE.md):** `npm run dev`, render the tile via Claude Preview / `verify` skill; confirm golden path (populated) + one edge state (empty → `—`); console clean. `npm run lint` clean (incl. no `src/mock/` import in the new path).

- [ ] **T5 — Business-goals doc + Conductor-App spec stub** (AC5, AC7)
  - [ ] Add the "delay-minutes avoided" measurable criterion under Goal 2 / Objective 2.2 in [01-Business-Goals.md](../design-artifacts/B-Trigger-Map/01-Business-Goals.md).
  - [ ] Author `_bmad-output/design-artifacts/D-UX-Design/conductor-app-dwell-aware-alerts.md` (the deferred banner suffix + amber→red `<30s` + per-shift totaliser), marked **Phase 2 — not built in 10-4**.

- [ ] **T6 — Self-review + sentinel + commit** (DoD)
  - [ ] Run `bmad-security-sentinel` (touches `shared/` payload + ingest path + a new auth-guarded endpoint — sentinel scope: no secrets, JWT/api-key trust on the new route, no raw-video/PII in the new field or KPI). No prompt-injection surface added (the new field is an `int` derived server-side, not external free-text).
  - [ ] Confirm no ADR contradiction (D2): if dev chose the D3 alternative or added an EventType against recommendation, add the ADR-update checkbox here.
  - [ ] Per CLAUDE.md git rule: stage only this story's files, commit `feat(...)` with the agent block, push `origin master`.

## Dev Notes

### CSS design tokens (CSS-TOKEN persistent rule — the KPI tile is CSS)

The new tile must use these `--obb-*` tokens from `control-centre/src/styles/colors_and_type.css` (existing `KpiStrip.css` already uses `--obb-surface-1`, `--obb-border-dark`, `--obb-text-on-dark-1/3`, `--obb-sev-critical`, `--obb-sev-medium`). **Do not use hex literals or invent token names.**

- **Severity ramp:** `--obb-sev-critical` (red), `--obb-sev-high` (orange), `--obb-sev-medium` (amber), `--obb-sev-advisory` (blue), `--obb-sev-normal` (green).
- **Common mistakes (have caused review cycles):** `--obb-sev-warning` does **NOT** exist → use `--obb-sev-medium`. `--obb-sev-danger` does **NOT** exist → use `--obb-sev-critical`.
- **Surfaces:** `--obb-surface-0..5`. **Text on dark:** `--obb-text-on-dark-1..4`. **Borders:** `--obb-border-dark` / `--obb-border-bright`. **Typography:** `--font-mono` (IDs/timestamps), `--font-size-sm`.
- The "delay-min avoided" tile is a positive/neutral metric — render in the default `--obb-text-on-dark-1` (the plain `.kpi-tile__value`), **not** a severity colour. It is not an alert.

### Shipped-contract ground truth (cite these, don't reinvent)

- **`AlertRaisedPayload`** — [payloads.py:94-139](../../shared/src/oebb_shared/events/payloads.py): `alert_code` is `_NonEmptyStr` (not an enum); `confidence_score: float | None`; `_serialize` already drops `None` `priority` via `_drop_none` (**use this pattern for `seconds_to_departure`**).
- **PIS source** — [models.py:30-36](../../vlan-pollers/src/vlan_pollers/models.py) `PisState.scheduled_departure: str` (ISO-UTC, `""` = unknown), polled at [pis_poller.py:57](../../vlan-pollers/src/vlan_pollers/pis_poller.py), pushed to context-state at [context_state.py:88-90](../../vlan-pollers/src/vlan_pollers/context_state.py).
- **Pre-departure signal** — [context_state.py:70-76](../../vlan-pollers/src/vlan_pollers/context_state.py) `station_approach: bool` (ADR-18 Trigger 3: set within 2 min of scheduled station, cleared when speed > 20 km/h after stop).
- **escalation_audit** — [0007_escalation_audit.py](../../cloud-backend/migrations/versions/0007_escalation_audit.py): append-only, denormalises `t_fired`/`alert_code`/`confidence_*`/`model_versions`; **no `seconds_to_departure`** (D3). Funnel query pattern (DB-clock window, `Security(require_api_key)`, `include_router`): [escalations_audit.py](../../cloud-backend/src/cloud_backend/routes/escalations_audit.py) — **clone its auth + window + skew-proof `NOW()` shape** for the KPI endpoint. The funnel's response model `AlertFunnel` lives in [api/escalations_audit.py](../../cloud-backend/src/cloud_backend/api/escalations_audit.py) — put the KPI response model in `api/kpi.py` the same way.
- **escalations table (where D3's column lands + what the KPI reads)** — [0006_escalations.py](../../cloud-backend/migrations/versions/0006_escalations.py): columns `escalation_id`, `alert_code`, `status` (`unacknowledged|acknowledged|resolved`), `t_fired` (not-null), `t_ack`/`t_resolve` (nullable), `confidence_*`, `action_tags`. The KPI's "resolved in-time" = `status='resolved' AND t_resolve < t_fired + seconds_to_departure*interval`. Add `seconds_to_departure INTEGER NULL` alongside `confidence_score` (Alembic 0008).
- **escalations upsert (where to write the new column)** — the `ALERT_RAISED → escalation upsert` is the 10-6 ingest path; the same UPDATE/INSERT already denormalises confidence — add `seconds_to_departure` alongside.
- **KPI strip data flow** — `useFleetData()` (SSE/WS) feeds `kpis` into `<KpiStrip kpis=… />` at [LiveMonitoring.jsx:13](../../control-centre/src/components/live/LiveMonitoring.jsx). The new 24h KPI is **not** live per-tick state — fetch it separately (D4).

### Async stale-closure trap (project-context rule)

T2's derivation runs in fusion's async enrichment path. **Snapshot `context_state.station_approach`, `speed_kmh`, and `pis.scheduled_departure` before the first `await`**; do not re-read after awaiting (a concurrent poller push could change them mid-computation). See the Python asyncio pattern in `project-context.md` "Async callbacks".

### UPDATE-file read log (FULL-FILE-READS rule — to be completed by dev in T0)

The dev agent must read each UPDATE target in full before editing and record current-state / what-changes / what-must-be-preserved. Files already read at story-creation time (current state captured): `payloads.py` (AlertRaisedPayload + `_drop_none` serializer), `KpiStrip.jsx`/`KpiStrip.css` (tile markup + token usage), `pis_poller.py`/`models.py`/`context_state.py` (PIS source + state), `escalation_audit` migration + funnel route, `main.py` router mounting, `LiveMonitoring.jsx` (KPI data flow), `01-Business-Goals.md`. Not yet read (dev must read before T2/T3): `fusion/src/fusion/enrichment.py` full file + the `emit_alert` call site; the 10-6 `routes/ingest.py` escalation-upsert block.

### Failure scenarios this story must survive (OEBB-specific)

1. **Midnight-crossing departure / clock skew:** an alert raised at 23:58 for a `scheduled_departure` of 00:05 the next day must yield `seconds_to_departure ≈ 420`, not a negative number from a date-only subtraction. Parse the full ISO-UTC instant (not just the time-of-day); the `journey_id` ADR-2 midnight rule is a precedent for why date handling here is a known trap. Test it.
2. **Feed-degraded does not poison the KPI:** when `scheduled_departure` is `""` for a stretch (PIS poller offline), every alert in that window carries `seconds_to_departure = None`; those escalations must be **excluded** from the delay-minutes-avoided sum (not counted as 0 in-time saves), and the tile must not crash or show `NaN` — it shows the sum of the rows that *do* have a value, or `—`/`0` if none. Integration-test a window mixing null-seconds and valued rows.

### Project Structure Notes

- New files: `cloud-backend/.../routes/kpi.py`, `cloud-backend/.../services/delay_minutes_avoided.py`, Alembic `0008_*`, `control-centre/src/hooks/useDelayMinutesAvoided.js` (or similar), `_bmad-output/design-artifacts/D-UX-Design/conductor-app-dwell-aware-alerts.md`. All align with existing per-package conventions (routes/ vs services/ vs api/; hooks/ naming).
- This story spans **four** code subpackages + one planning doc. Read each subpackage CLAUDE.md before touching it (shared = no FastAPI/framework deps; cloud-backend = no sync DB calls, migrations are generated-then-reviewed; control-centre = no TS, no hex, three-state, browser-verify).

### Permission Tiers (per CLAUDE.md story standard)

| Action | Tier | Note |
|---|---|---|
| `shared/` payload field, `fusion/` derivation, CC tile, docs | 2 (local edits) | normal dev mode |
| Event-schema field on `AlertRaisedPayload` + Alembic 0008 migration | **3** | **default permission mode** (shared contract + DB migration — CLAUDE.md: Tier-3 shared-infra actions use default mode regardless of session mode) |

### References

- [Source: epics.md#Story-E10-S4 (lines 2307-2338)] — original AC text (implement the *resolved* shapes, not the prose; see the divergence table)
- [Source: shared/src/oebb_shared/events/payloads.py:94-139] — `AlertRaisedPayload` + `_drop_none` serializer
- [Source: vlan-pollers/src/vlan_pollers/{models.py,pis_poller.py,context_state.py}] — PIS `scheduled_departure` source + `station_approach`
- [Source: cloud-backend/migrations/versions/0007_escalation_audit.py + routes/escalations_audit.py] — audit schema (no seconds_to_departure — D3) + the funnel query/auth pattern to clone
- [Source: control-centre/src/components/live/{KpiStrip.jsx,KpiStrip.css,LiveMonitoring.jsx}] — tile markup, tokens, KPI data flow
- [Source: _bmad-output/design-artifacts/B-Trigger-Map/01-Business-Goals.md] — Goal 2.2 (the metric this KPI proves)
- [Source: project memory project-actor-model-conrad] — actor model (no onboard human on conductorless default; naming locked — D5)
- [Source: ADR-18 (architecture.md) Trigger 3] — `station_approach` set/clear semantics; ADR-2 — midnight-crossing date trap precedent

## Dev Agent Record

### Context Reference
<!-- dev populates -->

### Agent Model Used
<!-- dev populates -->

### Pre-Flight
<!-- dev populates: assumptions, open questions, simplicity check, surgical-change test -->

### Debug Log References
<!-- dev populates -->

### Completion Notes List
<!-- dev populates; MUST record the D3 choice (escalations column vs audit denormalisation) and whether any D2 EventType escalation occurred -->

### File List
<!-- dev populates -->

### Change Log
<!-- dev populates -->
