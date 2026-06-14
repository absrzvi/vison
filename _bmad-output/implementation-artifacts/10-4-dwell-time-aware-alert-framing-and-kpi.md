---
baseline_commit: 4b4a840
---

# Story 10.4: Dwell-Time-Aware Alert Framing & Delay-Minutes-Avoided KPI

Status: done

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
then it returns `{ "delay_minutes_avoided": <number>, "window_hours": 24 }` (the window is carried in `window_hours`, not the key name — Round-1 review AC4 resolution), computed over the trailing 24h from the `escalations` rows, defined as (D3):
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

- **D1 — There is no `DWELL` state; derive `seconds_to_departure` from the shipped PIS substate. (PAYLOAD/STATE AUDIT)** The epic's "in `DWELL` state at a station" does not map to any shipped state. Verified: vlan-pollers [context_state.py:70-76](../../vlan-pollers/src/vlan_pollers/context_state.py) tracks `station_approach: bool` (set/cleared by SNMP+GPS proximity per ADR-18 Trigger 3), `speed_kmh: float`, and a `pis: PisState` substate. `PisState.scheduled_departure` ([models.py:33](../../vlan-pollers/src/vlan_pollers/models.py)) is an **already-polled ISO-UTC string** ([pis_poller.py:57](../../vlan-pollers/src/vlan_pollers/pis_poller.py)). **Decision:** "pre-departure at a station" = `station_approach == true` OR (`speed_kmh == 0` AND `scheduled_departure` parses to a future instant). Derive `seconds_to_departure` from `scheduled_departure − now`. **No new poller, no ZFR integration, no new state machine.**

  - **D1-PLUMBING (dev-story finding 2026-06-14, confirmed before RED):** the derivation runs in **fusion** (the only place `AlertRaisedPayload` is built), and fusion has its **own** `ContextState` ([fusion/context_state.py](../../fusion/src/fusion/context_state.py)) populated from `ContextPushModel` ([fusion/models.py:25](../../fusion/src/fusion/models.py)). vlan-pollers **already POSTs** `pis` to fusion `/context` (`_state_to_dict` includes `"pis"` — [vlan-pollers/context_state.py:114-124](../../vlan-pollers/src/vlan_pollers/context_state.py)), **but fusion's `ContextPushModel` has no `pis`/`scheduled_departure` field**, so Pydantic silently drops it and fusion never sees the departure time. **The minimal change is fusion-side only** (one package): add `scheduled_departure: str | None = None` to `ContextPushModel` + `ContextState` + `update_from_push` (present-replaces / absent-keeps, like the other optionals). No vlan-pollers change is needed — the data is already on the wire. This is slightly more than the original D1 wording ("already in context-state") implied; it is contained to fusion and rides the existing optional-push pattern. Tracked as task **T1.5** so the context-push contract change has its own RED tests before the derivation depends on it.

- **D2 — No `DWELL_FEED_DEGRADED` EventType; reuse the existing graceful-degradation log path. (PAYLOAD AUDIT / ADR FRESHNESS)** The epic asks for a `DWELL_FEED_DEGRADED` event on feed loss. Verified: no such member in [types.py](../../shared/src/oebb_shared/events/types.py), and `pis_poller` **already** degrades gracefully — missing fields become `""` and a failed poll logs `log.warning("pis_poll_failed", recoverable=True)` ([pis_poller.py:57,69](../../vlan-pollers/src/vlan_pollers/pis_poller.py)). Adding a new EventType + payload class is a Tier-3 contract change that cascades to event-store ingest, the EventType registry, and contract tests — disproportionate to "the departure time was unknown for one alert." **Decision:** the feed-degraded path is simply `seconds_to_departure = None` plus a structured log line (AC2); **do not** add `DWELL_FEED_DEGRADED`. Because no EventType, payload shape, or fusion ingest endpoint changes in a way that contradicts an existing ADR, **no ADR update is required** (ADR-FRESHNESS rule checked: the additive optional field on `AlertRaisedPayload` does not contradict ADR-20/21/22; the highest existing ADR is ADR-22). If the dev disagrees and wants a new EventType, that is a scope escalation — surface it, do not just add it.

- **D3 — The KPI cannot read from `escalation_audit` as the epic claims; one additive column on `escalations` is the minimum. (PAYLOAD AUDIT)** Epic AC4 says compute "from `escalation_audit` rows where outcome_tag indicates an in-time resolution." Verified against the shipped schema: [escalation_audit](../../cloud-backend/migrations/versions/0007_escalation_audit.py) has `t_fired`, `t_event`, `action_tags`, `transition`, `confidence_*` — **no `seconds_to_departure`, no `scheduled_departure`, no "in-time" concept**, and `action_tags` are the four landside tags (`resolved_remotely`/`field_team_dispatched`/`false_alarm`/`no_action_needed`) — none of which means "in-time." **Decision:** to compute "delay-minutes avoided" we need, per resolved escalation, (i) the `seconds_to_departure` at raise time and (ii) whether resolve preceded scheduled departure. The minimum shipped-compatible change is **one additive nullable column `seconds_to_departure INTEGER NULL` on the `escalations` table** (Alembic 0008, new-column-only → safe under concurrent reads per cloud-backend/CLAUDE.md), populated from the payload at the `ALERT_RAISED → escalation upsert` (the 10-6 ingest path). The KPI then sums `seconds_to_departure / 60` over rows that reached `resolved` and whose resolve time was before `t_fired + seconds_to_departure` (the in-time test, expressed in columns that exist). **Open sub-decision for dev:** if the team prefers zero schema change, the alternative is to denormalise `seconds_to_departure` onto the `escalation_audit` `raised` row (it already denormalises `confidence_*`/`model_versions` — same pattern) and read it there. **Recommended: the `escalations` column** (single source, the upsert already writes that row; the audit table stays append-only telemetry). Pick one and note it in the Dev Agent Record — do not invent an "outcome_tag = in-time" that does not exist.

