# Container Map — Phase 1 (Control Centre Only)

Decided: 2026-05-17. Supersedes earlier draft that included conductor-app, diagnostics-llm, ws-gateway.

## Phase 1 — Active Build

```
[edge-ingest] → [event-store] → [sync-agent] → [cloud-backend] → [control-centre-dashboard]
```

| Container | Where | Port | Purpose | Status |
|---|---|---|---|---|
| `edge-ingest` | Onboard (SYS2) | — | Hailo-8 inference (occupancy, object detection) + VLAN pollers (APC VLAN 8, Stadler SNMP VLAN 7, PIS/FIS VLAN 3, reservations VLAN 6). Generates events, writes to event-store. | Build |
| `event-store` | Onboard (SYS2) | 8001 | FastAPI + SQLite WAL. Edge truth store + cursor sync point. | Built (Story 1-1) |
| `sync-agent` | Onboard (SYS2) | — | Cursor-based batch push edge→cloud. 15s cadence; flush immediately on alert-class events. | Build |
| `cloud-backend` | Landside | 8002 | FastAPI + PostgreSQL. `GET /api/v1/fleet/overview` (REST poll) + `GET /api/v1/alerts/stream` (SSE). | Shell built (Story 1-1) — needs fleet/SSE endpoints |
| `control-centre-dashboard` | Landside | 80 | React SPA. 15s REST poll (ambient fleet view) + SSE (alert push). | Build |

## Transport Channels

| Channel | Protocol | Endpoint | Cadence |
|---|---|---|---|
| Edge → cloud | REST batch (sync-agent push) | `POST /api/v1/events` on cloud-backend | 15s; immediate flush on ALARM_ACTIVE / ALERT_RAISED |
| cloud-backend → Control Centre (ambient) | REST poll | `GET /api/v1/fleet/overview` | 15s pull |
| cloud-backend → Control Centre (alerts) | SSE | `GET /api/v1/alerts/stream` | Push on ALARM_ACTIVE / ALERT_RAISED / ALERT_RESOLVED |

## Deferred to Phase 2

| Container | Reason |
|---|---|
| `conductor-app` | Onboard SPA — Phase 2 scope |
| Edge WebSocket (`event-store:8001/ws`) | Stubbed in event-store; activate in Phase 2 for conductor-app |

## Explicitly Out of Scope (Later Roadmap)

| Container | Reason |
|---|---|
| `diagnostics-llm` | Later roadmap stage |
| `ws-gateway` | Not needed — REST + SSE sufficient for Control Centre; no cloud WebSocket required |

## Open Story Notes

1. **sync-agent alert flush** — flush immediately on alert-class events, not just on 15s tick. Add to sync-agent story.
2. **SSE reconnect policy** — control-centre frontend: exponential backoff + max retry cap. Add to dashboard story.
3. **sync-agent failure mode** — SQLite WAL retention window + cursor behaviour if cloud-backend unreachable >N minutes. Add to sync-agent story.
