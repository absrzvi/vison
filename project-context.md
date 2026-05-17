# ÖBB Smart Rail — Project Context

## Project Overview

**Name:** OEBB Smart Rail  
**Domain:** Austrian rail operations (ÖBB)  
**Stage:** UX design complete, entering design refinement and architecture phase

A Hailo-8 M.2 edge AI platform onboard ÖBB trains powers two AI services:
- **Passenger AI** — real-time occupancy, luggage detection, accessibility detection, passenger guidance
- **Diagnostics AI** — TCMS/SNMP fault ingestion, plain-language fault explanation, cross-correlated door/camera alerts

Both services are surfaced across 7 role-specific interfaces (4 onboard, 3 landside).

---

## User Roles

### Onboard
| Role | Device | Primary AI service |
|---|---|---|
| Conductor / Train Manager | Mobile handheld | Both |
| Onboard Technician | Mobile handheld | Diagnostics AI |
| Bistro / Café Staff | Tablet or handheld | Passenger AI |
| Driver | Cab-mounted display | Both (display only) |

### Landside
| Role | Device | Primary AI service |
|---|---|---|
| Control Centre Operator | Web dashboard | Both |
| Fleet Maintenance Manager | Web dashboard | Diagnostics AI + occupancy |
| Capacity Planner | Web reports | Passenger AI analytics |
| Platform Staff / Station Manager | Tablet or display | Passenger AI |

---

## Current Design Stage

- 8 personas defined
- 57 user stories written (35 use cases)
- Full UX design spec complete for all 7 interfaces
- HTML mockups complete for all 7 interfaces
- AI service architecture designed (Hailo-8 M.2, edge + cloud hybrid)
- React + Vite prototype (`control-centre/`) in active iterative refinement — all 5 tabs implemented and Freya-reviewed
- **Next:** Architecture spec (Winston), then BMAD implementation planning

---

## Key Design Decisions Made

- Single Hailo-8 M.2 on SYS2 handles all Passenger AI inference onboard
- Diagnostics AI ML models and LLM run landside (cloud), only structured SNMP data processed onboard
- All 7 interfaces share a unified alert severity model (critical / warning / info)
- Conductor app surfaces both AI services in one unified feed — no separate app per service
- Driver display is read-only (no interaction, safety requirement)

---

## Existing Artifacts

| Artifact | Location |
|---|---|
| UX design spec | `_bmad-output/design-artifacts/D-UX-Design/2026-05-13-oebb-ux-design.md` |
| AI service design | `_bmad-output/design-artifacts/D-UX-Design/2026-05-13-oebb-hailo8-ai-service-design.md` |
| User stories (57) | `_bmad-output/planning-artifacts/2026-05-13-oebb-user-stories.md` |
| HTML mockups (7) | `mockups/` |

---

## WDS Design Phase Status

| Phase | Folder | Status |
|---|---|---|
| A — Product Brief | `_bmad-output/design-artifacts/A-Product-Brief/` | Not started (derive from existing docs) |
| B — Trigger Map | `_bmad-output/design-artifacts/B-Trigger-Map/` | Not started |
| C — UX Scenarios | `_bmad-output/design-artifacts/C-UX-Scenarios/` | Partial (user stories exist) |
| D — UX Design | `_bmad-output/design-artifacts/D-UX-Design/` | Complete (refine with Saga/Freya) |
| G — Product Development | `_bmad-output/design-artifacts/G-Product-Development/` | Not started |

---

## Coding Craft Principles (Karpathy Guidelines)

All development agents follow these principles. They override default instincts toward completeness or speculation.

### 1. Think Before Coding

Before implementing: state assumptions explicitly. If uncertain, ask. If multiple interpretations exist, present them — don't pick silently. If something is unclear, stop and name what's confusing. Surface tradeoffs before writing code.

### 2. Simplicity First

Minimum code that solves the problem. Nothing speculative.
- No features beyond what was asked.
- No abstractions for single-use code.
- No "flexibility" or "configurability" that wasn't requested.
- No error handling for impossible scenarios — trust internal code and framework guarantees; only validate at system boundaries.
- If you write 200 lines and it could be 50, rewrite it.

### 3. Surgical Changes

Touch only what you must. Clean up only your own mess.
- Don't improve adjacent code, comments, or formatting.
- Don't refactor things that aren't broken.
- Match existing style, even if you'd do it differently.
- If you notice unrelated dead code, mention it — don't delete it.
- Every changed line must trace directly to the user's request.

### 4. Goal-Driven Execution

Transform tasks into verifiable goals. For multi-step tasks, state a brief plan with per-step verification criteria before touching code. Strong success criteria let you loop independently.
