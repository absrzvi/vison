# Story 1.5-4: Onboard Smoke Test

Status: review

## Story

As a platform engineer,
I want a CI-safe smoke test script that verifies the onboard `event-store` container builds and starts healthy with no external dependencies,
so that every push can confirm the containerisation layer works without requiring Hailo hardware.

## Acceptance Criteria

1. **`scripts/smoke-test-onboard.sh` exists** at the monorepo root and is executable (`chmod +x`).

2. **Smoke test brings up only `event-store`** using `docker compose -f docker-compose.onboard.yml up -d event-store` — not rtsp-ingest or inference (both require Hailo hardware or real RTSP streams).

3. **Smoke test waits for event-store to become healthy** by polling `GET /health/ready` on `http://localhost:8001` up to 30 seconds (3s interval × 10 attempts), failing with a non-zero exit code if the timeout is exceeded.

4. **Smoke test posts a test event** via `POST /api/v1/ingest` with a well-formed `PASSENGER_BOARDED` event envelope and the `X-API-Key: onboard-dev-key` header, and asserts HTTP 200 or 201.

5. **Smoke test queries the event** via `GET /api/v1/events?vehicle_id=SMOKE-TEST&limit=1` with the API key header and asserts HTTP 200 and that the response body contains `SMOKE-TEST`.

6. **Smoke test tears down cleanly** — `docker compose -f docker-compose.onboard.yml down -v` runs in a `trap` so containers are removed even on failure.

7. **Smoke test is idempotent** — running it twice in a row produces the same result (named volume is removed by `down -v`, so no leftover state).

8. **`scripts/` directory** is created with `.gitkeep` if it doesn't already exist so the path is tracked.

9. **YAML config check** — the script includes a `docker compose -f docker-compose.onboard.yml config --quiet` step that exits non-zero if the compose file is invalid, before attempting to bring up any service.

10. **Smoke test exits 0** on a dev machine with Docker installed (no Hailo hardware required); output is terse — one line per step.

## Failure Scenarios

- **event-store fails to reach healthy within 30s:** Script exits 1 with a clear message (`ERROR: event-store did not become healthy within 30s`), tears down via trap.
- **POST /api/v1/ingest returns 401:** API key mismatch between compose env and smoke-test header — script exits 1 with HTTP status in the error message.

## Dev Notes

### Scope

Only `event-store` is testable without Hailo hardware. rtsp-ingest requires a real cameras.json and RTSP streams; inference requires `/dev/hailo0`. The smoke test intentionally covers only the dependency root.

### cameras.json stub

`docker-compose.onboard.yml` bind-mounts `./cameras.json` into rtsp-ingest and inference — but since we only bring up `event-store`, this file is NOT required for the smoke test. No stub cameras.json needed.

### event-store API key

The compose file sets `EVENT_STORE_API_KEY=onboard-dev-key`. The smoke test must send `X-API-Key: onboard-dev-key` in all requests.

### Event payload

Use the minimal valid `PASSENGER_BOARDED` envelope from the shared schema. Minimal valid payload:

```json
{
  "event_type": "PASSENGER_BOARDED",
  "vehicle_id": "SMOKE-TEST",
  "source_service": "smoke-test",
  "payload": {"door_id": "D1", "coach_id": "C1", "count": 1}
}
```

### Ports

event-store is exposed on host port 8001 (matching the compose file).

### Curl availability

Use `curl` for HTTP calls — it is universally available in CI and dev Linux environments. Fail fast if curl is not found.

### Permission Tier

| Action | Tier |
|---|---|
| Write `scripts/smoke-test-onboard.sh` | 2 — local file edit |
| `docker compose up/down` | 3 — shell (Docker daemon) |
| `curl` HTTP calls | 3 — shell |

Tier 3 actions require explicit sign-off. This story is approved for Tier 3 execution in the dev workflow.

## Tasks

- [x] Create `scripts/` directory entry
  - [x] Create `scripts/.gitkeep` so the directory is tracked
- [x] Write `scripts/smoke-test-onboard.sh`
  - [x] Shebang + `set -euo pipefail`
  - [x] Pre-flight: check `docker` and `curl` are available
  - [x] Step 1: `docker compose config --quiet` validates compose YAML
  - [x] Step 2: register trap for `docker compose down -v`
  - [x] Step 3: `docker compose up -d event-store`
  - [x] Step 4: poll `/health/ready` up to 30s, exit 1 on timeout
  - [x] Step 5: POST test event, assert 200/201
  - [x] Step 6: GET events, assert 200 + body contains SMOKE-TEST
  - [x] Step 7: print `OK` and exit 0 (trap handles cleanup)
- [x] Make script executable (`chmod +x scripts/smoke-test-onboard.sh`)
- [x] Validate: `docker compose -f docker-compose.onboard.yml config --quiet` exits 0 (confirmed)
- [x] Run the smoke test and confirm exit 0

## File List

- `scripts/.gitkeep` — NEW
- `scripts/smoke-test-onboard.sh` — NEW
- `_bmad-output/implementation-artifacts/1-5-4-onboard-smoke-test.md` — story file

## Change Log

- 2026-05-21: Story created and implemented; smoke test exits 0; status → review

## Dev Agent Record

### Implementation Plan

- Write a bash smoke test that exercises only `event-store` (no Hailo hardware required)
- Use `docker compose up -d event-store` + health poll + curl POST/GET + cleanup trap
- Script is CI-safe: pure bash + docker + curl, no Python or extra deps

### Debug Log

- Initial attempt used `/api/v1/ingest` (non-existent) → changed to `POST /api/v1/events`
- Initial payload used `source_service` (not a schema field) and `PASSENGER_BOARDED` (not an EventType) → fixed to `source: inference`, `severity: info`, `event_type: OCCUPANCY_UPDATE` with correct `OccupancyUpdatePayload` fields
- Initial GET used `?journey_id=...` filter → raises `JourneyNotFoundError` because journeys table is populated separately from events table; changed to `GET /api/v1/events?limit=1` (no journey filter)

### Completion Notes

- `scripts/smoke-test-onboard.sh`: 7-step bash script (pre-flight → compose validate → up event-store → health poll → POST event → GET verify → cleanup trap)
- Event payload: `OCCUPANCY_UPDATE` from `source: inference` with `severity: info` — fully schema-valid
- POST returns HTTP 201; GET returns `SMOKE-TEST` in response body
- Smoke test is idempotent: `down -v` in trap removes the named volume so no state leaks between runs
- Confirmed: smoke test exits 0 on dev machine with Docker 29.4.0, no Hailo hardware

