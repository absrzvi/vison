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

---

## Known Patterns & Traps

### Async callbacks — stale closure / state read

**React (JS) and Python asyncio share the same trap:** reading a mutable value inside an async callback captures the value at closure-creation time, not at call time.

**React pattern — `useRef` mirror:**
```js
// When state must be read synchronously inside an async useCallback,
// mirror it with a ref. All mutations go through a _setX wrapper.
const [pending, setPending] = useState(null);
const pendingRef = useRef(null);

const _setPending = useCallback((val) => {
  pendingRef.current = val;
  setPending(val);
}, []);

const handleAsync = useCallback(async () => {
  if (pendingRef.current !== null) return;  // synchronous read, no stale closure
  _setPending('loading');
  try {
    await doWork();
    _setPending(null);
  } catch {
    _setPending(null);
  }
}, [_setPending]);  // dep array: _setPending (stable), NOT pending (stale)
```

**Python asyncio pattern — capture before await:**
```python
# Read shared state before the first await; don't re-read after.
async def handle():
    current_state = context_state.value  # snapshot before any await
    await do_work(current_state)
    # Do NOT re-read context_state.value here — it may have changed.
```

**Rule:** If you need to read a value inside an async function after an `await`, either (a) snapshot it before the first `await`, or (b) use a ref/lock/queue to ensure the read is synchronous and unaffected by concurrent mutations.

---

## CSS Design Tokens — Control Centre

All component CSS must use these variables from `control-centre/src/styles/colors_and_type.css`. **Do not use hex literals or invent token names.**

### Severity ramp (ops surfaces)
| Token | Value | Use |
|---|---|---|
| `--obb-sev-critical` | `#FF3B3B` | Fire/smoke, urgent escalations, errors |
| `--obb-sev-high` | `#FF6B00` | Vandalism, hazards |
| `--obb-sev-medium` | `#F5A623` | Warnings, advisories |
| `--obb-sev-advisory` | `#4A9EFF` | Informational, review-required |
| `--obb-sev-normal` | `#22C55E` | Resolved, healthy, success |

> **Common mistake:** `--obb-sev-warning` does not exist — use `--obb-sev-medium`. `--obb-sev-danger` does not exist — use `--obb-sev-critical`.

### Surface ramp (dark ops theme)
| Token | Use |
|---|---|
| `--obb-surface-0` | Deepest background |
| `--obb-surface-1` | Primary panel background |
| `--obb-surface-2` | Secondary panel / inline panel |
| `--obb-surface-3` | Hover / selected row |
| `--obb-surface-4` | Elevated element (toast, modal) |
| `--obb-surface-5` | Highest elevation |

### Text on dark
| Token | Use |
|---|---|
| `--obb-text-on-dark-1` | Primary text |
| `--obb-text-on-dark-2` | Secondary text |
| `--obb-text-on-dark-3` | Tertiary / icons |
| `--obb-text-on-dark-4` | Muted / disabled |

### Border
| Token | Use |
|---|---|
| `--obb-border-dark` | Subtle dividers (6% white) |
| `--obb-border-bright` | Emphasized borders (10% white) |

### Brand & accent
| Token | Use |
|---|---|
| `--obb-blue-accent` | `#4080D0` — links, info chips |
| `--obb-blue-dim` | Hover wash on blue elements |

### Typography
| Token | Use |
|---|---|
| `--font-mono` | Monospace (train IDs, timestamps, ticket refs) |
| `--font-size-sm` | `12px` equivalent |

---

## ADR Reference — Key Decisions for E4 (Onboard Edge Pipeline)

### ADR-2: journey_id Key Scheme

**Format:** `{vehicle_id}_{trip_number}_{journey_start_date_YYYYMMDD}`

**Critical rule:** `journey_start_date` is recorded by `vlan-pollers` when `trip_number` is **first seen**, and held constant for the life of that journey. The event's own timestamp date is **never** used for the key — this prevents the midnight-crossing flip where a journey starting at 23:45 would change ID at 00:05.

**Required test** (`tests/unit/test_journey_id.py`):
- Trip starts 23:45, event arrives 00:05, same `trip_number`
- Assert: `journey_id` is identical for both events (does NOT change)

### ADR-18: Operational Telemetry Fusion Rules

Three cross-VLAN triggers handled by `fusion`:

**Trigger 1 — Door Release → Platform Camera Priority:**
VLAN 2/7 `doors_released = true` → `fusion` sends `STREAM_PRIORITY` command to `rtsp-ingest` for platform-facing cameras of that coach. Internal command only — never written to `event-store`.

**Trigger 2 — Coach Comfort Index:**
On station approach or significant occupancy change → `fusion` computes `COACH_COMFORT_INDEX` per coach:
- Input: camera-derived `occupied_seats` + `standing_count` + VLAN 6 `reserved_seats`
- Output event payload: `{ car_id, reserved_seats, occupied_seats, standing_count, comfort_score }` (float 0.0–1.0)

**Trigger 3 — GPS/HAFAS Proximity Alert Escalation:**
Train within 2 min of scheduled station → any `ALERT_RAISED` in that window gets `"priority": "escalated"` in payload. Flag set by `context_state.py` pushing `station_approach = true` to `fusion`; cleared when speed > 20 km/h after stop.

---

## E4 Dependencies — Confirmed

| Item | Status | Location |
|---|---|---|
| `MockAPCAdapter` | ✅ exists | `shared/src/oebb_shared/adapters/apc/mock.py` |
| `APCAdapter` Protocol | ✅ exists | `shared/src/oebb_shared/adapters/apc/adapter.py` |
| `OccupancyReading`, `DoorState` | ✅ exported | same module |
