# Trigger Map — OEBB Smart Rail Passenger Intelligence

**Phase:** 2 — Trigger Map
**Date:** 2026-05-14
**Status:** Complete

---

## Overview

| Document | Contents |
|---|---|
| `01-Business-Goals.md` | 3 goals × 3 SMART objectives |
| `02-Conductor-Conrad.md` | Primary persona — full profile + driving forces |
| `03-Control-Centre-Claudia.md` | Secondary persona — full profile + driving forces |
| `04-Supporting-Personas.md` | Brigitte (Bistro), Diego (Driver), Finn (Fleet Manager) |
| `05-Key-Insights.md` | 4 strategic insights + prioritisation table |

---

## Visual Trigger Map

```mermaid
graph LR
    G1["🎯 Goal 1\nInfrastructure AI Provider\n• Renew ÖBB pilot\n• Sign 2nd operator\n• 40%+ gross margin"] --> P["🚆 OEBB Smart Rail\nPassenger Intelligence\nHailo-8 M.2 · Edge AI\nPrivacy-by-design SaaS"]
    G2["📈 Goal 2\nÖBB Staff Effectiveness\n• -50% manual checks\n• -30% door delays\n• 80% adoption"] --> P
    G3["🔒 Goal 3\nPrivacy by Design\n• Zero raw video off-train\n• DP review passed\n• Replicable architecture"] --> P

    P --> Conrad["👥 Conductor Conrad\nPRIMARY"]
    P --> Claudia["👤 Control Centre Claudia\nSECONDARY"]
    P --> Brigitte["Bistro Brigitte\nSUPPORTING"]
    P --> Diego["Driver Diego\nSUPPORTING"]
    P --> Finn["Fleet Manager Finn\nSUPPORTING"]

    Conrad --> C1["✅ Know whole train at a glance"]
    Conrad --> C2["✅ Act before problems escalate"]
    Conrad --> C3["✅ Feel in control at departure"]
    Conrad --> C4["✅ Look authoritative to passengers"]
    Conrad --> C5["✅ Less walking, more managing"]
    Conrad --> C6["❌ Fear missing safety incident"]
    Conrad --> C7["❌ Fear blamed for delayed departure"]
    Conrad --> C8["❌ Fear alert overload / false positives"]
    Conrad --> C9["❌ Fear public incompetence"]
    Conrad --> C10["❌ Resents tools requiring training"]

    Claudia --> CL1["✅ Real occupancy across fleet"]
    Claudia --> CL2["✅ Make defensible decisions"]
    Claudia --> CL3["✅ Spot patterns before incidents"]
    Claudia --> CL4["✅ Reduce radio dependency"]
    Claudia --> CL5["❌ Fear acting on stale data"]
    Claudia --> CL6["❌ Frustration with active monitoring"]
    Claudia --> CL7["❌ Fear accountability gaps"]

    Diego --> D1["✅ Receive alerts passively"]
    Diego --> D2["✅ Trust non-intrusive system"]
    Diego --> D3["❌ Fear distraction from noise"]
    Diego --> D4["❌ Fear responsibility creep"]

    Brigitte --> B1["✅ Know which coaches to prioritise"]
    Brigitte --> B2["✅ Calibrate stock to load"]
    Brigitte --> B3["❌ Fear running out of stock"]
    Brigitte --> B4["❌ Frustration with wasted prep"]

    Finn --> F1["✅ Deployment decisions on data"]
    Finn --> F2["✅ Identify capacity mismatches"]
    Finn --> F3["❌ Fear decisions on bad data"]
    Finn --> F4["❌ Frustration with manual extraction"]
```

---

## Strategic Focus Statement

**Priority 1 Goal:** Prove ÖBB staff effectiveness (Goal 2) — this is what triggers renewal and expansion

**Priority 1 User:** Conductor Conrad — his adoption is the pilot's single most important metric

**Priority 1 Driving Forces:**
1. Know the whole train at a glance (15/15 — HIGH)
2. Fear missing a safety-critical incident (15/15 — HIGH)
3. Fear alert overload / false positives (15/15 — HIGH)

**Design north star:** Build Conrad's trust in the first journey by showing him something true, useful, and noise-free. Everything else follows from that.