- **D4 — Conductor App is out of scope; ship the CC tile (read-only) + a spec stub. (SCOPE)** Epic AC2/AC3 describe a Conductor-App banner and a "minutes saved this shift" totaliser. The Conductor App is not part of the PoC Control Centre (epic AC8 descopes it; the actor model — memory `project-actor-model-conrad` — has no on-train human ack on the default conductorless case). The CC KPI strip is fed by `useFleetData()` (SSE/WS — [LiveMonitoring.jsx:13](../../control-centre/src/components/live/LiveMonitoring.jsx)), **not** the analytics REST path. **Decision:** ship (a) the CC "delay-min avoided (24h)" tile reading the new REST endpoint, and (b) a Conductor-App spec stub (AC7) preserving the deferred UX. The CC tile is **non-interactive** (no feed filter exists for a derived KPI). Wiring the tile's data: add a small fetch (24h KPI is a slow-changing daily value — a one-shot fetch on mount + interval refresh is sufficient; **do not** force it through the SSE `kpis` object, which is per-tick live state). If a dev wants it in the SSE payload instead, that is a backend ingest-worker change — flag it, don't assume it.

- **D5 — Honour shipped naming and the actor model.** Per memory `project-actor-model-conrad` (canonical) and 10-3/10-6: do not rename `conrad_flag`/`SOURCE_LABEL`/action-tag keys. The alert "source" is the on-train platform; the in-time-resolution actor on the default (conductorless) case is the landside Fleet Manager. The KPI copy must not imply an onboard human acted unless the train is Fernverkehr. Keep the tile label operator-neutral ("delay-min avoided").

## Tasks / Subtasks

- [x] **T0 — Explore pass (large-codebase discipline)** — read each UPDATE target in full. **Key finding:** fusion has its own `ContextState`/`ContextPushModel` that does NOT carry `scheduled_departure` (vlan-pollers sends `pis` but fusion drops it) → D1-PLUMBING + T1.5. 10-6 ingest upsert reads `ev.payload.get(...)` with `ON CONFLICT (escalation_id) DO NOTHING` → clean write point for the new column. `escalations` (0006) has `t_fired`/`t_resolve`/`status` → D3 in-time SQL buildable. fusion DoD = `--cov-fail-under=90` + `mypy --strict` (fusion/CLAUDE.md). Alert emit goes through `enrichment.py` `emit_envelope`; `_severity_for` is the speed-correlated severity decision.

- [x] **T1 — `shared/`: add `seconds_to_departure` to `AlertRaisedPayload`** (AC1, D1, D2)
  - [x] Add `seconds_to_departure: _NonNegInt | None = None` (additive, optional, non-negative when set).
  - [x] Extend `_serialize` to chain a second `_drop_none(data, "seconds_to_departure")` so the field is omitted when `None` (byte-compat).
  - [x] Added 4 `contract` tests: optional+omitted-when-None, roundtrips-when-set, rejects-negative, survives-envelope-roundtrip-both-directions (regression guard — both services deserialise via `PAYLOAD_MODELS`).
  - [x] `shared`: 4/4 new green, **196/196** full suite (no regressions), `mypy src/` clean, no new `ruff` violations (1 pre-existing E501 at payloads.py:426 `expect_orphan`, unrelated — left per surgical-change rule).

- [x] **T1.5 — `fusion/`: plumb `scheduled_departure` into fusion ContextState** (AC2, D1-PLUMBING)
  - [x] RED tests: `/context` push carrying `scheduled_departure` lands on `ContextState`; absent field keeps prior (present-replaces/absent-keeps).
  - [x] Added `scheduled_departure: str | None = None` to `ContextPushModel` ([fusion/models.py:64-67](../../fusion/src/fusion/models.py)) and `ContextState` ([fusion/context_state.py:42-45](../../fusion/src/fusion/context_state.py)); wired in `update_from_push`.
  - [x] No vlan-pollers change (already sends `pis`); fusion stops dropping it. `mypy --strict` + `ruff` clean.

