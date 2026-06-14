---
baseline_commit: e42a912
---

# Story 10.5: Alert Quality Measurement (Resolution-Quality Rates)

Status: done

<!-- Created 2026-06-14 via bmad-create-story (Amelia / Opus 4.8). P3 — final feature story in Epic 10 (Operator Adoption & Trust).
     Source of truth: E10-S5 in epics.md:2342-2377 (committed). Sprint-status names this 10-5-alert-quality-measurement, backlog.
     CODE-LIGHT story: NO shared/ payload change, NO enum change, NO DB migration. The audit (below) collapsed the epic's
     central deliverable. Two user decisions (D1, D2) were taken before AC authoring — see Decisions. Do NOT implement the
     epic text literally; implement the shipped shapes the Decisions resolve to. -->

## Story

As an **AI PM measuring whether alerts are operationally useful**,
I want **the System Health AI-quality surface to show two orthogonal resolution-quality rates per alert class (no-action rate and explicit-false-positive rate, the latter keyed off the *already-shipped* `false_alarm` tag), the weekly effectiveness report to flag any class breaching NFR3, and NFR3 itself redefined against a measurable quantity**,
so that **procurement claims about model accuracy are grounded in operator-observable behaviour rather than an unfalsifiable single "FP rate", and post-pilot retune candidates are identifiable from data that already exists**.

## Context — why this story exists

Epic 10 closes the AI-PM gap between a demo and a procurement-ready product. 10-1 made alerts *trustworthy* (confidence), 10-6 *persistent* (escalation lifecycle), 10-2 *measurable as behaviour* (telemetry), 10-3 *operationally wrapped* (SOP), 10-4 *KPI-aligned* (dwell-time). This story makes the **false-positive claim falsifiable**.

The PRD already anticipates this story by name: NFR3 ([prd.md:159](../../_bmad-output/planning-artifacts/prd.md)) carries a `⚠ Redefinition pending (E10-S5)` marker, and FR42 ([prd.md:130](../../_bmad-output/planning-artifacts/prd.md)) says "redefinition pending via E10-S5". This story discharges both markers.

### What the epic assumes vs what shipped — READ THIS BEFORE THE ACs

The epic AC text was written in BMAD Phase 3, before 10-6 shipped the escalation lifecycle. **Five of its assumptions do not match the shipped system.** The team PAYLOAD/ENUM-AUDIT rule caught all five. Two were load-bearing and were resolved by user decision (D1, D2) before this story was written; three are mechanical. **Implement the shipped shapes, not the epic prose.**

| # | Epic text assumes… | Shipped reality | Resolved in |
|---|---|---|---|
| **D1** | Add a NEW `false_positive` outcome tag, *mutually exclusive* with action tags ("FP OR action tags, never both"). | 10-6 shipped a fixed **4-key taxonomy** in `ACTION_TAG_KEYS` ([escalations.py:16-21](../../cloud-backend/src/cloud_backend/api/escalations.py)): `resolved_remotely / field_team_dispatched / false_alarm / no_action_needed`. The code comment at [escalations.py:14-15](../../cloud-backend/src/cloud_backend/api/escalations.py) states **`false_alarm` + `no_action_needed` ARE the false-positive signal**. `action_tags` is `min_length=1` ([escalations.py:30](../../cloud-backend/src/cloud_backend/api/escalations.py)) — ≥1 tag is mandatory; there is no exclusivity mechanism, and a new tag would *duplicate* `false_alarm`. **Decision: reuse the shipped `false_alarm` tag. No enum change, no new tag, no exclusivity rule, no migration.** | D1 |
| **D2** | Show THREE rates, incl. `auto_resolved_before_ack_rate = auto_resolved_before_ack / raised_total`. | **No `auto_resolved_before_ack` mechanism exists anywhere.** Resolve *requires* a prior ack (409 at [escalations.py:119-122](../../cloud-backend/src/cloud_backend/routes/escalations.py)); nothing auto-resolves. The rate would be structurally `0/undefined` forever. **Decision: drop it. Ship TWO rates** (`no_action_rate`, `explicit_fp_rate`); document the third as structurally-zero / out-of-scope. | D2 |
| **D3** | Surface lives in the "AI Quality **drawer**". | The 10-1 drawer is `AIPipelineDrawer.jsx`, explicitly **per-train**: comment at [AIPipelineDrawer.jsx:14](../../control-centre/src/components/health/AIPipelineDrawer.jsx) — *"no per-class breakdown."* A per-alert-class table is a NEW sibling surface in System Health, not an edit to that drawer. | D3 |
| **D4** | `explicit_fp_rate` keyed on `resolved_with_tag("false_positive")`. | Per D1, key on `false_alarm`. The data is **already populated** — `action_tags` JSONB on both `escalations` ([0006:47](../../cloud-backend/migrations/versions/0006_escalations.py)) and `escalation_audit` ([0007:48](../../cloud-backend/migrations/versions/0007_escalation_audit.py)) — and the report already unnests it ([escalations_audit.py:112-125](../../cloud-backend/src/cloud_backend/routes/escalations_audit.py)). Computable now, no schema add. | D1/D4 |
| **D5** | Update NFR3 in PRD + add a weekly-report breach flag. | Both editable: [prd.md:159](../../_bmad-output/planning-artifacts/prd.md) (the `⚠` row awaiting this story), [alert_effectiveness_report.py](../../cloud-backend/src/cloud_backend/services/alert_effectiveness_report.py). No divergence. | D5 |

