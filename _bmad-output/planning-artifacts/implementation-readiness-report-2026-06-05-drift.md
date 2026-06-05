---
stepsCompleted: [step-01-document-discovery, step-02-prd-analysis, step-03-epic-coverage-validation, step-04-ux-alignment, step-05-epic-quality-review, step-06-final-assessment]
documentsIncluded:
  prd: prd.md
  architecture: architecture.md
  epics: epics.md
  ux: ux-design-specification.md
focus: drift-check vs 2026-05-30-pass2
---

# Implementation Readiness Assessment Report — Drift Check

**Date:** 2026-06-05
**Project:** OEBB Smart Rail PoC (Nomad Digital / Hailo-8 AI Insights-as-a-Service)
**Scope:** Drift detection between `architecture.md` and current epics/stories plan since `implementation-readiness-report-2026-05-30-pass2.md`. Focus areas: Epic 10, ADR-20 SSE transport, Hailo-8 / YOLOX detector.

## Step 1 — Document Inventory

| Type | File | Size | Modified | Notes |
|---|---|---|---|---|
| PRD | `prd.md` | 20 KB | 2026-05-31 | single whole doc |
| Architecture | `architecture.md` | 111 KB | **2026-06-05** | single whole doc — modified *after* epics/prd |
| Epics & Stories | `epics.md` | 176 KB | 2026-05-31 | single whole doc |
| UX | `ux-design-specification.md` | 3 KB | 2026-05-31 | thin stub; full UX in design-artifacts/ |

**Duplicates:** none (no sharded/whole conflicts).
**Missing:** none of the four required types.
**Early drift signal:** architecture.md mtime (Jun 5) is 5 days ahead of epics.md/prd.md (May 31). Architecture has moved since the plan was last revised — the prime suspect for drift.

## Step 2 — PRD Analysis

**PRD version:** 1.2 (2026-05-30), status APPROVED. Changelog already ratifies ADR-20 (SSE landside) in v1.2 and descopes FR23/25/32/34/35 to Phase 2 in v1.1.

### Functional Requirements (active in PoC)

Onboard (Edge): FR1 per-coach headcount; FR2 luggage count; FR3 congestion map; FR4 unattended-bag alert; FR5 door obstruction; FR6 TCMS/SNMP alarm surfacing; FR7 correlated door alert; FR8 accessibility detection; FR9 speed-correlated door fault; FR10 depot suppression; FR11 accessibility-door release alert; FR12 ramp-deployed alert.

Control Centre — Live Ops: FR20 live fleet view; FR21 unified prioritised feed; FR22 dwell time; FR24 slip/fall; FR26 degraded-op alert; FR27 trip-ID/route tagging.

Analytics: FR33 anonymised ridership analytics.

**Deferred/out of PoC:** FR13–FR19, FR23, FR25, FR28–FR32, FR34–FR37 (Phase 2 / descoped).

Total active FRs: **19** (FR1–FR12, FR20–FR22, FR24, FR26, FR27, FR33).

### Non-Functional Requirements

NFR1 uptime ≥99.5%; NFR2 occupancy accuracy ≥95% post-hoc vs APC (ADR-15, camera authoritative); NFR3 FP rate <5% via suppression FSM; NFR4 alert latency within 30–90s dwell; NFR5 raw video never leaves train; NFR6 GDPR anonymised; NFR7 -40/+85°C; NFR8 SYS1-down resilience; NFR9 trip_id/vehicle_id/ISO-8601; NFR10 snake_case API; NFR11 `/api/v1/`; NFR12 ≥80% coverage; NFR13 GitLab CI stages; NFR14 structured JSON logging; NFR15 secret hygiene. Total NFRs: **15**.

### UX Design Requirements

UX-DR1–UX-DR15 (app shell, KPI strip, fleet list, unified feed, escalation detail, train detail, system health, analytics 4 sub-tabs, capacity/heatmap/dwell/AI-quality panels, design tokens, 1440px desktop, luggage monitoring). Total: **15**.

### PRD Completeness Assessment

