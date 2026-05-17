# OEBB Smart Rail — Architecture Phase 3 Handoff
**Date:** 2026-05-15
**Previous handoff:** `docs/handoff/2026-05-14-oebb-smart-rail-v3-handoff.md`
**Architecture document:** `_bmad-output/planning-artifacts/architecture.md`
**Workflow:** BMad `bmad-create-architecture` skill, Winston (System Architect) persona

---

## Session Summary

Phase 3 (Architecture) is **in progress**. Steps 1–6 complete, Step 7 (validation) was presented but not saved. The architecture document is substantive and ready for the validation save + Step 8 completion.

---

## Architecture Document Status

**File:** `_bmad-output/planning-artifacts/architecture.md`
**Frontmatter:** `stepsCompleted: [1, 2, 3, 4, 5, 6]`

### What's in the document (Steps 1–6, all saved):

| Step | Section | Status |
|---|---|---|
| 1 | Initialization + input documents | ✅ saved |
| 2 | Project Context Analysis (party mode enhanced) | ✅ saved |
| 3 | Technology Foundations (party mode enhanced) | ✅ saved |
| 4 | Core Architectural Decisions — 14 ADRs (party mode enhanced) | ✅ saved |
| 5 | Implementation Patterns & Consistency Rules (party mode enhanced) | ✅ saved |
| 6 | Project Structure & Boundaries (hailo-apps research incorporated) | ✅ saved |
| 7 | Architecture Validation Results | ❌ NOT YET SAVED — presented but session paused |

---

## Step 7 Validation Results (to be saved next session)

The validation was run and all checks passed. Here is the complete content ready to append:

### Outcome
- **Overall Status: READY FOR IMPLEMENTATION**
- **Confidence level: High**
- All 16 checklist items: `[x]`
- No critical gaps remaining

### Coherence Validation ✅
- All technology choices compatible (HailoRT 4.23, Python 3.11, asyncio, httpx, FastAPI, SQLite WAL, PostgreSQL, React+Vite)
- hailo-apps multisource + detection + BYTETracker + pose_estimation confirmed MIT licensed and directly reusable
- `shared/` package installable in both `python:3.11-slim-bookworm` and Hailo Suite Docker base images (note: each `Dockerfile` must include `pip install -e ./shared`)
- snake_case/PascalCase/UPPER_SNAKE_CASE patterns consistent across all layers
- 14 MUST rules all traceable to specific ADRs

### Requirements Coverage ✅
All 6 Passenger AI capabilities architecturally supported. TCMS/PIS have known external dependencies (not blockers — stubs in place). All 3 pilot success criteria (dwell time, passenger congestion, luggage congestion) measurable from event timestamps from day one.

### Implementation Readiness ✅
14 ADRs with rationale, implementation sequence (14 steps ordered by dependency), all 10 scenarios mapped to specific files, all architectural boundaries defined with protocol + auth + direction.

### Gaps (important, not blocking)
| Gap | Resolution |
|---|---|
| `shared/` pip install in both Docker base images | Document in each `Dockerfile` + `README.md` |
| Wheelchair/pushchair COCO proxy accuracy | Validate in PoC week 1–2; fine-tune post-PoC if needed |
| PIS L2 write API | Technical dep on Stadler/ÖBB network team |
| CI/CD platform (GitHub vs GitLab) | One-sentence confirm from Nomad Digital |
| Hailo-8 TOPS budget per stream | Confirm camera count from R5001C hardware spec |

### Key Strengths
- hailo-apps eliminates highest-risk custom engineering (RTSP + GStreamer + Hailo device)
- Single-writer SQLite pattern eliminates most common embedded event store concurrency bug
- APC Protocol stub means APC uncertainty cannot block critical path
- Suppression state machine elevated to correctness requirement
- journey_id midnight-crossing bug prevented by `journey_start_date` anchor in `vlan-pollers`
- 14 MUST rules + CI enforcement config (ruff S101/DTZ, mypy --strict, bandit, detect-secrets)

### Post-PoC Enhancements (documented, not open)
- JWT auth (Phase 2 explicit gate)
- PWA offline service worker (Phase 2)
- PostgreSQL HA (fleet rollout gate)
- Custom wheelchair/pushchair model (post-PoC if COCO proxy insufficient)
- Multi-CCU coupled-train topology (explicit deferral)
- ML predictive fault models (month 4–6)