- [x] **T2 — `fusion/`: derive and stamp `seconds_to_departure`** (AC2, AC6, D1, D2)
  - [x] `_seconds_to_departure()` pure helper in [enrichment.py:22-52](../../fusion/src/fusion/enrichment.py): `max(0, floor(sched_epoch − now_epoch))` when pre-departure (`station_approach OR speed==0`) + parseable; else `None`.
  - [x] **Async-safety:** `emit_alert` snapshots `speed_kmh`/`station_approach` before the single `await self._post_envelope`; `now=datetime.now(UTC)` computed at build time.
  - [x] Reuses shared `TIMESTAMP_RE` (the ISO-UTC-with-Z validator) — a non-Z/empty/malformed departure → `None`, no raise, no new EventType (D2). Full-instant parse handles the midnight-crossing case (tested).
  - [x] 6 derivation cases (healthy / standstill / past→0 / midnight-cross / unparseable×3→None / in-transit→None) + 2 emit-integration (stamped-when-pre-departure / dropped-in-transit) + 2 plumbing = 12 new tests.
  - [x] `fusion`: **170 passed, 93.56% cov** (gate ≥90; enrichment.py 98%), `mypy --strict` clean (13 files), `ruff` clean.

- [x] **T3 — `cloud-backend/`: schema column + KPI endpoint** (AC4, D3)
  - [x] Alembic **0008** ([0008_escalation_seconds_to_departure.py](../../cloud-backend/migrations/versions/0008_escalation_seconds_to_departure.py)): `op.add_column` nullable `seconds_to_departure INTEGER` — additive, no rewrite, idempotent (verified by `test_upgrade_head_idempotent`). Down-migration drops it.
  - [x] Populated in the `ALERT_RAISED → escalation upsert` ([ingest.py:127-153](../../cloud-backend/src/cloud_backend/routes/ingest.py)) from `ev.payload.get("seconds_to_departure")` — verified by `test_ingest_stamps_seconds_to_departure`.
  - [x] [services/delay_minutes_avoided.py](../../cloud-backend/src/cloud_backend/services/delay_minutes_avoided.py): `SUM(seconds_to_departure)/60` over escalations `status='resolved'`, non-NULL seconds, `t_resolve` in trailing 24h, and `t_resolve < t_fired + make_interval(secs => seconds_to_departure)` (in-time). DB-clock window (`NOW()`), skew-proof.
  - [x] [routes/kpi.py](../../cloud-backend/src/cloud_backend/routes/kpi.py): `GET /api/v1/kpi/delay-minutes-avoided`, `Security(require_api_key)`, returns `{delay_minutes_avoided, window_hours: 24}`; response model in [api/kpi.py](../../cloud-backend/src/cloud_backend/api/kpi.py) (mirrors the `AlertFunnel` split); registered in `main.py`.
  - [x] 8 integration tests (real Postgres via testcontainers): empty→0; in-time summed; late-resolve / null-seconds / unresolved / outside-24h excluded; ingest stamps the column; auth required. **8/8 deterministic across 3 runs.**
  - [x] `cloud-backend`: mypy clean (34 files), ruff clean (new files), unit 92/92, full suite **176/176** on a clean run; coverage **83%** (≥80 bar; kpi.py 92%, service 83%).
  - **Pre-existing flake (NOT this story):** 3 `test_escalation_audit.py` tests (`test_funnel_aggregates_per_alert_code`, `test_funnel_filter_by_alert_code`, `test_full_lifecycle_appends_three_rows`) fail ~2-3 of 4 runs **on the untouched baseline ca4a219** (verified by stash + re-run). Root cause: fixtures client-stamp `t_event`/`t_fired` (`datetime.now(UTC)`, ms-truncated) while the funnel window upper bound and the `ORDER BY t_event` use the DB clock — a client-vs-DB clock-skew race. My change (one additive INSERT column) does not touch `t_event` or ordering. Flagged as a separate task; do not block 10-4 on it.

- [x] **T4 — `control-centre/`: KPI tile** (AC3, D4)
  - [x] Added a non-interactive `delay-min avoided (24h)` `<div>` tile to [KpiStrip.jsx](../../control-centre/src/components/live/KpiStrip.jsx) (mirrors the `active trains` tile; `Math.round(value)` whole minutes; `—` when not a number). New `delayMinutesAvoided` prop.
  - [x] **No CSS change** — reuses existing `.kpi-tile` / `.kpi-tile__value` / `.kpi-tile__label` (all `--obb-*` tokens already; positive metric → default `--obb-text-on-dark-1`, not a severity colour).
  - [x] [api/kpi.js](../../control-centre/src/api/kpi.js) + [hooks/useDelayMinutesAvoided.js](../../control-centre/src/hooks/useDelayMinutesAvoided.js): one-shot fetch on mount + 5-min interval, `AbortController` cleanup, returns `null` until/​on-error (three-state); wired in [LiveMonitoring.jsx](../../control-centre/src/components/live/LiveMonitoring.jsx). **NOT** on the live SSE `kpis` object (D4). No `src/mock/` import.
  - [x] **Browser-verified (Claude Preview, port 5173):** golden path — stubbed `12.6` → tile renders **`13`** (round correct); edge state — no backend → fetch fails → tile shows **`—`** (no crash/NaN). Console: zero errors from my code (the `getDelayMinutesAvoided` failure degrades silently to `—`; only pre-existing `[FleetContext] fetchTrainAlerts` mock-mode errors present). Screenshot captured.
  - [x] Tests: [api/__tests__/kpi.test.js](../../control-centre/src/api/__tests__/kpi.test.js) 3/3; full vitest **250/250** (was 247; +3, no regressions). My new files are eslint-clean; the project lint gate is pre-existing red (34 errors in 5 unrelated files — FleetContext/mock/vite.config/etc. + pre-existing `Date.now()` purity violations in KpiStrip/LiveMonitoring lines I did not author).