PRD is approved, versioned, and internally consistent. Critically for this drift check: the PRD's §9 Architecture Constraints **already carries ADR-20 SSE (landside) + ADR-9 WS (onboard) split** — so PRD↔transport-decision drift is NOT expected. The open question is whether **epics.md (May 31) and architecture.md (Jun 5)** have kept pace with each other and with the Epic-10 / Hailo-YOLOX decisions logged after these docs were last revised. 13 open questions remain (OQ-13 = SSE multi-worker fan-out, non-blocking for PoC).

## Step 3 — Epic Coverage Validation

### Coverage matrix (active PoC FRs)

| FR | Epic coverage (epics.md FR Coverage Map §124–144) | Status |
|---|---|---|
| FR1–FR3 (occupancy/congestion) | Epic 4 + Epic 2 | ✓ |
| FR4–FR5 (bag/door) | Epic 4 + Epic 2 + Epic 5 | ✓ |
| FR6–FR7 (TCMS/correlated door) | Epic 4 | ✓ |
| FR8, FR11–FR12 (accessibility) | Epic 4 | ✓ |
| FR9–FR10 (speed/suppression) | Epic 4 | ✓ |
| FR20–FR21, FR26 (CC live ops) | Epic 2 | ✓ |
| FR22, FR27, FR33 (dwell/tag/analytics) | Epic 3 + Epic 1 | ✓ |
| FR24 (slip/fall) | Epic 4 | ✓ |
| Deferred: FR13–19, 23, 25, 28–32, 34–37 | Marked Phase 2 in both PRD & epics | ✓ aligned |

### Coverage statistics
- Active PoC FRs: 19 · Covered in epics: 19 · **Coverage: 100%**
- Deferred FRs: PRD §5.4 and epics FR Coverage Map agree on the same descope set (FR23/25/32/34/35 descoped 2026-05-30 in both). **No FR-level drift.**

### Epic 10 / Epic 11 status (focus area)
- **epics.md is MORE current than its mtime implies.** It fully contains Epic 10 (E10-S1 through E10-S5, decomposed into S1a/S1b/S1c) and Epic 11 (Admin & Identity), including `confidence_score`, `INFERENCE_HEARTBEAT`, `alert_class_state` kill-switch, `escalation_audit`. These match the kanban and sprint-status.yaml. ✓ **No Epic-10 plan drift.**
- ⚠️ **PRD lag (minor):** Epic 10 / Epic 11 exist in epics.md but are NOT reflected in the PRD as functional requirements (no FR IDs, not in §5). Epic 10 is sourced from `owning-the-gap-ai-pm-analysis.md`, not the PRD. NFR3 is slated for redefinition by E10-S5 but PRD still carries the old "<5%" wording. **Traceability gap: Epic 10 has no PRD anchor.**

### ADR-20 (SSE transport) — focus area
- ✓ **Fully reconciled across all three docs.** PRD §9 v1.2, epics.md changelog + E1-S6/E1-S6′/E2-S1/E5-S1 story updates, and architecture.md §667 transport table all agree: SSE landside, WS onboard-only. No drift.

### Hailo-8 / YOLOX detector — focus area — ⚠️ **PRIMARY DRIFT FOUND**
The 2026-06-05 architecture edits introduced the YOLOX detector decision into the new §148 capacity-budget section, but did **not** propagate it through the rest of the architecture or into epics:

| Location | Says | Should say |
|---|---|---|
| architecture.md §154, §158 (Jun 5) | **YOLOX / YOLOX-S** person detector | (correct — new decision) |
| architecture.md ADR-15/16 §467, §469, §471 | `yolov8m.hef`, `yolov8m_pose.hef` | YOLOX (AGPL rejection per memory) |
| architecture.md §1198 | eliminates `yolov8m_pose.hef` | model name stale |
| architecture.md source tree §1296, §1585 | `yolov8m.hef` (person/suitcase/bicycle) | YOLOX `.hef` |
| epics.md §1352 | `yolov8m.hef` loaded | YOLOX |

**Impact:** The detector model name is contradictory *within architecture.md itself* and between architecture and epics. Per project memory (`project_hailo_test_decisions`), YOLOX was chosen specifically to avoid yolov8m's AGPL licence — so the stale `yolov8m.hef` references are a licensing-risk drift, not cosmetic. Any dev picking up E4-S4/inference stories from epics.md §1352 or the architecture source-tree diagram would fetch the wrong (AGPL) model.