**Net effect of D1+D2:** the story is **code-light and almost entirely additive** — one new read-only endpoint + service (two rates from existing columns), one new per-alert-class CC component, the weekly-report NFR3 breach flag, the PRD NFR3 rewrite, and one resolve-UI hint string. **No `shared/` change. No Alembic migration. No enum/contract change.**

## Decisions

### D1 — Reuse shipped `false_alarm`; do NOT add a `false_positive` tag *(user-confirmed 2026-06-14)*
The epic's headline deliverable (a new mutually-exclusive `false_positive` tag) collides with the shipped contract. 10-6's `ACTION_TAG_KEYS` already encodes `false_alarm` as the "model was wrong" signal, and `action_tags` is mandatory `min_length=1`. Adding `false_positive` would duplicate `false_alarm`, require a new exclusivity rule contradicting `min_length=1`, and re-open a settled taxonomy. **Resolution:** `explicit_fp_rate` is defined over the shipped `false_alarm` key. The taxonomy is untouched. The only UI change is the resolve-flow hint (AC5) clarifying when to pick `False alarm`.

### D2 — Ship two rates; auto-resolved-before-ack is out of scope *(user-confirmed 2026-06-14)*
No code path auto-resolves an escalation before acknowledgement (resolve hard-requires ack — 409 otherwise). The epic's third rate would always be zero. **Resolution:** ship `no_action_rate` and `explicit_fp_rate`. The endpoint and component carry exactly two rates. A one-line note in the endpoint docstring records *why* the third epic rate is absent (no auto-resolve mechanism in the shipped lifecycle), so a future reviewer doesn't read it as an omission.

### D3 — New `AIQualityRates` component, sibling to `AIPipelineRow` in System Health
The shipped `AIPipelineDrawer` is per-train and explicitly carries no per-class breakdown. Rather than overload it, add a new per-alert-class component to the System Health surface alongside `AIPipelineRow` ([SystemHealth.jsx:230](../../control-centre/src/components/health/SystemHealth.jsx)). Naming follows the epic deliverable: `control-centre/src/components/health/AIQualityRates.jsx` + `.css`.

### D4 — No migration; rates computed from existing `escalation_audit` columns
`escalation_audit` already has `transition`, `alert_code`, `action_tags` (JSONB), `t_event` — everything both rates need. The endpoint reuses the half-open window + `jsonb_array_elements_text` unnest pattern already proven in [escalations_audit.py:67-125](../../cloud-backend/src/cloud_backend/routes/escalations_audit.py). Rolling **7-day** window (epic: "calibration requires a longer window" — not the 1-hour live tile).

## Acceptance Criteria

> **Scope note:** the epic's `false_positive`-tag AC and `auto_resolved_before_ack_rate` are removed by D1/D2. This story ships: the two-rate endpoint (AC1), its per-class data definition (AC1), the System Health component (AC2, AC3), the NFR3 PRD redefinition (AC4), the resolve-UI hint (AC5), the weekly-report breach flag (AC6), and unit/component tests (AC7). **No `shared/` edit, no migration, no enum change.**

**AC1 — New read-only endpoint `GET /api/v1/ai-quality/resolution-rates` returns two rates per alert class**
Given the shipped `escalation_audit` rows ([0007_escalation_audit.py](../../cloud-backend/migrations/versions/0007_escalation_audit.py)),
when the endpoint is called (optional `from`/`to` ISO params; **default window = trailing 7 days**, computed in SQL via `COALESCE(:from, NOW() - INTERVAL '7 days')` to stay clock-skew-proof — copy the window idiom from [escalations_audit.py:67-73](../../cloud-backend/src/cloud_backend/routes/escalations_audit.py)),
then it returns a list of per-`alert_code` objects, each carrying both rates **with their integer count denominators** (so small-sample noise is visible — epic requirement):
- `no_action_rate` = `resolved_with_zero_action_tags / resolved_total`, where "zero action tags" means the resolved row's `action_tags` array is empty/NULL. **Edge:** since 10-6 enforces `min_length=1` on resolve, a strictly-empty array should be rare; the rate is still defined (it will typically be `0`). Carry `resolved_total` as the denominator.
- `explicit_fp_rate` = `resolved_with_tag("false_alarm") / resolved_total` (D1/D4 — keyed on the shipped `false_alarm` canonical key, **not** `false_positive`).
- Each object shape: `{ alert_code, resolved_total, no_action_count, no_action_rate, false_alarm_count, explicit_fp_rate }`. Rates are `float | None` — **`None` when `resolved_total == 0`** (divide-by-zero guard — the NULL/zero-denominator trap, mirrors [alert_effectiveness_report.py:101](../../cloud-backend/src/cloud_backend/services/alert_effectiveness_report.py) and [analytics.py:53](../../cloud-backend/src/cloud_backend/api/analytics.py)).
The endpoint is **auth-guarded** with `Security(require_api_key)` and registered via `include_router` in [main.py:37-44](../../cloud-backend/src/cloud_backend/main.py), exactly like [kpi.py:17](../../cloud-backend/src/cloud_backend/routes/kpi.py). Route handler in `routes/`, business logic in `services/`, Pydantic response model in `api/` (cloud-backend/CLAUDE.md layering — handlers contain no business logic). The endpoint is **read-only** — no migration, no write.

