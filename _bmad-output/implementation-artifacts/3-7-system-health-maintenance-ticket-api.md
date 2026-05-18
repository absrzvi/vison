# Story 3.7: System Health Maintenance Ticket API

Status: ready-for-dev

## Story

As a Fleet Maintenance Manager,
I want maintenance tickets raised from the System Health panel to get server-generated reference numbers,
so that ticket IDs are stable, unique, and traceable in the maintenance system rather than being random client-side strings.

## Acceptance Criteria

**AC1 — POST on confirm:**
Given the System Health inline detail panel is open for a train with issues,
When the operator clicks "Raise Maintenance Ticket" and confirms,
Then `POST /api/v1/maintenance/tickets` is called with body `{ train_id, issue_summary, raised_by: "<operator_id>" }` and `X-API-Key` header; the request is sent before the confirmation UI updates.

**AC2 — 201 success path:**
Given the API returns HTTP 201 with `{ ticket_id: "REF#XXXXX", created_at: "<ISO-8601>" }`,
When the response is received,
Then the panel footer updates to the "raised" state showing the server-returned `ticket_id` in monospace; the toast shows "Ticket raised — {ticket_id} · {train_id}" and auto-dismisses after 4s.

**AC3 — Error path:**
Given the API returns HTTP 4xx or 5xx,
When the error is received,
Then the confirmation UI reverts to the default "Raise Maintenance Ticket" button state; a toast error "Ticket creation failed — please try again" appears; no fake ticket ID is shown.

**AC4 — ESC cancels pending confirm:**
Given the operator presses Escape during the two-step confirmation,
When Escape is detected,
Then the pending confirmation state is cancelled; no API call is made; existing prototype behaviour preserved.

**AC5 — MAINTENANCE_APP_ENABLED flag:**
Given the `MAINTENANCE_APP_ENABLED` flag,
When it is `false` (current default),
Then the Maintenance App CTA (`sh-panel-cta`) remains hidden; the flag value is read from `VITE_MAINTENANCE_APP_ENABLED` env var; no hardcoded `false` in component logic.

**AC6 — Remove Math.random():**
`Math.random()` is removed entirely from `SystemHealth.jsx` — no client-side ticket ID generation remains.

**AC7 — Backend endpoint:**
`POST /api/v1/maintenance/tickets` must exist in the cloud backend, return 201 with `{ ticket_id, created_at }`, accept `{ train_id, issue_summary, raised_by }`, and require `X-API-Key` auth.

## Tasks / Subtasks

- [ ] **T1** Create `control-centre/src/api/maintenance.js` (AC1, AC2, AC3)
  - [ ] T1.1 Follow the `escalations.js` pattern: shared `_post` helper with `X-API-Key` and 10s timeout
  - [ ] T1.2 Export `raiseMaintenanceTicket(trainId, issueSummary, raisedBy)` → `POST /api/v1/maintenance/tickets`
  - [ ] T1.3 On non-ok response throw `Error` with `.status` set (same pattern as escalations.js)

- [ ] **T2** Refactor `confirmRaiseTicket` in `SystemHealth.jsx` to call the API (AC1, AC2, AC3, AC6)
  - [ ] T2.1 Import `raiseMaintenanceTicket` from `../../api/maintenance`
  - [ ] T2.2 Remove `Math.random()` ticket ID generation entirely
  - [ ] T2.3 Make `confirmRaiseTicket` async; call `raiseMaintenanceTicket`, await response
  - [ ] T2.4 On success: set `ticketRaisedIds`, set `ticketRefs[trainId] = ticket_id` (from server), clear `ticketPending`, show toast "Ticket raised — {ticket_id} · {train_id}"
  - [ ] T2.5 On error: revert `ticketPending` to null; show error toast "Ticket creation failed — please try again"; do NOT populate `ticketRefs`
  - [ ] T2.6 Add `[ticketPending]` loading state to prevent double-submit (set before fetch, clear on resolve/reject)

- [ ] **T3** Wire `VITE_MAINTENANCE_APP_ENABLED` env flag (AC5)
  - [ ] T3.1 In `SystemHealth.jsx` read `const maintenanceAppEnabled = import.meta.env.VITE_MAINTENANCE_APP_ENABLED === 'true'`
  - [ ] T3.2 Conditionally render `sh-panel-cta` only when `maintenanceAppEnabled === true`
  - [ ] T3.3 Remove any hardcoded `false` in component logic for that CTA