### Secondary structural issue — duplicate ADR numbering
architecture.md contains **two ADR-15s and two ADR-16s**:
- §435 ADR-15 = Camera-Based Primary Passenger Counting; §463 ADR-16 = Spatial Zone Masking (onboard ADRs)
- §1692 ADR-15 = Control Centre Frontend Stack; §1711 ADR-16 = CC State Management (frontend ADRs)

Cross-references like "ADR-15 Phase 2 amendment" (§151) and "ADR-16" (§467) are ambiguous. Frontmatter `adrUpdates: [ADR-15, ADR-16, ADR-17, ADR-18]` in epics.md compounds the ambiguity. Not a PoC blocker, but a traceability hazard.

## Step 4 — UX Alignment

### UX documentation state
- `ux-design-specification.md` is a **Scenario-06-only conceptual stub** (2026-05-14), not the dashboard spec. The authoritative UX contract is **PRD §7 UX-DR1–UX-DR15** (derived from DD-001 locked prototype) plus the full `design-artifacts/D-UX-Design/` set.

### UX ↔ PRD alignment
- ✓ 15 UX-DRs live *in* the PRD, so UX↔PRD is coherent by construction.
- ⚠️ The whole-doc UX file's `stepsCompleted: [1, 2]` and single-scenario scope make it misleading as "the UX doc." Low risk (the real spec is elsewhere) but a discovery hazard for a new dev.

### UX ↔ Architecture alignment
- ✓ Architecture carries CC-specific ADRs (frontend stack = JS/React/Vite, state management) that support UX-DR13 design tokens and UX-DR1–12 component structure.
- ✓ SSE transport (ADR-20) supports the real-time UX-DR2 KPI strip / UX-DR4 unified feed / UX-DR15 luggage live updates — consistent across PRD §9, architecture §667, and epics.
- ⚠️ **Epic-10 UI surfaces vs UX-DRs:** E10-S1c adds a per-alert **confidence chip**, a **degraded banner**, and an **AI pipeline health row** (System Health); E10-S5 adds an **AI Quality rates** component. None of these are described in UX-DR1–UX-DR15. New operator-facing UI is being introduced through epics with **no corresponding UX-DR and no PRD anchor** — same traceability gap as the FR side. Freya (WDS) owns CC UX; these surfaces bypassed the UX-DR register.

## Step 5 — Epic Quality Review (scoped to drift / in-flight work)

> This is a drift check, not a full re-audit. Epics 1–9 are shipped/validated by prior readiness reports (2026-05-17, 2026-05-30 ×2). Quality review here focuses on the **recently added Epic 10 / Epic 11 cluster** and any structural drift the 2026-06-05 work introduced.

### 🔴 Critical violations
- **None.** No technical-milestone-only epics in the new cluster; Epic 10 is framed as user value ("operator changes how they run trains"), Epic 11 as identity/admin value.

### 🟠 Major issues
- **Epic 10 has no PRD/FR or UX-DR anchor** (carried from Steps 3–4). Epic 10's stories introduce schema changes (`confidence_score`, `INFERENCE_HEARTBEAT`, `escalation_audit`) and operator UI with no FR ID and no UX-DR. Traceability is to `owning-the-gap-ai-pm-analysis.md` only. Recommendation: add FR38+ (or an explicit "trust & adoption" NFR cluster) to the PRD and UX-DR16+ for the three E10-S1c surfaces, so the matrix closes.
- **Detector model drift** (carried from Step 3): epics.md §1352 + architecture source-tree say `yolov8m.hef`; new capacity budget says YOLOX. A dev implementing the inference story would fetch the AGPL model. **This is the highest-priority remediation** because it crosses the licensing boundary in CLAUDE.md security notes.

### 🟡 Minor concerns
- **Forward dependency E10 → E11 (mitigated):** Epic 11 is numbered/positioned after Epic 10 yet Epic 10's kill-switch admin UI conceptually belongs to it. epics.md explicitly resolves this: E10-S1 ships behind a shared `CC_ADMIN_KEY` seam (curl-operated per E10-S3 playbook); E11 swaps in JWT later. Documented and intentional — **not a true forward dependency**, but the epic numbering reads backwards (the prerequisite is numbered higher).
- **E10 internal dependencies are clean & backward:** S2→S1, S3→S1, S4→S2, S5→S1+S2. No forward refs within the epic. ✓
- **E4-S6 oversized-story flag still open** (epics.md §1428): bundles 6 modules, flagged "split before dev pickup" 2026-05-30 into E4-S6a..E4-S6c. Epic 4 is marked Done in the epic list (§153) — so either the split happened during dev or the flag is stale. **Status mismatch to reconcile:** the in-line ⚠ warning contradicts the Done status.
- **Duplicate ADR numbering** (carried from Step 3): two ADR-15 / two ADR-16 in architecture.md. Recommend renumbering the frontend pair (e.g. ADR-CC-1/2) or a clear namespace.