**AC2 — `AIQualityRates` component renders the two rates per class in System Health**
Given the System Health surface ([SystemHealth.jsx](../../control-centre/src/components/health/SystemHealth.jsx)),
when the component mounts,
then a new `control-centre/src/components/health/AIQualityRates.jsx` (+ `.css`) fetches the AC1 endpoint and renders a per-alert-class table showing both rates each formatted as **`<pct>% (<count> of <denominator>)`** (e.g. `4.2% (3 of 71)`) — the count must be visible per the epic. The component:
- handles **all three states** (loading / error / populated) per control-centre/CLAUDE.md — render `—` for a rate whose value is `None` or while loading, never a bare `NaN%` or `0%` masquerading as data;
- uses **only `--obb-*` design tokens** (see Dev Notes for the token list) — no hex literals, no invented token names;
- is rendered as a **sibling of `AIPipelineRow`** within System Health (D3), not inside `AIPipelineDrawer` (which is per-train).

**AC3 — Two rates shown side-by-side, never an aggregated single number**
Given the epic's anti-pattern warning ("No aggregated single 'FP rate' number; all shown side-by-side"),
then the component shows `no_action_rate` and `explicit_fp_rate` as **two distinct columns per class**. It must NOT compute or display any blended/averaged single quality score.

**AC4 — NFR3 redefined in the PRD**
Given NFR3 ([prd.md:159](../../_bmad-output/planning-artifacts/prd.md)) currently reads `<5% false-positive rate` with a `⚠ Redefinition pending (E10-S5)` marker,
when the PRD is updated,
then NFR3 is rewritten to: **`explicit_fp_rate < 5% per alert class over a rolling 7-day window`**, the `⚠ pending` marker is removed, `no_action_rate` is named as a *target* (not a gate), and the row cross-references FR42. The FR42 row ([prd.md:130](../../_bmad-output/planning-artifacts/prd.md)) `(redefinition pending via E10-S5)` parenthetical is updated to reflect that E10-S5 has landed. Bump the PRD changelog (§ near [prd.md:6](../../_bmad-output/planning-artifacts/prd.md)) with a `1.4` entry noting the NFR3 redefinition.

**AC5 — Resolve-flow hint clarifies the `False alarm` tag**
Given the resolve picker in [EscalationDetail.jsx:11-16](../../control-centre/src/components/live/EscalationDetail.jsx) (`ACTION_TAGS`),
when the operator opens the resolve flow,
then a small static explanatory line is shown near the tag picker: **"Mark *False alarm* if the model was wrong (no bag, no obstruction, no fall). Mark an action tag if the model was right and you took action."** This is **copy-only** — do NOT change the `ACTION_TAGS` list, the backend `ACTION_TAG_KEYS`, or any validation (D1). Exact placement is Freya's call; a single helper `<p>` above the tag list using existing detail-panel typography tokens is acceptable for the PoC.

**AC6 — Weekly report flags NFR3 breaches**
Given the weekly effectiveness report ([alert_effectiveness_report.py](../../cloud-backend/src/cloud_backend/services/alert_effectiveness_report.py)),
when a report is generated,
then a new section flags any `alert_code` whose `explicit_fp_rate ≥ 5%` over the reported ISO week (the report's existing `[dt_from, dt_to)` window — reuse `_funnel_rows`' window, do NOT add a second window definition). The `false_alarm` count per class is derivable from the same `action_tags` unnest the funnel route already uses; add a minimal query or extend `_funnel_rows` to carry `false_alarm` + `resolved` counts. A class with `resolved_total == 0` is **not** flagged (no divide-by-zero, mirrors the existing `ack_rate is None` guard at [alert_effectiveness_report.py:99-101](../../cloud-backend/src/cloud_backend/services/alert_effectiveness_report.py)). Render `—` / "no resolutions this window" when empty.

**AC7 — Tests cover both rates, the null path, and the breach flag**
Given the rate computation,
then:
- **cloud-backend unit/integration** (testcontainers Postgres, no mocks — cloud-backend/CLAUDE.md): (a) class with known mix of `false_alarm` / zero-tag / action-tag resolves → correct `no_action_rate` + `explicit_fp_rate` with correct denominators; (b) `resolved_total == 0` → both rates `None` (not `0`, not 500); (c) window boundary — a row on the half-open `to` edge counted by exactly one window; (d) auth — missing `X-API-Key` → 401/403, never 500.
- **report:** a class with `explicit_fp_rate ≥ 5%` is flagged; a class with `< 5%` is not; a class with zero resolves is not flagged and does not divide-by-zero.
- **control-centre vitest:** the `AIQualityRates` component renders populated, loading, error, and `None`-rate (`—`) states; asserts the `% (n of d)` format and that no aggregated single score is rendered (AC3).
- Browser verification (required, control-centre/CLAUDE.md): the component renders in System Health on the golden path **and** at least one edge state (empty/error); console clean during the check.

