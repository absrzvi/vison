# Story 1.5-4: Onboard Smoke Test

Status: done

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

### Review Findings (code-review 2026-05-21, Opus 4.7)

**Patches (7)**
- [x] [Review][Patch] P1 — Drop `-f` from `curl` in Steps 4 and 5; capture body for diagnostics; status-code case branch unreachable on 422/5xx with `-f` + `set -e` [scripts/smoke-test-onboard.sh]
- [x] [Review][Patch] P2 — Add `journey_id=SMOKE-TEST_001_20260521` filter to GET (or use larger limit); `?limit=1` without filter returns oldest event in DB — leftover volume state breaks assertion [scripts/smoke-test-onboard.sh]
- [x] [Review][Patch] P3 — `docker compose config --quiet` validates ALL services including bind mounts; stub `cameras.json` must exist (or validate only event-store) so CI doesn't fail on missing `./cameras.json` and `/opt/hailo/models/yolov8m.hef` [scripts/smoke-test-onboard.sh]
- [x] [Review][Patch] P4 — Add `docker compose version` to pre-flight; bare `docker` check doesn't catch missing compose v2 plugin [scripts/smoke-test-onboard.sh]
- [x] [Review][Patch] P5 — Add CWD guard: `cd "$(dirname "$0")/.."` so script works from any directory; `docker-compose.onboard.yml` is a relative path [scripts/smoke-test-onboard.sh]
- [x] [Review][Patch] P6 — Allow env override: `API_KEY="${EVENT_STORE_API_KEY:-onboard-dev-key}"` so production `.env` auto-load doesn't silently change the key [scripts/smoke-test-onboard.sh]
- [x] [Review][Patch] P7 — Verified and fixed executable bit to `100755` in git index (`git update-index --chmod=+x`) [scripts/smoke-test-onboard.sh]

**Deferred (5)**
- [x] [Review][Defer] D1 — AC4/AC5 spec text references `/api/v1/ingest` and `PASSENGER_BOARDED` which don't exist in the API; implementation correctly uses `POST /api/v1/events` + `OCCUPANCY_UPDATE` — spec text is stale; update ACs to match implementation [_bmad-output/implementation-artifacts/1-5-4-onboard-smoke-test.md]
- [x] [Review][Defer] D2 — `journey_id` in payload hardcodes today's date `20260521`; will silently rot if schema ever adds temporal date validation [scripts/smoke-test-onboard.sh]
- [x] [Review][Defer] D3 — No CI project-name isolation (`-p`); parallel CI jobs collide on port 8001 and `onboard_event_store_data` volume — deferred, PoC posture [scripts/smoke-test-onboard.sh]
- [x] [Review][Defer] D4 — No `jq` structured JSON assertion — `grep` is fragile vs error messages echoing vehicle_id back — deferred, acceptable for smoke test [scripts/smoke-test-onboard.sh]
- [x] [Review][Defer] D5 — Smoke test doesn't exercise event-store cursor pagination or event_type filters — deferred, out of scope for smoke test [scripts/smoke-test-onboard.sh]

## File List

- `scripts/.gitkeep` — NEW
- `scripts/smoke-test-onboard.sh` — NEW
- `_bmad-output/implementation-artifacts/1-5-4-onboard-smoke-test.md` — story file

## Change Log

- 2026-05-21: Story created and implemented; smoke test exits 0; status → review
- 2026-05-21: Code review (Opus 4.7): 7 patches applied (curl -f, GET filter, cameras.json stub, compose v2 check, CWD guard, API_KEY env, executable bit); smoke test exits 0; status → done

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

