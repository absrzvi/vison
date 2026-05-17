# OEBB Smart Rail — E2 Sprint-Ready Handoff
**Date:** 2026-05-17  
**Previous handoff:** `docs/handoff/2026-05-17-epics-complete-handoff.md`  
**Repo:** https://github.com/absrzvi/vison

---

## Status

**Control Centre Dashboard (E2) dev handover assessment: COMPLETE**  
Open questions OQ2, OQ3, OQ6 resolved. E2 stories are sprint-ready pending E1 foundation gates.

---

## Open Questions Resolved This Session

| OQ | Question | Resolution |
|----|----------|------------|
| OQ2 | WebSocket staleness threshold | **120s default, configurable.** Added `staleness_threshold_sec` (60/120/180/300s) to `operator_preferences` table alongside alert threshold. Nomad provides internet onboard — 120s is a sound starting point. |
| OQ3 | AI escalation confidence threshold | **80% minimum.** Named constant `ALERT_CONFIDENCE_THRESHOLD = 0.80` in `inference/src/inference/detector.py`. Start conservative; tune down post-PoC if incidents are missed. (Was 0.70 placeholder — updated in E4-S5.) |
| OQ6 | Fleet planning queue — internal or ÖBB external system? | **Internal PostgreSQL for PoC.** New `capacity_review_queue` table. Claudia exports as CSV (`GET /api/v1/capacity-review-queue/export`) to share with Passenger Experience / Fleet Management. External system integration out of PoC scope. |

---

## What Changed This Session

### `_bmad-output/planning-artifacts/epics.md`
- **E2-S8 rewritten** — added `operator_preferences` DDL with both `threshold_sec` and `staleness_threshold_sec` fields; full `GET`/`PATCH /api/v1/operators/me/preferences` API contract; `localStorage`-as-cache / server-as-truth reconciliation pattern. Sprint-ready.
- **E2-S9 added** — System Health data feed integration: REST fetch on mount, WS event updates for `CAMERA_DEGRADED`/`CAMERA_RECOVERED`, live-ticking server-sourced timestamps, staleness banner wired to `operator_preferences.staleness_threshold_sec`.
- **E3-S2 updated** — added CSV export ACs (`GET /api/v1/capacity-review-queue/export`), `capacity_review_queue` table DDL, explicit note that no external ÖBB system integration is in scope.
- **E4-S5 updated** — inference confidence threshold changed from `0.70` placeholder to `0.80` (OQ3 resolved).
- **Epic 2 FR coverage** — added FR26 (was missing).

### `_bmad-output/design-artifacts/DD-001-cc-dashboard.md`
- OQ2, OQ3, OQ6 marked resolved with full rationale.

---

## E2 Story Sprint Readiness

| Story | Title | Sprint-ready? |
|-------|-------|---------------|
| E2-S1 | Real WebSocket Client | ✅ |
| E2-S2 | KPI Strip Filter Tap Wiring | ✅ |
| E2-S3 | Fleet List Passenger Count Sort | ✅ |
| E2-S4 | Unified Feed "New Items" Chip | ✅ |
| E2-S5 | Escalation Acknowledge / Resolve API | ✅ |
| E2-S6 | Train Detail Event-Store Alert Integration | ✅ |
| E2-S7 | Loading Skeletons | ✅ |
| E2-S8 | Per-Operator Configurable Preferences | ✅ |
| E2-S9 | System Health Data Feed Integration | ✅ |

---

## E1 Hard Gates Before E2 Sprint Starts

E2 cannot start until these E1 stories are **done**:

| E1 Story | Unblocks |
|----------|----------|
| E1-S1 — System Skeleton MVP | E2-S1 (WebSocket endpoint must exist) |
| E1-S6 — WebSocket Subscription Spec | E2-S1 (SubscriptionRequest contract) |
| E1-S7 — REST API Skeleton + Auth | E2-S5, S6, S8, S9 (all need /api/v1/ endpoints) |
| E1-S3 — PostgreSQL Schema + Alembic | E2-S8 (operator_preferences migration) |

Recommended E1 implementation order: **E1-S1 → E1-S2 → E1-S3 → E1-S6 → E1-S7**, then E2 sprint begins.

---

## Remaining Open Questions (Non-blocking for E2)

| OQ | Question | Blocks | Owner |
|----|----------|--------|-------|
| OQ1 | Pose estimation feasibility for seated/standing split | Coach drill-in columns | Hailo-8 / Nomad Digital |
| OQ4 | Maintenance App deep-link URL + auth | System Health CTA (`MAINTENANCE_APP_ENABLED = false`) | Maintenance App team |
| OQ5 | 7-day trend query key — by train number or route+timeslot? | Analytics trend accuracy | Nomad Digital backend |
| ~~OQ7~~ | ~~CCTV stream amber vs red threshold~~ | ~~System Health badge logic~~ | ✅ Resolved: amber ≥ 2 min (`CCTV_AMBER_SEC=120`), red ≥ 5 min (`CCTV_RED_SEC=300`) |
| ~~OQ8~~ | ~~Applications amber vs red threshold~~ | ~~System Health badge logic~~ | ✅ Resolved: same duration thresholds — `APP_AMBER_SEC=120`, `APP_RED_SEC=300` |
| OQ9 | Health poll interval for rtsp-ingest and event-store | "Updated Xs ago" freshness | Nomad Digital |
| OQ10 | Dismissed exceptions: greyed vs hidden | Analytics exception list | ÖBB operations / Claudia |

OQ9 should be resolved before E2-S9 (System Health) is implemented. OQ7 and OQ8 are resolved.

---

## Agent Roster

| Agent | Role |
|-------|------|
| **Winston** | Architecture, ADRs, container design |
| **Freya** | UX design, interface specs, design system |
| **Amelia** | Requirements, story ACs, backlog |
| **Mary** | Gap analysis, cross-cutting concerns |
| **John** | Implementation, code patterns |

---

## Next Steps

1. Start **E1 implementation** — E1-S1 is the unblocking root story
2. Resolve OQ9 (health poll interval) with Nomad Digital before E2-S9 sprint
3. E2 sprint begins once E1-S1, S2, S3, S6, S7 are done