## Tasks / Subtasks

- [x] **T1 — cloud-backend endpoint + service (AC1)** — Tier 2
  - [x] `api/ai_quality.py`: `AlertQualityRates` Pydantic response model (`rate: float | None`, integer counts).
  - [x] `services/ai_quality_rates.py`: SQL over `escalation_audit` (transition='resolved', 7-day COALESCE window, `?`-operator for `false_alarm` count + `jsonb_array_length=0` zero-tag count + `resolved_total`); compute both rates with `None` on zero denominator. Docstring records why the epic's 3rd rate (auto-resolved-before-ack) is absent (D2).
  - [x] `routes/ai_quality.py`: `APIRouter(prefix="/api/v1/ai-quality", dependencies=[Security(require_api_key)])`, `GET /resolution-rates`; registered in `main.py` via `include_router`.
  - [x] mypy `--strict` + ruff clean on touched files.
- [x] **T2 — System Health component (AC2, AC3)** — Tier 2
  - [x] `components/health/AIQualityRates.jsx` + `.css`: fetch endpoint, per-class table, two columns, `% (n of d)` format, three-state handling, `--obb-*` tokens only.
  - [x] Mount as sibling of `AIPipelineRow` in `SystemHealth.jsx` (D3) — render even when the train-grid fetch fails, matching the `AIPipelineRow` precedent.
- [x] **T3 — Resolve-flow hint (AC5)** — Tier 2
  - [x] Copy-only `<p>` helper above the `ACTION_TAGS` picker in `EscalationDetail.jsx`. `ACTION_TAGS` and backend taxonomy untouched. New `resolve-form__hint` CSS class (`--obb-*` tokens).
- [x] **T4 — Weekly-report NFR3 breach flag (AC6)** — Tier 2
  - [x] Extended `_funnel_rows` to carry per-class `false_alarm` count + `explicit_fp_rate`; added `_nfr3_breaches` pure helper + "NFR3 breaches (≥5%)" render section; zero-resolve guard (None → not flagged).
- [x] **T5 — PRD NFR3 redefinition (AC4)** — Tier 2 (docs)
  - [x] Rewrote NFR3 row (explicit_fp_rate <5% per class, 7-day window), dropped `⚠ pending`, updated FR42, added changelog `1.4` + version bump.
- [x] **T6 — Tests + browser verify (AC7)** — Tier 2/3 (testcontainers needs Docker)
  - [x] cloud-backend: integration suite written (mix, null, raised-excluded, half-open boundary, auth) — runs on CI (no local Docker); unit auth (2) + report NFR3 (4) pass locally. CC vitest (7: loading/populated/breach/null-dash/empty/error + format + no-aggregate) pass. Browser verify blocked by pre-existing mock-config SPA-mount failure (FleetContext needs real backend) — documented in Completion Notes; Vite compiled all new files with zero build errors.

## Dev Notes

### CRITICAL — do not implement the epic literally
The epic's `false_positive` tag and `auto_resolved_before_ack_rate` are **removed** by D1/D2 (user-confirmed). Implement: reuse `false_alarm`, ship two rates. No `shared/` change, no migration, no enum change. If you find yourself editing `ACTION_TAG_KEYS`, `payloads.py`, or writing an Alembic migration, **stop** — you've drifted from the Decisions.

### Files this story touches (all NEW or additive; none are destructive UPDATEs to behavior)
| File | Kind | What |
|---|---|---|
| `cloud-backend/src/cloud_backend/api/ai_quality.py` | NEW | response models |
| `cloud-backend/src/cloud_backend/services/ai_quality_rates.py` | NEW | rate SQL + compute |
| `cloud-backend/src/cloud_backend/routes/ai_quality.py` | NEW | endpoint |
| `cloud-backend/src/cloud_backend/main.py` | UPDATE (1 line) | `include_router` |
| `cloud-backend/src/cloud_backend/services/alert_effectiveness_report.py` | UPDATE | breach-flag section + false_alarm count |
| `control-centre/src/components/health/AIQualityRates.jsx` + `.css` | NEW | per-class rates surface |
| `control-centre/src/components/health/SystemHealth.jsx` | UPDATE (mount) | render sibling of AIPipelineRow |
| `control-centre/src/components/live/EscalationDetail.jsx` | UPDATE (copy) | AC5 hint line only |
| `_bmad-output/planning-artifacts/prd.md` | UPDATE | NFR3 + FR42 + changelog |