## Summary and Recommendations

### Overall Readiness Status

**NEEDS WORK (minor)** — No blocker to continuing Epic 10 implementation. The plan↔architecture spine is sound: FR coverage is 100%, ADR-20 SSE is fully reconciled across PRD/epics/architecture, and Epic 10/11 are properly scoped in epics.md and sprint-status. The drift is concentrated in **one substantive item (detector model)** plus a cluster of **traceability/consistency gaps**.

### Critical issues requiring action

1. **Detector model drift (YOLOX vs yolov8m) — fix before any inference story dev.** The 2026-06-05 capacity-budget edit adopted YOLOX but left `yolov8m.hef` / `yolov8m_pose.hef` in architecture ADR-15/16 (§467/469/471), the source-tree diagram (§1296/1585), the pose-removal note (§1198), **and epics.md §1352**. Per memory `project_hailo_test_decisions`, YOLOX was chosen to avoid yolov8m's AGPL licence — so a dev following the stale refs would pull an AGPL-licensed model into a commercial product. Crosses the CLAUDE.md licensing/security boundary.

### Major (close before pilot signoff)

2. **Epic 10 has no PRD/FR or UX-DR anchor.** Add FR38+ (or a "Trust & Adoption" requirement cluster) and UX-DR16+ for the three E10-S1c surfaces (confidence chip, degraded banner, AI pipeline row) + E10-S5 AI Quality rates. Currently traceable only to `owning-the-gap-ai-pm-analysis.md`.
3. **NFR3 redefinition pending.** PRD still says FP rate "<5%"; E10-S5 is scheduled to redefine it into three observable rates. PRD NFR3 and E10-S5 will conflict until the PRD is updated — sequence the PRD edit with E10-S5.

### Minor (housekeeping)

4. **Duplicate ADR numbering** in architecture.md (two ADR-15, two ADR-16). Renumber the frontend pair.
5. **E4-S6 status mismatch:** in-line "split before dev pickup" ⚠ vs Epic 4 = Done. Confirm the split shipped and clear the stale warning.
6. **UX stub file** `ux-design-specification.md` is single-scenario; add a pointer to the real UX-DR register (PRD §7) + `D-UX-Design/` to avoid misdirection.
7. **Doc mtime hygiene:** epics.md content is current (has Epic 10/11) but was last *saved* 2026-05-31; architecture moved 2026-06-05. Re-save epics with the YOLOX correction so mtime reflects currency.

### Recommended next steps

1. **Global find/replace `yolov8m` → YOLOX** across architecture.md and epics.md §1352 (preserve the `_pose` distinction: YOLOX-Pose or the chosen pose model), with a one-line ADR-15/16 amendment note dated 2026-06-05. *(Tier-2 doc edit.)*
2. Add FR + UX-DR anchors for Epic 10 (PRD §5/§7) so the traceability matrix closes; redefine NFR3 in lockstep with E10-S5.
3. Renumber duplicate frontend ADRs; reconcile E4-S6 status; fix the UX stub pointer.
4. Then resume `bmad-dev-story` for **10-1-alert-confidence-and-ai-pipeline-health** (unblocked — none of the above gates it, but item 1 should land first since 10-1 touches inference/shared schema).

### Final note

This assessment identified **7 issues across 4 categories** (1 critical, 2 major, 4 minor). Only item 1 (detector model) should be fixed before touching inference code; the rest are pre-pilot-signoff housekeeping and do not block Epic 10 dev. The core plan is aligned — this is drift cleanup, not a replan.

---

_Drift readiness check — 2026-06-05 — assessor: Claude (PM/requirements-traceability). Method: bmad-check-implementation-readiness, drift-scoped._