- [x] **T5 — Business-goals doc + Conductor-App spec stub** (AC5, AC7)
  - [x] Added the "delay-minutes avoided (24h)" measurable criterion under Goal 2 / Objective **2.2** in [01-Business-Goals.md](../design-artifacts/B-Trigger-Map/01-Business-Goals.md), defining it as the operator-observable proxy with its exact computation + exclusion rule.
  - [x] Authored [conductor-app-dwell-aware-alerts.md](../design-artifacts/D-UX-Design/conductor-app-dwell-aware-alerts.md): deferred banner `· {N}s to departure` suffix, amber→red `<30s` shift (correct `--obb-sev-medium`/`--obb-sev-critical` tokens), per-shift totaliser, actor-model note. Marked **Phase 2 — NOT built in 10-4**.

- [x] **T6 — Self-review + sentinel + commit** (DoD)
  - [x] `bmad-security-sentinel` → **APPROVED** (no Critical/Major). New KPI endpoint is api-key-guarded + takes no user input; `seconds_to_departure` is server-derived + schema-validated (no prompt-injection / untrusted-input surface); no secrets, no raw-video/CCTV/Conrad path, zero new deps.
  - [x] **No ADR contradiction (D2 confirmed):** additive optional field + new-column migration + new read endpoint contradict no existing ADR (ceiling ADR-22); chose the recommended D3 (column on `escalations`, not audit denormalisation); added no new EventType. No ADR-update checkbox needed.
  - [x] Final gate sweep all green: shared 196 + mypy; fusion 170 (cov 93.56%, ≥90) + mypy --strict; cloud-backend 176 + mypy; CC vitest 250. Browser-verified.
  - [x] Staged **only** the 10-4 files (excluded the unrelated external `test_escalation_audit.py` flake fix — see Completion Notes); committed `feat(...)` with agent block; pushed `origin master`.

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

Story self-contained. Key shipped contracts cited inline: `AlertRaisedPayload` (shared), fusion `ContextState`/`Enrichment`, 10-6 `escalations` table + ingest upsert, 10-2 `escalation_audit` funnel pattern, CC `KpiStrip`.

### Agent Model Used

claude-opus-4-8[1m] (Claude Opus 4.8, 1M context)

### Pre-Flight

**Assumptions**
- The `seconds_to_departure` derivation belongs in fusion's enrichment path — the only producer of `AlertRaisedPayload`.
- vlan-pollers already POSTs `pis.scheduled_departure` to fusion `/context`; fusion drops it (no field on `ContextPushModel`). Fixed in T1.5.
- Pre-departure = `station_approach == true` OR (`speed_kmh == 0` AND `scheduled_departure` parses to a future instant) — D1.
- The D3 minimum is one additive nullable column on `escalations` (not `escalation_audit`); the 10-6 ingest upsert is the write point (confirmed: `ON CONFLICT (escalation_id) DO NOTHING`, reads `ev.payload.get(...)`).