---

## Key Design Decisions (do not re-open)

### From Phase 2 (UX — all locked)
- Hailo-8 is the primary detection trigger for all onboard alerts
- Ramps deploy automatically via TCMS — Conrad's role is presence only
- Auto-resolve pattern: alerts resolve on sensor change, not manual action
- Event-gated camera model: single still-frame at detection time only
- `--color-review` (steel blue) for unattended bag; `--color-accessibility` (blue-teal) for accessibility
- 3-band occupancy for staff; 4-band for passenger portal (intentional divergence)

### From Phase 3 (Architecture — all locked)
- Single-vehicle PoC only — multi-CCU deferred
- 5 interfaces in pilot: Conductor App, Passenger Portal (demo screen), PIS screens, Control Centre Dashboard, Driver Display
- Bistro App + Maintenance Dashboard descoped from PoC
- Pilot success criteria: reduce dwell time + reduce passenger/luggage congestion
- journey_id: `{vehicle_id}_{trip_number}_{journey_start_date_YYYYMMDD}` (start date, not event date)
- SQLite single-writer via event-store HTTP POST (ADR-4 sync cursor pattern)
- APC format open → `APCAdapter` Protocol stub + `MockAPCAdapter`
- Suppression state machine in `fusion/suppression.py` — correctness requirement, not a library
- VLAN isolation for onboard auth in PoC; JWT deferred to Phase 2
- API key for cloud auth in PoC; OIDC upgrade path documented
- WebSocket subscription model with 50-event reconnect replay (ADR-9)
- hailo-apps (MIT) reused for: `multisource` (RTSP), `detection` (YOLO), BYTETracker, `pose_estimation`
- `rtsp-ingest` + `inference` base from Hailo Software Suite Docker image (HailoRT 4.23 + TAPPAS 5.1.0)

---

## Open External Dependencies

| Dependency | Impact | Owner |
|---|---|---|
| APC data format (AFZ supplier) | Fusion ground-truth; stub unblocks ADR | Nomad Digital / AFZ supplier |
| TCMS alarm name list (Stadler xlsm) | vlan-pollers snmp schema completeness | Stadler |
| L2 write access to PIS screens | All PIS scenario outputs | Stadler / ÖBB network team |
| Camera count per tier per train | inference/budget.py TOPS allocation | R5001C hardware spec |
| Cloud backend hosting (Nomad vs Azure/AWS) | Cloud sync retry + schema versioning | Nomad Digital commercial |
| Source control platform (GitHub vs GitLab) | CI/CD pipeline YAML | Nomad Digital internal |
| GDPR sign-off from ÖBB legal | Cloud sync data policy | ÖBB legal |

---

## How to Resume Next Session

1. Activate Winston: use `bmad-agent-architect` skill
2. Winston activates `bmad-create-architecture` workflow
3. Workflow will detect `stepsCompleted: [1, 2, 3, 4, 5, 6]` in frontmatter → load `step-01b-continue.md`
4. Navigate to Step 7 — paste or re-present the validation results above
5. Save Step 7 → proceed to Step 8 (completion + implementation guidance)

---

## Project Files Reference

| Artifact | Location |
|---|---|
| **Architecture document** | `_bmad-output/planning-artifacts/architecture.md` |
| UX design spec (v2) | `_bmad-output/design-artifacts/D-UX-Design/2026-05-14-oebb-ux-design-v2.md` |
| AI service design | `_bmad-output/design-artifacts/D-UX-Design/2026-05-13-oebb-hailo8-ai-service-design.md` |
| Inference pipeline design | `docs/superpowers/specs/2026-05-14-onboard-inference-pipeline-design.md` |
| Product brief | `_bmad-output/design-artifacts/A-Product-Brief/product-brief.md` |
| User stories (57) | `_bmad-output/planning-artifacts/2026-05-13-oebb-user-stories.md` |
| Scenario specs (all 13) | `_bmad-output/design-artifacts/D-UX-Design/scenario-*-specs/` |
| Validation reports (10 high-priority) | `_bmad-output/_progress/scenario-*-validation-report-*.md` |
| HTML mockups | `mockups/` |
| Project context | `project-context.md` |