### Reuse — do NOT reinvent these (they exist and are proven)
- **Window idiom** (skew-proof half-open, default-in-SQL): [escalations_audit.py:67-73](../../cloud-backend/src/cloud_backend/routes/escalations_audit.py). Copy it.
- **`action_tags` JSONB unnest** (`LATERAL jsonb_array_elements_text` + `jsonb_typeof = 'array'` guard): [escalations_audit.py:112-125](../../cloud-backend/src/cloud_backend/routes/escalations_audit.py). Copy it.
- **Auth-guarded read-only KPI route** (prefix + `Security(require_api_key)` + service split): [kpi.py:17-30](../../cloud-backend/src/cloud_backend/routes/kpi.py). Mirror it exactly.
- **Divide-by-zero / `None`-rate guard:** [alert_effectiveness_report.py:99-101](../../cloud-backend/src/cloud_backend/services/alert_effectiveness_report.py), [analytics.py:53](../../cloud-backend/src/cloud_backend/api/analytics.py). Same pattern: `None` when denominator 0, never `0.0` masquerading as a real rate.
- **Three-state CC fetch component:** any `components/health/` component; `AIPipelineRow.jsx` is the nearest sibling.

### Shipped action-tag taxonomy (the contract — DO NOT CHANGE)
Canonical keys (from [escalations.py:16-21](../../cloud-backend/src/cloud_backend/api/escalations.py)): `resolved_remotely`, `field_team_dispatched`, `false_alarm`, `no_action_needed`. UI labels in [EscalationDetail.jsx:11-16](../../control-centre/src/components/live/EscalationDetail.jsx) map to these via the backend dict. **`false_alarm` is the false-positive signal** (per the shipped code comment) — this story computes `explicit_fp_rate` off it. `action_tags` is mandatory `min_length=1`; "no action" is represented by the `no_action_needed` tag, so a *strictly empty* `action_tags` array is an edge that `no_action_rate` tolerates (typically 0) but must not crash on.

### CSS design tokens (control-centre) — `--obb-*` ONLY, no hex, no invented names
All component CSS must use the tokens in `control-centre/src/styles/colors_and_type.css`. **Common mistakes that have caused review cycles:** `--obb-sev-warning` does NOT exist → use `--obb-sev-medium`; `--obb-sev-danger` does NOT exist → use `--obb-sev-critical`.
- Severity ramp: `--obb-sev-critical` (red), `--obb-sev-high` (orange), `--obb-sev-medium` (amber), `--obb-sev-advisory` (blue), `--obb-sev-normal` (green).
- Surfaces: `--obb-surface-0..5`; text on dark: `--obb-text-on-dark-1..4`; borders: `--obb-border-dark` / `--obb-border-bright`; brand: `--obb-blue-accent` / `--obb-blue-dim`.
- Typography: `--font-mono` (IDs/timestamps/counts), `--font-size-sm`.
For a quality-rates table, a breaching `explicit_fp_rate ≥ 5%` may be tinted `--obb-sev-medium`; healthy `--obb-sev-normal`. Do not invent a `--obb-sev-warning`.

### Untrusted-input boundary
`escalation_audit.action_tags` originates from operator input bucketed server-side into the canonical taxonomy, so it is trusted at read time. The new endpoint is read-only and parameterised (no string interpolation of user values into SQL) — keep the `from`/`to` params bound, never f-string-interpolated (the existing route binds them; the `code_clause` is the only conditional fragment and it too binds its value). Per cloud-backend/CLAUDE.md error shape: all 4xx use `{"detail": "..."}` / the existing `{"error": ..., "detail": ..., "recoverable": ...}` 422 shape — never raw exception text.

### Permission tier
**Tier 2** throughout (local file edits, git-reviewable). **No Tier-3 schema change** — the D1/D2 decisions removed the enum extension and migration the epic implied. T6 integration tests need Docker (testcontainers); that's a local dev dependency, not a Tier-3 shared-infra action.

### ADR freshness
No ADR is contradicted. The shipped taxonomy is unchanged (D1), no new EventType, no payload-shape change, no migration. ADR ceiling is 22; this story adds none. (Per team ADR-FRESHNESS rule: searched architecture.md — no ADR describes the action-tag taxonomy or AI-quality rates in a way this story changes.)

### Previous-story intelligence (10-4, done 2026-06-14)
10-4 was the immediately-preceding story (same epic, same author). Carry-forward learnings:
- The **payload audit caught real epic↔shipped drift** in 10-4 (4 divergences) and again here (5). The audit is load-bearing — the green-test trap from the 10-4 review (synthetic unit tests masking a dead prod path) is why AC7 mandates **testcontainers integration**, not just mocked unit tests, for the SQL rates.
- 10-4's KPI endpoint (`kpi.py` / `delay_minutes_avoided.py`) is the **exact structural template** for this endpoint: auth-guarded prefix router, `services/` compute split, `api/` response model, `window_hours`-style explicit window. Reuse the shape.
- 10-4's CC tile rendered `—` on unavailable per the three-state rule; do the same per-rate here.

### Project Structure Notes
- New backend files land in the established trio (`routes/` handler, `services/` logic, `api/` model) — no new directories.
- New CC component lives in `components/health/` beside its peers; matching `.css`; no TypeScript (control-centre/CLAUDE.md).
- No `shared/` edit means no contract test in `shared/` and no event-store round-trip concern (contrast 10-4, which did add a `shared/` field).