**Open Questions** — one surfaced and resolved with the user before RED: D1 understated the fusion plumbing (fusion can't see `scheduled_departure`). User chose "build full story"; D1-PLUMBING + task T1.5 added. No remaining blockers.

**Simplicity Check**
- Add: `scheduled_departure` to fusion `ContextPushModel`/`ContextState` (T1.5); derivation helper (T2); `seconds_to_departure` optional field on shared `AlertRaisedPayload` (T1); `escalations.seconds_to_departure` col + KPI service/route + `api/kpi.py` response model (T3); CC tile + fetch hook (T4); docs (T5).
- Rejected: new `DWELL_FEED_DEGRADED` EventType (D2 — reuse graceful log); new poller (data already on the wire); a `pis` sub-object on fusion's push model (only `scheduled_departure` is needed — keep the contract minimal); forcing the 24h KPI through the live SSE `kpis` object (D4 — separate slow-changing fetch).

**Surgical-Change Test** — file→AC trace:
- `shared/.../payloads.py` + contract test → AC1
- `fusion/.../models.py`, `context_state.py` → AC2 (T1.5 plumbing); `fusion/.../enrichment.py` (or health.py emit path) + tests → AC2/AC6
- `cloud-backend/.../migrations/0008`, `routes/ingest.py`, `services/delay_minutes_avoided.py`, `routes/kpi.py`, `api/kpi.py`, `main.py` + tests → AC4 (+ AC3 data source)
- `control-centre/.../KpiStrip.jsx`, `KpiStrip.css`, `hooks/useDelayMinutesAvoided.js`, `LiveMonitoring.jsx` → AC3
- `01-Business-Goals.md` → AC5; `conductor-app-dwell-aware-alerts.md` → AC7

### Debug Log References

- `grep alert_code= fusion/src/` + read of fusion `enrichment.py`/`context_state.py`/`models.py` → confirmed D1-PLUMBING (fusion drops vlan-pollers' `pis`).
- RED runs: shared contract tests (3 fail `extra_forbidden`), fusion (collection ImportError on `_seconds_to_departure`) — both failed for the right reason before GREEN.
- Flaky-test attribution: stashed all my changes → 3 `test_escalation_audit.py` tests still fail 2-3/4 on baseline ca4a219 → **pre-existing**, not from 10-4.

### Completion Notes List

- **D3 choice = the recommended option: one additive `seconds_to_departure INTEGER NULL` column on `escalations` (Alembic 0008), not denormalisation onto `escalation_audit`.** Single source of truth; the 10-6 ingest upsert already writes that row. The KPI sums `seconds_to_departure/60` over `status='resolved'` rows whose `t_resolve < t_fired + make_interval(secs => seconds_to_departure)` (in-time), DB-clock window.
- **D2 honoured: no `DWELL_FEED_DEGRADED` EventType added.** Feed-degraded path = `seconds_to_departure=None`. No new EventType, no ADR change (additive optional field doesn't contradict ADR-20/21/22).
- **D1-PLUMBING (Pre-Flight finding, user-approved "build full story"):** fusion's `ContextPushModel`/`ContextState` did not carry `scheduled_departure` (vlan-pollers sends `pis`, fusion dropped it). Added the field fusion-side only (T1.5) — no vlan-pollers change. Snapshot-before-await in `emit_alert` honours the async stale-closure rule.
- **Conductor App (D4):** out of scope — shipped the CC read-only tile (REST, not SSE) + a Phase-2 spec stub. Epic AC2/AC3 (onboard banner colour-shift + per-shift totaliser) deferred per epic AC8.
- **PRE-EXISTING flake NOT caused by 10-4:** 3 `test_escalation_audit.py` tests (funnel ×2 + full-lifecycle) failed ~2-3/4 on the untouched baseline (client-vs-DB clock skew in the test fixtures). Flagged as a separate task. **A fix for this landed in my working tree from outside this story** (a back-dating + explicit-`to`-window change to `test_escalation_audit.py`); with it present the suite is deterministically 176/176. **That test-file change was deliberately EXCLUDED from the 10-4 commit** (CLAUDE.md: stage only this milestone's files) — it belongs to the flaky-test task.
- **Pre-existing tech debt left untouched (surgical-change rule):** project-wide eslint debt (34 errors in FleetContext/mock/vite.config/etc. + `react-hooks/purity` `Date.now()` violations in KpiStrip/LiveMonitoring lines I did not author); `payloads.py:426` E501 (`expect_orphan`, story 4-8). None introduced by 10-4.

### File List

**shared/**
- `src/oebb_shared/events/payloads.py` (EDIT — `seconds_to_departure` field + serializer drop — AC1)
- `tests/contract/test_alert_raised_compat.py` (EDIT — 4 contract tests — AC1)

**fusion/**
- `src/fusion/models.py` (EDIT — `scheduled_departure` on `ContextPushModel` — T1.5)
- `src/fusion/context_state.py` (EDIT — `scheduled_departure` field + `update_from_push` — T1.5)
- `src/fusion/enrichment.py` (EDIT — `_seconds_to_departure` helper + `emit_alert` stamping — AC2)
- `tests/unit/test_enrichment.py` (EDIT — 12 tests — AC2/AC6/T1.5)

**cloud-backend/**
- `migrations/versions/0008_escalation_seconds_to_departure.py` (NEW — AC4/D3)
- `src/cloud_backend/routes/ingest.py` (EDIT — persist `seconds_to_departure` on upsert — AC4)
- `src/cloud_backend/services/delay_minutes_avoided.py` (NEW — AC4)
- `src/cloud_backend/api/kpi.py` (NEW — AC4 response model)
- `src/cloud_backend/routes/kpi.py` (NEW — AC4 endpoint)
- `src/cloud_backend/main.py` (EDIT — register `kpi_router` — AC4)
- `tests/integration/test_delay_minutes_avoided.py` (NEW — 8 tests — AC4)

**control-centre/**
- `src/api/kpi.js` (NEW — AC3)
- `src/hooks/useDelayMinutesAvoided.js` (NEW — AC3)
- `src/components/live/KpiStrip.jsx` (EDIT — tile + prop — AC3)
- `src/components/live/LiveMonitoring.jsx` (EDIT — wire hook → tile — AC3)
- `src/api/__tests__/kpi.test.js` (NEW — AC3)

**docs/**
- `_bmad-output/design-artifacts/B-Trigger-Map/01-Business-Goals.md` (EDIT — KPI under Goal 2.2 — AC5)
- `_bmad-output/design-artifacts/D-UX-Design/conductor-app-dwell-aware-alerts.md` (NEW — Phase-2 stub — AC7)

**bookkeeping**
- `_bmad-output/implementation-artifacts/10-4-dwell-time-aware-alert-framing-and-kpi.md` (EDIT — story record)
- `_bmad-output/implementation-artifacts/sprint-status.yaml` (EDIT — status)

> **Explicitly NOT in this story's commit:** `cloud-backend/tests/integration/test_escalation_audit.py` — an external flaky-test fix present in the working tree; belongs to the separate flaky-test task.

### Change Log

- 2026-06-14 — Implemented E10-S4 (dwell-time KPI): `seconds_to_departure` on `AlertRaisedPayload` (shared) + fusion derivation/plumbing + `escalations` column (Alembic 0008) + `/api/v1/kpi/delay-minutes-avoided` endpoint + Control Centre KPI tile + business-goal wiring + Conductor-App Phase-2 spec stub. Pre-Flight surfaced + resolved the fusion-plumbing gap (D1-PLUMBING, T1.5). Security-sentinel APPROVED. Gates: shared 196, fusion 170 (cov 93.56%), cloud-backend 176, CC vitest 250 — all green; mypy clean across packages. Status ready-for-dev → review.
- 2026-06-14 — Code-review Round 1 (multi-agent adversarial, wf_eb03b492): **BLOCKED**. 10 findings (1 blocker, 2 high, 2 medium, 4 low), all confirmed against live code by independent skeptics. Headline: the `scheduled_departure` plumbing is **dead in production** (vlan-pollers sends it nested under `pis`; fusion reads a flat top-level key it never receives → KPI permanently empty) and the unit tests masked it by constructing `ContextPushModel` synthetically. Status review → in-progress.
- 2026-06-14 — Round-1 fixes applied (all 10 findings). BLOCKER fixed via a targeted PIS push (vlan-pollers `update_pis` → fusion, mirroring `set_station_approach`) — strictly more minimal than the proposed fusion-`pis`-sub-model, zero fusion-model change, zero blast radius; real-producer contract test added (fusion `/context` ← actual wire body). Journey-change reset, AC2 degraded log, speed-branch future-gate, log snapshot, single-`now` boundary, AC4 prose, CC per-`load` AbortController all fixed. Pre-existing full-delta `extra='forbid'` 422 flagged as a follow-up (no longer load-bearing). Gates: vlan-pollers 89 / shared 176 / fusion 175 (93.68%) / cloud-backend KPI 8 / CC vitest 250 — all green; mypy --strict clean; browser re-verified. Status in-progress → review.

## Senior Developer Review (AI) — Round 1

**Reviewer:** Multi-agent adversarial workflow (wf_eb03b492 — bug-hunter + edge-case-hunter + acceptance-auditor + cross-package-contract layers, each finding verified by an independent skeptic against live code). 15 agents. **Date:** 2026-06-14. **Outcome: BLOCKED — story cannot be marked DONE.**

> ⚠️ **Reviewer-independence caveat:** this review was run by the same model family (Opus 4.8) that implemented the story, via independent subagents that replayed the real wire format the implementer's tests bypassed. It caught a blocker the implementer's own suite missed. A genuinely different model (or `/code-review ultra`) would be an even stronger second pass, but the wire-replay methodology surfaced the core defect.

**10 findings confirmed against live code: 1 blocker · 2 high · 2 medium · 4 low. Zero dismissed (every raised finding survived independent verification).**

### Action Items

**BLOCKER**
- [x] **[BLOCKER] Dead plumbing — `seconds_to_departure` never reaches fusion in production.** `vlan-pollers/_state_to_dict` emits `scheduled_departure` ONLY nested inside the `pis` object ([vlan-pollers/context_state.py:114-125](../../vlan-pollers/src/vlan_pollers/context_state.py)), but fusion's `ContextPushModel` reads a **flat top-level** `scheduled_departure` ([fusion/models.py:65](../../fusion/src/fusion/models.py)) that no producer sends. Confirmed empirically (TestClient POST of the real `_state_to_dict` body → fusion `/context` returns **422** on `extra='forbid'` for `pis`/`trip_number`/`alarms`/`occupancy`; even ignoring that, `model.scheduled_departure` is `None`). Net: `ctx.scheduled_departure` stays `None` forever → `_seconds_to_departure()` always `None` → `escalations.seconds_to_departure` always NULL → **delay-minutes-avoided KPI permanently 0**. The `models.py:63` comment ("vlan-pollers already POSTs this inside its push body; fusion stops dropping it") is factually wrong — the key is nested, not top-level. **Fix:** add a `pis` sub-model (or `dict`) to `ContextPushModel` and read `model.pis['scheduled_departure']` in `update_from_push`, matching the real wire shape; reconcile the `extra='forbid'` mismatch (the full delta push 422s today — pre-existing but now load-bearing). [fusion/models.py:62-65, fusion/context_state.py:107-108]

**HIGH**
- [x] **[HIGH] Plumbing tests are synthetic — they mask the blocker.** ✅ `test_context_push_carries_scheduled_departure` ([test_enrichment.py:269](../../fusion/tests/unit/test_enrichment.py)) builds `ContextPushModel(scheduled_departure=...)` directly instead of replaying `vlan_pollers._state_to_dict(state)`. No CI test bridges the real producer body to fusion's `/context`. **Fix:** add a cross-package contract test that POSTs the actual `_state_to_dict` body (populated `PisState`) to fusion's `/context` and asserts `202` + `ctx.scheduled_departure` populated + a stamped `seconds_to_departure`. This one test fails on both the dead-plumbing blocker and the `extra='forbid'` mismatch.
- [x] **[HIGH] (same root cause as blocker — the contract reviewer's independent confirmation)** `extra='forbid'` on `ContextPushModel` rejects the real vlan-pollers push body (`pis`/`trip_number`/`alarms`/`occupancy` undeclared). Pre-existing producer/consumer mismatch, but this story's feature is the first to depend on that boundary working. Resolve together with the blocker fix.

**MEDIUM**
- [x] **[MEDIUM] `scheduled_departure` not reset on journey change.** Present-replaces/absent-keeps semantics ([context_state.py:107-108](../../fusion/src/fusion/context_state.py)) + journey-gated `comfort.reset()` ([health.py:104-105](../../fusion/src/fusion/health.py)) that does NOT clear `scheduled_departure`. A journey-B alert before journey-B's first PIS push can inherit journey-A's still-future departure → wrong positive `seconds_to_departure` inflating the KPI on an invalid basis. **Fix:** clear `ctx.scheduled_departure = None` on the `journey_id`-change branch alongside `comfort.reset()`; add a unit test.
- [x] **[MEDIUM] AC2 missing the required feed-degraded structured log.** AC2 (story line 55) + T2 mandate a `log.info/warning` on the skip/degraded path (mirroring `pis_poll_failed`); `_seconds_to_departure` returns `None` silently and `enrichment.alert_emitted` doesn't even log `seconds_to_departure` → a degraded feed is invisible in logs. **Fix:** emit a structured log in the skip branch (distinguish in-transit DEBUG from unparseable-departure WARNING); add a test asserting it fires. [enrichment.py:33-58]

**LOW**
- [x] **[LOW] Speed-branch stamps `0` not `None` for a stopped train past its departure.** `pre_departure = station_approach or speed_kmh == 0.0` doesn't enforce a *future* departure on the speed branch (D1/AC2 require it) → a delayed stopped train gets `seconds_to_departure=0` instead of `None`. KPI impact nil today (a 0-row never counts in-time); Phase-2 Conductor-App would render "0s to departure". **Fix:** return `None` when standstill-not-station_approach and `(sched - now) <= 0`; add the test. [enrichment.py:52-58]
- [x] **[LOW] Stale `station_approach` in the post-await log.** `emit_alert` snapshots `station_approach` for the payload but the final `log.info` reads the **live** `self._ctx.station_approach` after the `await` ([enrichment.py:190](../../fusion/src/fusion/enrichment.py)) — logged value can disagree with the snapshot-derived `priority` for the same alert. Observability-only. **Fix:** `station_approach=station_approach` (use the snapshot).
- [x] **[LOW] In-time boundary marginally lenient.** `seconds_to_departure` uses a different `now` read than the envelope `t_fired`, plus floor truncation, so the reconstructed in-time boundary (`t_fired + seconds`) lands sub-second-to-low-second *after* true scheduled departure. **Fix:** use one `now` for both derivation and envelope timestamp, or persist the absolute departure instant and compare `t_resolve` directly. [enrichment.py:160-180, delay_minutes_avoided.py:32]
- [x] **[LOW] AC4 response-key prose mismatch.** AC4 text specifies `delay_minutes_avoided_24h`; code ships `delay_minutes_avoided` (+ separate `window_hours`). Internally consistent end-to-end (tests + CC hook agree) — no runtime break. **Fix (preferred):** update AC4 text to the shipped `{delay_minutes_avoided, window_hours}` shape. [api/kpi.py:16]
- [x] **[LOW] CC hook reuses one `AbortController` across interval refreshes.** A fetch slower than the 5-min interval can resolve after a newer one and overwrite it with a stale value (not a leak — unmount aborts). **Fix:** fresh `AbortController` per `load()`, or a request-sequence guard. [useDelayMinutesAvoided.js:13-35]

### Disposition

The blocker + both highs are **one connected failure**: the KPI's data supply is severed (nested-vs-flat `scheduled_departure`), and the synthetic test strategy hid it. The fix is contained but cross-package (fusion `ContextPushModel`/`update_from_push` + a real-producer contract test), and touches the pre-existing `extra='forbid'` vlan-pollers↔fusion mismatch — which raises a scope question (fix-in-place vs spin the contract reconciliation into its own story). **Awaiting user decision before applying fixes.**

### Round-1 Resolution (all 10 findings addressed, 2026-06-14)

**User chose "minimal in-scope fix".** During implementation I found a **strictly more minimal** mechanism than the option's suggested fusion-`pis`-sub-model: a **targeted PIS push** from vlan-pollers (mirroring the existing, reviewed `set_station_approach` pattern), which makes the already-shipped flat `scheduled_departure` field work with **zero** fusion-model change and **zero** blast radius on other features. Deviated to it and documented the rationale below.

- **[BLOCKER] dead plumbing → FIXED.** `update_pis` ([vlan-pollers/context_state.py](../../vlan-pollers/src/vlan_pollers/context_state.py)) now sends a targeted `{scheduled_departure, journey_id}` push to fusion (alongside the existing full-delta push to inference). fusion's flat `scheduled_departure` field receives it. RED test `test_update_pis_sends_targeted_scheduled_departure_to_fusion` (the failure output literally showed only the nested `pis` reaching fusion). vlan-pollers 89 pass, mypy+ruff clean.
- **[HIGH] synthetic tests → FIXED.** Added `test_real_targeted_pis_push_populates_scheduled_departure` ([fusion contract test](../../fusion/tests/contract/test_candidate_payload_contract.py)) — POSTs the real targeted-push JSON body through the actual `/context` endpoint and asserts `ctx.scheduled_departure` populated. Tightened the unit test to validate the raw wire dict via `model_validate` (not synthetic kwargs). The vlan-pollers producer test proves the body shape from the other side.
- **[HIGH] extra='forbid' → RESOLVED by design (not code).** The targeted push carries only declared keys (`scheduled_departure`, `journey_id`), so it validates cleanly; the feature no longer depends on the full-delta push working. The pre-existing full-delta→fusion 422 mismatch (`pis`/`trip_number`/`alarms`/`occupancy` undeclared) is **no longer load-bearing for 10-4** — flagged as a pre-existing follow-up (see Pre-existing observations), not fixed here per the user's minimal scope.
- **[MEDIUM] journey-change reset → FIXED.** `update_from_push` ([fusion/context_state.py](../../fusion/src/fusion/context_state.py)) clears `scheduled_departure` to `None` on a `journey_id` change unless the same push sets a new one. Test `test_scheduled_departure_cleared_on_journey_change`.
- **[MEDIUM] AC2 degraded log → FIXED.** `emit_alert` emits `enrichment.seconds_to_departure_unavailable` (WARNING, `recoverable=True`) when pre-departure but no derivable seconds; in-transit stays silent (expected). Tests assert it fires / doesn't fire (via `structlog.testing.capture_logs`).
- **[LOW] speed-branch future-gate → FIXED.** Speed-only branch returns `None` for a past departure (overdue ≠ pre-departure); station_approach branch still clamps to `0` (AC6b). Test `test_seconds_to_departure_standstill_past_departure_returns_none`.
- **[LOW] stale log → FIXED.** `enrichment.alert_emitted` now logs the `station_approach` snapshot, not the post-await live read.
- **[LOW] boundary skew → FIXED.** One `now` read drives both the `seconds_to_departure` delta and the envelope `timestamp` (threaded via `_build_envelope(timestamp=…)`), so the in-time boundary reconstructs from a single instant. (Sub-second floor truncation is inherent to integer seconds — accepted.)
- **[LOW] AC4 prose → FIXED.** AC4 text updated to the shipped `{delay_minutes_avoided, window_hours}` shape.
- **[LOW] CC AbortController → FIXED.** [useDelayMinutesAvoided.js](../../control-centre/src/hooks/useDelayMinutesAvoided.js) creates a fresh `AbortController` per `load()` and aborts the prior in-flight request; the resolve guard checks `signal.aborted`. Browser-re-verified (stubbed 8.4 → tile `8`, console clean).

**Pre-existing observations (NOT fixed in 10-4 — flagged for follow-up):**
- The vlan-pollers↔fusion **full-delta** `/context` push 422s entirely (fusion `extra='forbid'` rejects `pis`/`trip_number`/`alarms`/`occupancy`). Every `_push_context_delta`-driven update (speed/occupancy/reservations/journey/alarm) therefore fails to deliver to fusion in production today — a pre-existing integration hole affecting comfort-index/occupancy delivery, independent of 10-4. Worth a dedicated contract-reconciliation story.

**Post-fix gates (all green):** vlan-pollers 89 · shared 176 (unit+contract) · fusion **175** (cov 93.68%, mypy --strict) · cloud-backend KPI integration 8/8 (+ full 176 from dev round) · CC vitest 250. Browser re-verified. Status → review.

## Senior Developer Review (AI) — Round 2 (re-review of Round-1 fixes)

**Reviewer:** Multi-agent adversarial re-review workflow (wf_4b4c0912 — blocker-closure verifier + regression-hunter + fix-completeness auditor, each alleged problem independently refuted; 6 agents). **Date:** 2026-06-14. **Outcome: APPROVED.**

**The blocker is genuinely CLOSED — verified end-to-end on the REAL wire** (reviewers drove the actual `update_pis` → captured its real HTTP body `{scheduled_departure, journey_id}` flat → POSTed it to the real `/context` → 200 + `ctx.scheduled_departure` populated → emitted through the real `/candidates/alert_raised` → payload carried `seconds_to_departure=599`, single-`now` `t_fired` → ingest persists the column → KPI sums it). **17 fix-confirmations, all 10 Round-1 findings independently corroborated, zero regressions, zero new high/blocker.**

**Surviving findings (2, both LOW, both fixed in this commit):**
- [x] **[LOW] Stale comment `models.py:62-64`** described the pre-fix nested mechanism ("vlan-pollers already POSTs this inside its push body; fusion stops dropping it") — the exact text the blocker disproved. Rewritten to state the field arrives via the flat targeted push.
- [x] **[LOW] Sibling stale comment `context_state.py:41-43`** ("Already on the /context wire … `_state_to_dict["pis"]`") — same stale framing. Rewritten.

Both comment-only; no logic change; fusion mypy --strict + ruff clean after the edit.

**Non-blocking note (R7):** no dedicated vitest for the CC hook's abort-on-refresh race (only the API client is unit-tested). Nice-to-have, not required for this story.

### Change Log addendum

- 2026-06-14 — Round-2 re-review (wf_4b4c0912): **APPROVED**. Blocker verified closed end-to-end on the real wire (seconds_to_departure=599 stamped through the live producer→fusion→KPI chain). 2 surviving LOW findings = stale comments, fixed in place. Status review → done.
