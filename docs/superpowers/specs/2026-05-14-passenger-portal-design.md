# Passenger Portal — Coach Guidance Design Spec
**Date:** 2026-05-14
**Agents:** Saga (analyst) · Freya (UX designer)
**WDS Phase:** 2 (Trigger Mapping) → 4 (UX Design)
**Status:** Complete — ready for implementation planning

---

## What We Built

A live coach occupancy guidance panel added to the ÖBB Railnet CNA (Captive Network Assistant) portal — the WiFi splash page every passenger sees before connecting to onboard WiFi.

**Position:** Below the existing entertainment promo, above the VERBINDEN button.
**Reach:** 100% of passengers on any device, no login, no app, no opt-in.
**Language:** German only.
**Load time:** <1 second (served locally from Nomad Digital R5001C).

---

## New Personas (Saga)

### Persona 9 — Petra (Passenger, General)
- **File:** `_bmad-output/design-artifacts/B-Trigger-Mapping/persona-passenger-general.md`
- **Core tension:** 90-second boarding window, wrong coach = standing for 2 hours
- **Top driving force (15/15):** Know where space is available before committing to a door
- **Use cases:** UC-P01 through UC-P05

### Persona 10 — Hanna (Passenger, Accessibility)
- **File:** `_bmad-output/design-artifacts/B-Trigger-Mapping/persona-passenger-accessibility.md`
- **Core tension:** PRM space may be full; ramp may not be ready; staff may not know she is coming
- **Top driving forces (15/15 each):** Confirm space available before walking to door · Know exact door number
- **Use cases:** UC-A01 through UC-A05

---

## Use Cases Summary

### General passenger (Petra)
| Code | Scenario | Portal behaviour |
|---|---|---|
| UC-P01 | Mixed load — no clear best coach | Show coach colours only, no arrow |
| UC-P02 | One coach clearly least occupied | Show "Gehen Sie zu Wagen N →" with directional arrow |
| UC-P03 | All coaches >85% full | Show "Zug stark besetzt — Wagen N am wenigsten voll" |
| UC-P04 | Connects after boarding mid-journey | Show current load; offer reposition guidance |
| UC-P05 | Luggage density high in recommended coach | Steer to coach with available rack space |

### Accessibility passenger (Hanna)
| Code | Scenario | Portal behaviour |
|---|---|---|
| UC-A01 | Accessible space free | Show door + ramp preparing; fire Conrad alert silently |
| UC-A02 | Accessible space occupied | Show occupied; direct to find conductor |
| UC-A03 | Multiple accessible coaches | Show both with status; recommend nearest |
| UC-A04 | Automatic Conrad alert | Fires on page load — no passenger action needed |
| UC-A05 | Ramp confirmed by Conrad | Panel updates live: "Rampe bereit ✓" |

---

## Panel Design (Freya)

**Full spec:** `_bmad-output/design-artifacts/E-Passenger-Portal/passenger-portal-ux-design.md`
**Mockup:** `mockups/passenger-portal-v1.html` (8 interactive states)

### Panel structure
```
┌─ PANEL HEADER ─────────────────────────────┐
│  ZUGAUSLASTUNG  •  Wagen 1–8    🟢 Vor 8s  │
├─────────────────────────────────────────────┤
│  [W1][W2][W3][W4][W5][W6][W7][W8]          │  ← coach diagram, always shown
│   🟢  🟡  🟢  🟠  🟢  🟢  🟡  🟢           │
├─────────────────────────────────────────────┤
│  → Gehen Sie zu Wagen 6                     │  ← guidance box, conditional
│     Viel Platz · Gepäckfach frei            │
├─────────────────────────────────────────────┤
│  ♿ Rollstuhlplatz frei                      │  ← accessibility panel, conditional
│     Wagen 2 · Tür 1                         │
│     Rampe wird vorbereitet …                │
└─────────────────────────────────────────────┘
```

### 8 portal states
| State | Trigger | Key behaviour |
|---|---|---|
| 1 — Mixed load | Load spread across train | Coach colours only, no arrow |
| 2 — Clear recommendation | One coach >20% less full | Green box + directional arrow + coach name |
| 3 — Train full | All coaches >85% | Amber warning box, least-worst coach named |
| 4 — Accessibility free | PRM space available | Blue accessibility panel + ramp status |
| 5 — Accessibility occupied | PRM space taken | Amber panel, contact conductor |
| 6 — Ramp confirmed | Conrad confirms in app | Panel updates live to "Rampe bereit ✓" |
| 7 — Stale data | >60s since last update | Diagram desaturated, no recommendation shown |
| 8 — No data | Hailo offline | Diagram hidden, graceful fallback message |

### Directional arrow logic
Arrow shown only when ALL THREE conditions met:
1. One coach >20% less occupied than next-best
2. Train orientation data available and <5 min old
3. Recommended coach is not nearest to passenger's likely position

### Occupancy thresholds (consistent with all interfaces)
| Colour | Range | German label |
|---|---|---|
| Green `#22C55E` | 0–60% | Viel Platz |
| Amber `#F5A623` | 61–85% | Mäßig besetzt |
| Orange `#FF6B00` | 86–100% | Stark besetzt |
| Red `#FF3B3B` | >100% | Überfüllt |

---

## Technical Requirements

| Item | Requirement |
|---|---|
| Data source | Local REST API on R5001C — `GET /api/v1/coach-load` |
| Refresh | 30s interval + on page load |
| Conrad alert | `POST /api/v1/accessibility-alert` — fires silently on page load when PRM data present |
| Train orientation | `GET /api/v1/train-orientation` — optional, degrades gracefully |
| Load time | <800ms total render (all assets local) |
| Fallback | API error or timeout >2s → hide diagram, show "nicht verfügbar" |
| DSGVO | No personal data, no cookies, no analytics — all processing onboard |
| Language | German only |

---

## Artifacts Produced

| Artifact | Path |
|---|---|
| Persona — Petra (general) | `_bmad-output/design-artifacts/B-Trigger-Mapping/persona-passenger-general.md` |
| Persona — Hanna (accessibility) | `_bmad-output/design-artifacts/B-Trigger-Mapping/persona-passenger-accessibility.md` |
| Use cases | `_bmad-output/design-artifacts/E-Passenger-Portal/passenger-portal-use-cases.md` |
| UX design spec | `_bmad-output/design-artifacts/E-Passenger-Portal/passenger-portal-ux-design.md` |
| HTML mockup (8 states) | `mockups/passenger-portal-v1.html` |
| This spec | `docs/superpowers/specs/2026-05-14-passenger-portal-design.md` |