### References
- [Source: epics.md:2342-2377 — E10-S5 acceptance criteria + deliverables]
- [Source: owning-the-gap-ai-pm-analysis.md §3 (gap 3) — alert-quality intent]
- [Source: cloud-backend/src/cloud_backend/api/escalations.py:14-21 — shipped ACTION_TAG_KEYS taxonomy (D1)]
- [Source: cloud-backend/src/cloud_backend/routes/escalations.py:119-130 — resolve requires prior ack (D2 basis)]
- [Source: cloud-backend/src/cloud_backend/routes/escalations_audit.py:67-125 — window + JSONB-unnest idioms to reuse]
- [Source: cloud-backend/src/cloud_backend/routes/kpi.py:17-30 — auth-guarded read-only KPI route template]
- [Source: cloud-backend/src/cloud_backend/services/alert_effectiveness_report.py — weekly report; breach-flag target (AC6)]
- [Source: control-centre/src/components/health/SystemHealth.jsx:228-230 — AIPipelineRow mount precedent (D3)]
- [Source: control-centre/src/components/health/AIPipelineDrawer.jsx:14 — "no per-class breakdown" (D3 rationale)]
- [Source: control-centre/src/components/live/EscalationDetail.jsx:11-16 — ACTION_TAGS picker (AC5)]
- [Source: prd.md:130,159 — FR42 + NFR3 redefinition-pending markers this story discharges (AC4)]
- [Source: project-context.md — CSS token reference; async/SQL patterns]

## Dev Agent Record

### Agent Model Used

Amelia (claude-opus-4-8[1m])

### Debug Log References

- cloud-backend: `pytest -m unit` → 98 passed / 92 deselected (integration needs Docker); `mypy src/` --strict → 0 issues (37 files); `ruff check src/ + new tests` → clean.
- control-centre: `vitest run` → 257 passed (21 files), incl. 7 new `AIQualityRates` tests; new files lint-clean (pre-existing SystemHealth/EscalationDetail purity errors untouched).

### Completion Notes List

- **D1 implemented (reuse `false_alarm`):** `explicit_fp_rate` keys on the shipped `false_alarm` canonical tag — no new `false_positive` tag, no enum/contract change, no migration. `ACTION_TAG_KEYS` and the CC `ACTION_TAGS` picker are untouched.
- **D2 implemented (two rates):** endpoint + report ship `no_action_rate` + `explicit_fp_rate` only. The epic's `auto_resolved_before_ack_rate` is documented-as-absent (no auto-resolve path in the shipped lifecycle) in the service docstring and the PRD NFR3 note.
- **AC1 endpoint:** `GET /api/v1/ai-quality/resolution-rates` — new `routes/ai_quality.py` + `services/ai_quality_rates.py` + `api/ai_quality.py`, registered in `main.py`. 7-day skew-proof window + `jsonb` `?`-operator for `false_alarm`, `jsonb_array_length=0`/NULL for no-action; rates `None` on zero denominator. Auth via `Security(require_api_key)`.
- **AC2/AC3 component:** `AIQualityRates.jsx` (+ `.css`, `--obb-*` only) renders two side-by-side per-class columns as `% (n of d)`; three-state handling; breach tint `--obb-sev-medium` at ≥5%. Mounted as sibling of `AIPipelineRow` in both the main and error branches of `SystemHealth.jsx`.
- **AC5 hint:** static copy `<p>` above the resolve tag picker; no logic/taxonomy change.
- **AC6 report:** `_funnel_rows` extended with `false_alarm` + `explicit_fp_rate`; `_nfr3_breaches` pure helper + new "NFR3 breaches (≥5%)" section; zero-resolve classes excluded (no divide-by-zero).
- **AC4 PRD:** NFR3 redefined (explicit_fp_rate <5% per class, rolling 7-day; no_action_rate a target); `⚠ pending` removed; FR42 updated; changelog `1.4` + version → 1.4.
- **Integration tests (AC7):** written against testcontainers Postgres; not run locally (no Docker — same constraint as 10-1/10-4), will run on first CI. Logic verified by structure against the proven 10-2 funnel idiom and 10-4 KPI test.
- **Browser verification (AC7):** blocked — the `control-centre-mock` launch config does not fully wire `VITE_MOCK_API`, so `FleetContext` fails its alerts fetch and the SPA shell does not mount at any route (root `#root` empty; reproduced on baseline, not caused by this story). Vite compiled all new files with **zero build errors**. The component's five render states (loading/populated/breach/null-dash/empty/error) are fully covered by the 7 passing RTL tests against real React+jsdom. Recommend the reviewer confirm in-browser once a backend-connected dev environment is available (pre-pilot).
- **Surgical-change note:** pre-existing eslint React-purity errors in `SystemHealth.jsx` (6) and `EscalationDetail.jsx` (2) exist on baseline `e42a912` and were left untouched per the surgical-change rule. Candidate for Epic 8.

### File List

**New (cloud-backend):**
- `cloud-backend/src/cloud_backend/api/ai_quality.py`
- `cloud-backend/src/cloud_backend/services/ai_quality_rates.py`
- `cloud-backend/src/cloud_backend/routes/ai_quality.py`
- `cloud-backend/tests/integration/test_ai_quality_rates.py`
- `cloud-backend/tests/unit/test_ai_quality_rates_security.py`
- `cloud-backend/tests/unit/test_alert_effectiveness_nfr3.py`

