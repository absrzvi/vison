# Container Map — Decided 2026-05-17

## Onboard (SYS2 — Edge)

| Container | Port | Purpose | Status |
|---|---|---|---|
| `inference` | — | Hailo-8 model serving — occupancy, object detection, event generation | Build |
| `vlan-pollers` | — | APC (VLAN 8), Stadler SNMP (VLAN 7), PIS/FIS (VLAN 3), reservations (VLAN 6) | Build |
| `event-store` | 8001 | FastAPI + SQLite WAL. Edge truth store. WebSocket for conductor-app + driver-display | Built (Story 1-1) |
| `sync-agent` | — | Cursor-based batch push edge→cloud, 15s cadence | Build |
| `conductor-app` | 80 | Static SPA + local API, served via edge nginx. Must work offline (tunnels) | Build |

## Landside (Cloud)

| Container | Port | Purpose | Status |
|---|---|---|---|
| `cloud-backend` | 8002 | FastAPI + PostgreSQL. Fleet overview endpoint + SSE alerts endpoint | Shell built (Story 1-1) — needs fleet/SSE |
| `control-centre-dashboard` | 80 | React SPA. REST poll 15s (ambient) + SSE alert stream | Build |
| `diagnostics-llm` | — | LLM fault explanation. Resource-heavy, landside only (Hailo-8 is vision-only) | Build |

## Transport Channels

| Channel | Protocol | Endpoint | Cadence |
|---|---|---|---|
| Edge → conductor-app / driver-display | WebSocket | `event-store:8001/ws` | Real-time, offline-tolerant |
| Edge → cloud | REST batch (sync-agent push) | `cloud-backend POST /api/v1/events` | 15s |
| cloud-backend → Control Centre (ambient) | REST poll | `GET /api/v1/fleet/overview` | 15s pull |
| cloud-backend → Control Centre (alerts) | SSE | `GET /api/v1/alerts/stream` | Push on ALARM_ACTIVE / ALERT_RAISED / ALERT_RESOLVED |

## Explicitly Removed

- **ws-gateway** — not needed. Edge WebSocket is built into event-store. No cloud WebSocket required; REST + SSE sufficient for Control Centre operator workflow.

## Open Story Notes (not blockers)

1. **SSE reconnect policy** — control-centre frontend: exponential backoff + max retry cap. Add to dashboard story.
2. **sync-agent failure mode** — define SQLite WAL retention window + cursor behaviour if cloud-backend unreachable >N minutes. Add to sync-agent story.
3. **conductor-app offline boundary** — explicit mapping of local-only vs cloud-proxied API calls before conductor-app story is scoped.
