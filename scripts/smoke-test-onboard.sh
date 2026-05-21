#!/usr/bin/env bash
# smoke-test-onboard.sh — CI-safe onboard stack smoke test (event-store only).
# Does NOT require Hailo hardware, real RTSP cameras, or cameras.json.
#
# Usage:
#   cd <monorepo-root>
#   bash scripts/smoke-test-onboard.sh
#
# Exit 0 on success, non-zero on any failure.
set -euo pipefail

COMPOSE_FILE="docker-compose.onboard.yml"
EVENT_STORE_URL="http://localhost:8001"
API_KEY="onboard-dev-key"
HEALTH_TIMEOUT=30
HEALTH_INTERVAL=3

# ── helpers ──────────────────────────────────────────────────────────────────

log() { echo "[smoke] $*"; }
fail() { echo "[smoke] ERROR: $*" >&2; exit 1; }

# ── pre-flight ───────────────────────────────────────────────────────────────

log "Pre-flight: checking required tools"
command -v docker >/dev/null 2>&1 || fail "docker not found in PATH"
command -v curl   >/dev/null 2>&1 || fail "curl not found in PATH"
log "  docker: $(docker --version | head -1)"
log "  curl: $(curl --version | head -1)"

# ── cleanup trap ─────────────────────────────────────────────────────────────

cleanup() {
  log "Cleanup: docker compose down -v"
  docker compose -f "$COMPOSE_FILE" down -v --remove-orphans --timeout 10 2>/dev/null || true
}
trap cleanup EXIT

# ── step 1: validate compose YAML ────────────────────────────────────────────

log "Step 1: Validating $COMPOSE_FILE"
docker compose -f "$COMPOSE_FILE" config --quiet
log "  compose YAML valid"

# ── step 2: bring up event-store only ────────────────────────────────────────

log "Step 2: Starting event-store (no Hailo hardware required)"
docker compose -f "$COMPOSE_FILE" up -d --build event-store
log "  event-store container started"

# ── step 3: wait for /health/ready ───────────────────────────────────────────

log "Step 3: Waiting for event-store /health/ready (timeout ${HEALTH_TIMEOUT}s)"
elapsed=0
until curl -sf "${EVENT_STORE_URL}/health/ready" -o /dev/null; do
  if [ "$elapsed" -ge "$HEALTH_TIMEOUT" ]; then
    fail "event-store did not become healthy within ${HEALTH_TIMEOUT}s"
  fi
  sleep "$HEALTH_INTERVAL"
  elapsed=$((elapsed + HEALTH_INTERVAL))
  log "  waiting... ${elapsed}s elapsed"
done
log "  event-store is healthy"

# ── step 4: POST a test event ─────────────────────────────────────────────────

log "Step 4: POST OCCUPANCY_UPDATE event"
HTTP_STATUS=$(curl -sf -o /dev/null -w "%{http_code}" \
  -X POST "${EVENT_STORE_URL}/api/v1/events" \
  -H "Content-Type: application/json" \
  -H "X-API-Key: ${API_KEY}" \
  -d '{
    "event_type": "OCCUPANCY_UPDATE",
    "vehicle_id": "SMOKE-TEST",
    "journey_id": "SMOKE-TEST_001_20260521",
    "source": "inference",
    "severity": "info",
    "payload": {
      "car_id": "C1",
      "occupancy_count": 5,
      "occupancy_pct": 0.25,
      "capacity": 20,
      "service_tier": "T1"
    }
  }'
)
case "$HTTP_STATUS" in
  200|201) log "  POST returned HTTP $HTTP_STATUS — OK" ;;
  401)     fail "POST returned 401 Unauthorized — check API key match between compose and smoke test" ;;
  *)       fail "POST returned unexpected HTTP $HTTP_STATUS" ;;
esac

# ── step 5: GET events and verify ────────────────────────────────────────────

log "Step 5: GET /api/v1/events and verify SMOKE-TEST event present"
RESPONSE=$(curl -sf \
  -H "X-API-Key: ${API_KEY}" \
  "${EVENT_STORE_URL}/api/v1/events?limit=1"
)
if ! echo "$RESPONSE" | grep -q "SMOKE-TEST"; then
  fail "GET response does not contain SMOKE-TEST — unexpected body: $RESPONSE"
fi
log "  GET returned SMOKE-TEST event — OK"

# ── done ─────────────────────────────────────────────────────────────────────

log "OK — onboard smoke test passed"
# trap EXIT handles docker compose down -v