**New (control-centre):**
- `control-centre/src/api/aiQuality.js`
- `control-centre/src/components/health/AIQualityRates.jsx`
- `control-centre/src/components/health/AIQualityRates.css`
- `control-centre/src/components/health/__tests__/AIQualityRates.test.jsx`

**Modified:**
- `cloud-backend/src/cloud_backend/main.py` (include_router)
- `cloud-backend/src/cloud_backend/services/alert_effectiveness_report.py` (NFR3 breach flag)
- `control-centre/src/components/health/SystemHealth.jsx` (mount AIQualityRates)
- `control-centre/src/components/live/EscalationDetail.jsx` (AC5 hint)
- `control-centre/src/components/live/EscalationDetail.css` (resolve-form__hint)
- `_bmad-output/planning-artifacts/prd.md` (NFR3 redefinition, FR42, changelog 1.4)

## Change Log

| Date | Change |
|---|---|
| 2026-06-14 | Implemented 10-5 (T1–T6): AI-quality resolution-rates endpoint + CC component + report NFR3 breach flag + PRD NFR3 redefinition + resolve hint. Reused shipped `false_alarm` (D1); shipped two rates (D2). Status → review. |
| 2026-06-14 | Code-review Round 1 (multi-agent adversarial, wf_4b011970): 1 BLOCKER + 1 high + 1 medium + 2 low fixed; 1 medium accepted-as-deferral; 1 low deferred; 6 refuted. |
| 2026-06-14 | Code-review Round 2 (wf_0c944bdb): all 3 R1 fixes re-verified correct; 1 new low (fixture truncated only escalation_audit, leaked escalations parents) → FIXED (TRUNCATE both). APPROVED. Status → done. |

## Senior Developer Review (AI) — Round 2

**Reviewer:** Amelia (re-verification workflow `wf_0c944bdb`, 2 parallel verifiers — FK-fix correctness + HIGH/LOW regression scan). **Delta:** `ff96e4a` → `9e280a3`.
**Outcome:** APPROVED.

All three R1 fixes verified correct against the real code and schema:
- **FK seed fix (BLOCKER):** `_seed_parent()` inserts a valid `escalations` parent (every NOT-NULL col satisfied, status defaults) before every audit insert, matching `eid`; no residual constraint risk; the 4 data tests now genuinely exercise the `?`-operator + `jsonb_array_length` branches.
- **Untracked test (HIGH):** committed as a new file; 8 tests cover all AC7 cases.
- **2-decimal label (LOW):** keeps the `% (n of d)` contract; no other test expected one decimal; `_render` tests assert the exact emitted markdown.

**1 new finding (LOW) — FIXED in R2:** the `factory` fixture truncated only `escalation_audit`, so the newly-seeded `escalations` parents leaked across the module's tests (no constraint violation — a hygiene issue). Fixed: `TRUNCATE escalations, escalation_audit RESTART IDENTITY CASCADE`.

