# OEBB Smart Rail — Epics & Stories Complete Handoff
**Date:** 2026-05-17  
**Previous handoff:** `docs/handoff/2026-05-16-architecture-complete-handoff.md`  
**Repo:** https://github.com/absrzvi/vison

---

## Status

**Epic & Story Planning: COMPLETE**  
`epics.md` — `stepsCompleted: [1, 2, 3]`, `adrUpdates: [ADR-15, ADR-16, ADR-17, ADR-18]`

All 34 stories written across 4 epics. Architecture extended with ADRs 15–18. Event payload schemas updated. Repo initialized and pushed to GitHub.

---

## BMAD Agent Roster

| Agent | Role | When to invoke |
|---|---|---|
| **Winston** | Architect | Architecture decisions, ADRs, container design, data flow |
| **Freya** | UX Designer | All UX topics — interfaces, components, flows, design system. **Use Freya, not Sally** |
| **Amelia** | Product Manager | Requirements, scope, story acceptance criteria, backlog |
| **Mary** | Business Analyst | Gap analysis, requirements traceability, cross-cutting concerns |
| **John** | Developer | Implementation detail, code patterns, technical feasibility |

Party mode tip: invoke agents via `/p` — pick 2–4 relevant voices per round, spawn in parallel.

---

## Key Artifacts

| Artifact | Location |
|---|---|
| Architecture + ADRs 1–18 | `_bmad-output/planning-artifacts/architecture.md` |
| Epics & Stories (34 stories) | `_bmad-output/planning-artifacts/epics.md` |
| Event payload schemas | `_bmad-output/planning-artifacts/event-payload-schemas.md` |
| Control Centre Dashboard DD | `_bmad-output/design-artifacts/DD-001-cc-dashboard.md` |
| UX design spec v2 | `_bmad-output/design-artifacts/D-UX-Design/2026-05-14-oebb-ux-design-v2.md` |
| HTML mockups (7 interfaces) | `mockups/` |
| Control Centre React prototype | `control-centre/src/` |
| Shared Python library | `shared/src/oebb_shared/` |
| Event-store skeleton | `event-store/src/event_store/` |

---

## What Was Done This Session

### ADRs 15–18 (added to `architecture.md`)
- **ADR-15** — Camera-primary counting: camera count is authoritative; APC is calibration reference only (Dilax dropped — not on this train; APC adapter remains as phase 2 hook via `MockAPCAdapter`)
- **ADR-16** — Spatial zone masking: static per-coach seat/standing zone polygons in `cameras.json`; no per-frame dynamic calibration
- **ADR-17** — Inter-wagon closed-ledger reconciliation: P1 gangway tripwires, `WAGON_EXIT`/`WAGON_ENTRY` pairs, `LEDGER_DRIFT_ALERT` before station arrival
- **ADR-18** — Three fusion triggers: (1) door release → `STREAM_PRIORITY` internal command to `rtsp-ingest`; (2) `COACH_COMFORT_INDEX` event on station approach / 10% occupancy delta; (3) GPS/PIS proximity (2 min) → `priority: "escalated"` on `ALERT_RAISED`

### New event types added to `event-payload-schemas.md`
`CALIBRATION_DRIFT`, `WAGON_EXIT`, `WAGON_ENTRY`, `LEDGER_DRIFT_ALERT`, `COACH_COMFORT_INDEX`, `STREAM_PRIORITY` (internal only — not persisted, not published via MQTT)

### Stories modified
- **E4-S1** (`vlan-pollers`) — Added: door-release push to `rtsp-ingest` (ADR-18 T1); station proximity → `ContextState.station_approach` flag (ADR-18 T3)
- **E4-S3** (`rtsp-ingest`) — Added: receives door-release context push, raises camera priority to P1 for 120s internally
- **E4-S4** (`inference`) — Added: static zone mask AC (ADR-16)
- **E4-S6** (`fusion`) — Modified: removed 70/30 weighted average; camera count is authoritative (ADR-15)

### New stories added
- **E4-S8** — Gangway Tripwire Ingest (`inference/tripwire.py`)
- **E4-S9** — Closed-Ledger Reconciliation Engine (`fusion/ledger.py`)
- **E4-S10** — Coach Comfort Index (`fusion/comfort_index.py`)

### Git
- Repo initialized at `C:\Users\AbbasRizvi\Documents\oebb-agent`
- Remote: https://github.com/absrzvi/vison
- Initial commit pushed: 306 files, all planning artifacts, source skeletons, mockups, design docs

---

## Epic Summary

| Epic | Title | Stories | Status |
|---|---|---|---|
| E1 | Shared Infrastructure & Contracts | 7 stories | Written |
| E2 | Control Centre Dashboard (Landside) | 10 stories | Written |
| E3 | Landside Ingest & Cloud Backend | 5 stories | Written |
| E4 | Onboard Container Stack | 12 stories (incl. E4-S8/9/10) | Written |
| 4.CS1 | Cloud-Sync Container | 1 story | Written |

---

## Next Steps

### Immediate: Step 4 — Final Validation
Run the epics skill final validation step:
```
Read and follow: .claude/skills/bmad-create-epics-and-stories/steps/step-04-final-validation.md
```

### Then: Implementation
Recommended sequence (from architecture.md):
1. **E1** — Shared library + contracts (foundation for everything)
2. **E2** — Control Centre Dashboard (landside, testable without hardware)
3. **E3** — Cloud backend + MQTT ingestor
4. **E4** — Onboard containers (requires Hailo-8 hardware for full integration tests)

### Party mode for implementation decisions
- Architecture/container questions → Winston
- UX/interface questions → **Freya** (not Sally)
- Story/requirements questions → Amelia or Mary
- Code patterns → John

---

## Open Items / Decisions Deferred

| Item | Status |
|---|---|
| APC passenger counting system format | Phase 2 — `MockAPCAdapter` in place |
| PIS L2 write API (Stadler/ÖBB network team) | Still pending |
| Wheelchair/pushchair detection accuracy | Post-PoC |
| GitLab CI pipeline | Deferred (E1-S8 dropped this session) |