- [ ] **T4** Create backend route `cloud-backend/src/cloud_backend/routes/maintenance.py` (AC7)
  - [ ] T4.1 `POST /api/v1/maintenance/tickets` with `Security(require_api_key)`
  - [ ] T4.2 Accept request body: `{ train_id: str, issue_summary: str, raised_by: str }`
  - [ ] T4.3 Generate server-side `ticket_id`: `f"REF#{uuid4().hex[:5].upper()}"` (deterministic prefix, no Math.random)
  - [ ] T4.4 Return HTTP 201 with `{ ticket_id, created_at: datetime.now(UTC).isoformat() }`
  - [ ] T4.5 Register router in `cloud-backend/src/cloud_backend/main.py`

- [ ] **T5** Write tests
  - [ ] T5.1 `control-centre/src/api/__tests__/maintenance.test.js` — follow escalations.test.js pattern; test: 201 → returns `{ ticket_id, created_at }`; 4xx → throws Error with `.status`; 5xx → throws Error with `.status`; request body contains `train_id`, `issue_summary`, `raised_by`; `X-API-Key` header sent
  - [ ] T5.2 `cloud-backend/tests/unit/test_maintenance_api.py` — test: 401 without key; 201 with valid key + body; `ticket_id` matches `REF#[A-F0-9]{5}` pattern; `created_at` is ISO-8601

- [ ] **T6** Run full test suite and lint; confirm no regressions

## Dev Notes

### Current state of `confirmRaiseTicket` — what MUST change

`SystemHealth.jsx` lines 164–170 (current):

```js
const confirmRaiseTicket = useCallback((trainId) => {
  const ref = `REF#${Math.floor(10000 + Math.random() * 90000)}`;
  setTicketRaisedIds(prev => new Set([...prev, trainId]));
  setTicketRefs(prev => ({ ...prev, [trainId]: ref }));
  setTicketPending(null);
  setTicketToast({ trainId, ref });
  clearTimeout(toastTimerRef.current);
  toastTimerRef.current = setTimeout(() => setTicketToast(null), 4000);
}, []);
```

**This entire function must be replaced.** The `Math.random()` call is the core problem. The new version must be async and call the API:

```js
const confirmRaiseTicket = useCallback(async (trainId) => {
  // Prevent double-submit — mark loading immediately
  setTicketPending(`${trainId}--loading`);
  try {
    const { ticket_id } = await raiseMaintenanceTicket(
      trainId,
      `Fleet health issue reported for ${trainId}`,  // issue_summary
      API_KEY_VALUE,   // raised_by — see note on operator ID below
    );
    setTicketRaisedIds(prev => new Set([...prev, trainId]));
    setTicketRefs(prev => ({ ...prev, [trainId]: ticket_id }));
    setTicketPending(null);
    setTicketToast({ trainId, ref: ticket_id });
    clearTimeout(toastTimerRef.current);
    toastTimerRef.current = setTimeout(() => setTicketToast(null), 4000);
  } catch {
    setTicketPending(null);
    setTicketToast({ trainId, ref: null, error: true });
    clearTimeout(toastTimerRef.current);
    toastTimerRef.current = setTimeout(() => setTicketToast(null), 4000);
  }
}, []);
```

### `raised_by` / operator ID

The epics spec says `raised_by: "<operator_id>"`. In the current system, `operator_id` is the API key value (same pattern as preferences.py: `operator_id` is derived server-side from `X-API-Key`). The backend already derives identity from the key — so on the **backend** side `raised_by` can be ignored or derived from the key. On the **frontend**, pass `import.meta.env.VITE_API_KEY ?? 'dev-key'` as `raised_by`. Do not introduce a new context — keep it simple. The backend can store it as-is; no operator session table is touched.

### Toast error state

Currently `ticketToast` is `{ trainId, ref }`. The error case needs `{ trainId, ref: null, error: true }`. The toast render in SystemHealth.jsx (lines 501–505):

```jsx
{ticketToast && (
  <div className="sh-toast">
    Ticket raised — {ticketToast.ref} · {ticketToast.trainId}
  </div>
)}
```

Must branch on `ticketToast.error`:

```jsx
{ticketToast && (
  <div className={`sh-toast${ticketToast.error ? ' sh-toast--error' : ''}`}>
    {ticketToast.error
      ? 'Ticket creation failed — please try again'
      : `Ticket raised — ${ticketToast.ref} · ${ticketToast.trainId}`}
  </div>
)}
```

Add `.sh-toast--error` to `SystemHealth.css` (red/danger tone, matching `--obb-sev-high` token).

### Pending state rendering

`ticketPending` is currently `trainId | null`. With the loading pattern above, when a request is in-flight the state will be `"${trainId}--loading"`. The `renderFooter` function checks `const isPending = ticketPending === trainId`. This check becomes `const isPending = ticketPending === trainId || ticketPending === \`${trainId}--loading\``.

