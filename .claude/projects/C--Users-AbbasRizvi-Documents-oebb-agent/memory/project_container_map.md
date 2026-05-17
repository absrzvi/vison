---
name: Container map — edge vs landside
description: Definitive container placement decisions from 2026-05-17 party mode session
type: project
---

Onboard (SYS2): inference, vlan-pollers, event-store (built), sync-agent, conductor-app (nginx).
Landside: cloud-backend (built shell), control-centre-dashboard, diagnostics-llm.
No ws-gateway — removed. Edge WS is event-store:8001/ws. Control Centre uses REST poll 15s + SSE for alerts.
Sync-agent cadence: 15s cursor-based batch push.

**Why:** cellular unreliable (tunnels). Onboard stack must operate fully independently. Landside is analytics/visibility only. ws-gateway eliminated because Control Centre ambient payload is ~700B/train — polling trivially sufficient.

**How to apply:** use this as the authoritative container list when writing new stories or epics. Any new container must justify its placement against the offline-resilience principle.