### Residual
- ~~Integration suite needs Docker~~ — **DISCHARGED 2026-06-14.** Docker came up; ran `pytest -m integration` on real Postgres (testcontainers + Alembic head): all **6 of 6** 10-5 integration tests PASS (`test_two_rates_with_denominators` 0.25/0.25, `test_null_action_tags_counts_as_no_action`, `test_raised_rows_do_not_count_as_resolved`, `test_window_upper_bound_is_half_open`, `test_empty_window_returns_empty_list`, `test_requires_api_key`). This empirically proves the BLOCKER fix (FK `_seed_parent`) and the novel `?`-operator + `jsonb_array_length` SQL on real Postgres. Full cloud-backend integration suite: **92 passed, 0 failed** — no regressions.
- ~~Browser verification (AC7) blocked~~ — **DISCHARGED 2026-06-14, and the "block" was a misdiagnosis.** The earlier "SPA does not mount" claim was wrong: it came from a `pushState`+reload that raced React's mount, mis-read as a failure. Re-checked properly — the app mounts fine in `control-centre-mock` (`#root` = 27k chars, routes resolve). Note: there is **no `VITE_MOCK_API` flag** in the source at all (the launch config sets one nothing reads); the real mock seam is `VITE_WS_URL`-unset → `MockWebSocketClient`. The two `fetchTrainAlerts` console errors are pre-existing (mock server doesn't serve that REST route), are caught into state, and do **not** crash the shell.
  Verified live at `/dashboard/health` (rates endpoint stubbed, since the mock server doesn't serve it): the `AIQualityRates` table renders the header "Alert quality — resolution rates (7d)", two side-by-side columns (AC3), `% (n of d)` at two decimals (`7.04% (5 of 71)`, `4.23% (3 of 71)`, `20.00% (2 of 10)`), exactly **one breach cell** tinted (`slip_fall` 20% ≥ gate; `door_obstruction` 4.23% not) computing to `rgb(245,166,35)` = `--obb-sev-medium`. Table font-size resolves to 14px (the deferred `--font-size-sm` token does NOT manifest as oversized text). Console clean of any `AIQualityRates` error. Golden path browser-verified; the five edge states (loading/empty/error/null-dash/breach) remain covered by the 8 RTL tests.

## Senior Developer Review (AI) — Round 1

**Reviewer:** Amelia (multi-agent adversarial workflow `wf_4b011970`, 14 agents — Blind / Edge-Case / Acceptance-Auditor / SQL-Semantics find layers → per-finding refutation with diverse lenses → completeness critic). **Baseline:** `e42a912` → impl `ff96e4a`.
**Outcome:** CHANGES_REQUESTED → fixed → re-verify.

9 raw findings + 4 critic findings → 3 confirmed + 4 critic-confirmed, 6 refuted. The **completeness critic caught the headline defect all four find-layers missed** (the FK-broken integration seed) — classic green-test trap.

### Action Items

- [x] **[BLOCKER] Integration tests violate the `escalation_audit → escalations` FK** (`tests/integration/test_ai_quality_rates.py`). `_seed_resolved` and the raw `raised`-row insert wrote `escalation_audit` rows with orphan `escalation_id`s and never created the parent `escalations` row. `escalation_audit.escalation_id` is `NOT NULL` with a non-deferrable FK (`0007:37-42` → `0006:29`), so all 4 data-bearing tests would `ForeignKeyViolationError` on first CI run — leaving the novel `?`-operator SQL with **zero** passing coverage. **Fix:** added `_seed_parent()` that inserts the matching `escalations` row (NOT-NULL cols + default status) keyed by the same `eid`, called before every audit insert.
- [x] **[HIGH] `AIQualityRates.test.jsx` was never committed** — the sole AC7 control-centre test deliverable was untracked (`?? `), absent from `ff96e4a` and CI, despite Completion Notes claiming "7 passing tests". **Fix:** staged + committed in the R1 fix commit (now 8 tests incl. the boundary case below).
- [x] **[MEDIUM] Novel JSONB `?` operator unverified** (diverged from the LATERAL-unnest idiom the story said to copy). Verified correct against Postgres source via Context7: `jsonb ? text` tests membership of a string as a **top-level key OR array element** (exactly the use here), and `jsonb_array_length` is `proisstrict=true` so it returns NULL (never errors) on a NULL row — the `no_action` NULL branch is safe on all paths. **Resolution:** keep `?` (correct + idiomatic; unnest would multiply rows under GROUP BY); the BLOCKER fix makes the integration test actually exercise it on CI.
- [x] **[LOW] Rounded label disagreed with the breach tint at the 5% gate** (`AIQualityRates.jsx`). One-decimal `4.96%` and `5.04%` both rendered `5.0%` with only one tinted. **Fix:** label now two decimals (`PCT` → `toFixed(2)`); raw-float gate unchanged so tile and report stay consistent; added an RTL boundary test asserting `4.96%`/`5.04%` render distinctly with exactly one tinted. (Report half of the finding was refuted — `_fmt_pct` only renders already-breaching classes, no contradictory pair.)
- [x] **[LOW] `_render` NFR3 section had no rendered-output test** (only the pure `_nfr3_breaches` filter was covered). **Fix:** added two `_render` unit tests (breach listed + counts; empty-state line) — no DB needed.
- [x] **[MEDIUM] Browser verification** (AC7 / control-centre CLAUDE.md "not optional"). **DISCHARGED 2026-06-14** — and the original "blocked" framing was a misdiagnosis (the SPA mounts fine; the earlier empty-`#root` came from a pushState+reload racing the mount). Verified the `AIQualityRates` golden path live at `/dashboard/health`: correct header, two columns, 2-decimal `% (n of d)`, one breach cell tinted to `--obb-sev-medium`, 14px text, clean console. See the Round-2 "Residual" section for the full evidence. Edge states remain RTL-covered.
- [ ] **[LOW — deferred] `--font-size-sm` is an undefined token** (the real token is `--fs-small`). Pre-existing drift across 5 files / 11 occurrences (AIPipelineRow, ConfidenceChip, DegradedBanner, EscalationDetail); the new CSS correctly matched the established (broken) precedent per the surgical-change rule. **Deferred** to a token-cleanup story (fix once via an alias `--font-size-sm: var(--fs-small)` so all 5 files retro-fix together) — fixing only the 10-5 files would diverge them from their siblings.

### Refuted (6 — verified false positives / out-of-scope)
- Asymmetric default window when only `to` given — intended, spec-mandated reuse of the proven skew-proof idiom; all outcomes safe.
- No `[0,1]` range validation on rates — mathematically impossible to violate (FILTER count is a subset of the COUNT(\*) denominator in the same GROUP BY).
- Resolve-hint has no test — by-design copy-only (AC5), logic-free constant, AC7 deliberately excludes it.
- Empty-string `alert_code` — unreachable (`alert_code` NOT NULL; response model only built server-side from real rows; matches sibling `AlertFunnel`).
- Dead zero-denominator `None` guard — spec-mandated defensive contract (AC1), mirrors `analytics.py`/`alert_effectiveness_report.py`.
- Report FP-rate at 0 decimals — pre-existing `_fmt_pct`, AC6 imposes no precision, and only already-breaching classes are rendered (no contradictory pair).