Add a `const isLoading = ticketPending === \`${trainId}--loading\`` to show a disabled "Confirming…" button state during the fetch:

```jsx
if (isLoading) {
  return (
    <div className="sh-panel__footer sh-panel__footer--confirm">
      <span className="sh-panel__confirm-label">Raising ticket for {trainId}…</span>
    </div>
  );
}
```

No spinner required — text is sufficient.

### `maintenance.js` API module pattern

Follow `escalations.js` exactly. The module must:
1. Import nothing from React — plain JS module
2. Use `import.meta.env.VITE_API_URL` and `import.meta.env.VITE_API_KEY`
3. 10s timeout via `AbortSignal.timeout` with fallback
4. POST returns parsed JSON; non-ok throws `Error` with `.status = res.status`

```js
// control-centre/src/api/maintenance.js
const API_BASE = import.meta.env.VITE_API_URL ?? '';
const API_KEY  = import.meta.env.VITE_API_KEY  ?? '';

const FETCH_TIMEOUT_MS = 10000;

function _timeoutSignal(ms) {
  if (typeof AbortSignal.timeout === 'function') return AbortSignal.timeout(ms);
  const ctrl = new AbortController();
  setTimeout(() => ctrl.abort(), ms);
  return ctrl.signal;
}

export async function raiseMaintenanceTicket(trainId, issueSummary, raisedBy) {
  const res = await fetch(`${API_BASE}/api/v1/maintenance/tickets`, {
    method: 'POST',
    headers: {
      'Content-Type': 'application/json',
      'X-API-Key': API_KEY,
    },
    body: JSON.stringify({ train_id: trainId, issue_summary: issueSummary, raised_by: raisedBy }),
    signal: _timeoutSignal(FETCH_TIMEOUT_MS),
  });
  if (!res.ok) {
    const err = new Error(`API error ${res.status}`);
    err.status = res.status;
    throw err;
  }
  return res.json();
}
```

### Backend route pattern

Follow `cloud-backend/src/cloud_backend/routes/preferences.py` for auth wiring and `routes/analytics.py` for router registration style.

```python
# cloud-backend/src/cloud_backend/routes/maintenance.py
from __future__ import annotations

from datetime import UTC, datetime
from uuid import uuid4

import structlog
from fastapi import APIRouter, Security
from pydantic import BaseModel

from ..api.auth import require_api_key

log = structlog.get_logger()

router = APIRouter(
    prefix="/api/v1/maintenance",
    dependencies=[Security(require_api_key)],
)


class TicketRequest(BaseModel):
    train_id: str
    issue_summary: str
    raised_by: str


class TicketResponse(BaseModel):
    ticket_id: str
    created_at: str


@router.post("/tickets", response_model=TicketResponse, status_code=201)
async def raise_ticket(body: TicketRequest) -> TicketResponse:
    ticket_id = f"REF#{uuid4().hex[:5].upper()}"
    created_at = datetime.now(UTC).isoformat()
    log.info("maintenance_ticket_raised", ticket_id=ticket_id, train_id=body.train_id, raised_by=body.raised_by)
    return TicketResponse(ticket_id=ticket_id, created_at=created_at)
```

Register in `main.py`:
```python
from .routes.maintenance import router as maintenance_router
# ...
app.include_router(maintenance_router)
```

**No database write required for PoC.** Ticket is logged + returned; persistence deferred. If the team wants persistence later, that is a separate story.

### `VITE_MAINTENANCE_APP_ENABLED` — current state

The `sh-panel-cta` div is not currently rendered in `SystemHealth.jsx` (grep returns no match). The epics AC says to read the flag from `VITE_MAINTENANCE_APP_ENABLED` — this implies the CTA was planned but not yet added. T3 only needs to ensure: if the CTA is absent, it must NOT be added unconditionally. Any future CTA must be gated. No new UI work needed if CTA does not exist — just ensure no hardcoded `false` if a CTA element exists.

**Check:** `grep -n "sh-panel-cta\|maintenance.*app\|maintenanceApp" SystemHealth.jsx` — if zero matches, T3 is a no-op verification task only.

### Test approach — frontend (`maintenance.test.js`)

Follow `control-centre/src/api/__tests__/escalations.test.js` exactly — `// @vitest-environment node`, mock `globalThis.fetch`, test success and error paths. Extract tests from the module-level function, no React import.

