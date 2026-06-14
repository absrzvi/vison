# Story 10.5: Alert Quality Measurement (Resolution-Quality Rates)

Status: ready-for-dev

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

- [ ] **T1 — cloud-backend endpoint + service (AC1)** — Tier 2
  - [ ] `api/ai_quality.py`: `ResolutionRate` / `AlertQualityRates` Pydantic response models (`rate: float | None`, integer counts).
  - [ ] `services/ai_quality_rates.py`: SQL over `escalation_audit` (transition='resolved', 7-day COALESCE window, `jsonb_array_elements_text` for `false_alarm` count + zero-tag count + `resolved_total`); compute both rates with `None` on zero denominator. Docstring records why the epic's 3rd rate (auto-resolved-before-ack) is absent (D2).
  - [ ] `routes/ai_quality.py`: `APIRouter(prefix="/api/v1/ai-quality", dependencies=[Security(require_api_key)])`, `GET /resolution-rates`; register in `main.py` via `include_router`.
  - [ ] mypy `--strict` + ruff clean on touched files.
- [ ] **T2 — System Health component (AC2, AC3)** — Tier 2
  - [ ] `components/health/AIQualityRates.jsx` + `.css`: fetch endpoint, per-class table, two columns, `% (n of d)` format, three-state handling, `--obb-*` tokens only.
  - [ ] Mount as sibling of `AIPipelineRow` in `SystemHealth.jsx` (D3) — render even when the train-grid fetch fails, matching the `AIPipelineRow` precedent at [SystemHealth.jsx:228-230](../../control-centre/src/components/health/SystemHealth.jsx).
- [ ] **T3 — Resolve-flow hint (AC5)** — Tier 2
  - [ ] Copy-only `<p>` helper above the `ACTION_TAGS` picker in `EscalationDetail.jsx`. Do NOT touch `ACTION_TAGS` or backend taxonomy.
- [ ] **T4 — Weekly-report NFR3 breach flag (AC6)** — Tier 2
  - [ ] Extend `_funnel_rows` (or add a sibling query) to carry per-class `false_alarm` + `resolved` counts; add a "NFR3 breaches (explicit_fp_rate ≥ 5%)" render section; zero-resolve guard.
- [ ] **T5 — PRD NFR3 redefinition (AC4)** — Tier 2 (docs)
  - [ ] Rewrite NFR3 row, drop `⚠ pending`, update FR42 parenthetical, add changelog `1.4` entry.
- [ ] **T6 — Tests + browser verify (AC7)** — Tier 2/3 (testcontainers needs Docker)
  - [ ] cloud-backend unit/integration (mix, null, boundary, auth); report tests (flag/no-flag/zero-resolve); CC vitest (4 states + format + no-aggregate); browser verify golden + edge.

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

### Debug Log References

### Completion Notes List

### File List