### Test approach — backend (`test_maintenance_api.py`)

Follow `tests/unit/test_rest_api.py` pattern: `TestClient(app)`, override `get_db` if needed (this endpoint does NOT need a DB so no override required), check 401 without key, check 201 response shape.

```python
import re
from cloud_backend.main import app
from cloud_backend.config import get_settings
from fastapi.testclient import TestClient

_HEADERS = {"X-API-Key": get_settings().api_key}

def test_no_api_key_returns_401():
    with TestClient(app) as client:
        r = client.post("/api/v1/maintenance/tickets", json={...})
    assert r.status_code == 401

def test_raise_ticket_201():
    with TestClient(app) as client:
        r = client.post("/api/v1/maintenance/tickets",
                        json={"train_id": "4011", "issue_summary": "CCTV degraded", "raised_by": "op-1"},
                        headers=_HEADERS)
    assert r.status_code == 201
    body = r.json()
    assert re.match(r"REF#[A-F0-9]{5}", body["ticket_id"])
    assert "created_at" in body
```

### Files to change

| File | Change |
|---|---|
| `control-centre/src/api/maintenance.js` | NEW — `raiseMaintenanceTicket` export |
| `control-centre/src/api/__tests__/maintenance.test.js` | NEW — unit tests for API module |
| `control-centre/src/components/health/SystemHealth.jsx` | UPDATE — remove Math.random, call API, loading state, error toast, MAINTENANCE_APP_ENABLED flag |
| `control-centre/src/components/health/SystemHealth.css` | UPDATE — add `.sh-toast--error` style |
| `cloud-backend/src/cloud_backend/routes/maintenance.py` | NEW — POST /api/v1/maintenance/tickets |
| `cloud-backend/src/cloud_backend/main.py` | UPDATE — register maintenance_router |
| `cloud-backend/tests/unit/test_maintenance_api.py` | NEW — 401 and 201 tests |

### What NOT to change

- Existing `confirmRaiseTicket` call sites in `renderFooter` — only the function body changes; callers stay the same.
- `ticketRaisedIds`, `ticketRefs`, `ticketPending`, `ticketToast` state names — all preserved.
- `toastTimerRef` and 4s auto-dismiss logic — preserved.
- ESC handler (lines 132–141) — already cancels `ticketPending`; the new loading state `"${trainId}--loading"` must also be caught: `if (ticketPending) { setTicketPending(null); return; }` already does this since any truthy `ticketPending` value triggers the guard.
- `getSystemHealth` in `api/health.js` — not touched.
- PostgreSQL schema — no migration needed; no DB writes for PoC.
- All other analytics and fleet routes — no changes.

### Previous story intelligence (from E3-S6)

- Test file uses `// @vitest-environment node` — maintain this for `maintenance.test.js`.
- ESLint `react-refresh/only-export-components` fires for non-component exports from component files — API modules live in `src/api/`, not component files; no issue.
- `react-hooks/exhaustive-deps` suppression pattern for `useMemo` with tick dep — unchanged.
- `useCallback` with async: the existing ESLint config does not flag async callbacks; safe to use.
- `AbortController` already in `fetchHealth` (lines 106–118) — do not add another one to `confirmRaiseTicket`; the 10s timeout signal in `maintenance.js` handles it.

## File List

- `control-centre/src/api/maintenance.js` (NEW)
- `control-centre/src/api/__tests__/maintenance.test.js` (NEW)
- `control-centre/src/components/health/SystemHealth.jsx` (UPDATE — remove Math.random, API call, loading state, error toast, env flag)
- `control-centre/src/components/health/SystemHealth.css` (UPDATE — `.sh-toast--error`)
- `cloud-backend/src/cloud_backend/routes/maintenance.py` (NEW)
- `cloud-backend/src/cloud_backend/main.py` (UPDATE — register maintenance_router)
- `cloud-backend/tests/unit/test_maintenance_api.py` (NEW)

## Dev Agent Record

### Pre-Flight
- Assumptions: No DB persistence required for PoC — log + return is sufficient. `raised_by` is passed as the VITE_API_KEY value (same pattern as operator_id derivation in preferences). `sh-panel-cta` does not currently exist in SystemHealth.jsx — T3 is verification only. Backend has no existing maintenance router.
- Open Questions: None.
- Simplicity Check: 2 new files (frontend module + backend route), 2 new test files, 1 component update (remove Math.random + wire async), 1 CSS addition, 1 main.py router registration.

## Change Log

- 2026-05-19: Story created — system health maintenance ticket API
