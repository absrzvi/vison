#!/usr/bin/env bash
# smoke-test-onboard.sh — CI-safe onboard stack smoke test (event-store only).
# Does NOT require Hailo hardware, real RTSP cameras, or cameras.json.
#
# Usage (from any directory):
#   bash scripts/smoke-test-onboard.sh
#   ./scripts/smoke-test-onboard.sh
#
# Exit 0 on success, non-zero on any failure.
set -euo pipefail

# Resolve repo root from script location so this works regardless of CWD.
REPO_ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$REPO_ROOT"

COMPOSE_FILE="docker-compose.onboard.yml"
EVENT_STORE_URL="http://localhost:8001"
# Allow env override so a production .env that sets EVENT_STORE_API_KEY doesn't silently
# break auth (the hardcoded default matches docker-compose.onboard.yml's dev placeholder).
API_KEY="${EVENT_STORE_API_KEY:-onboard-dev-key}"
HEALTH_TIMEOUT=30
HEALTH_INTERVAL=3

# ── helpers ──────────────────────────────────────────────────────────────────

log() { echo "[smoke] $*"; }
fail() { echo "[smoke] ERROR: $*" >&2; exit 1; }

# ── pre-flight ───────────────────────────────────────────────────────────────

log "Pre-flight: checking required tools"
command -v docker >/dev/null 2>&1 || fail "docker not found in PATH"
command -v curl   >/dev/null 2>&1 || fail "curl not found in PATH"
# Confirm docker compose v2 plugin is available (not just docker v1 daemon).
docker compose version >/dev/null 2>&1 || fail "docker compose (v2 plugin) not available; install via 'apt install docker-compose-plugin'"
log "  docker: $(docker --version | head -1)"
log "  curl: $(curl --version | head -1)"
log "  compose: $(docker compose version --short 2>/dev/null || echo 'unknown')"

# Ensure compose file exists before proceeding.
[ -f "$COMPOSE_FILE" ] || fail "$COMPOSE_FILE not found — run from monorepo root or check REPO_ROOT"

# Create a stub cameras.json if absent — only needed for compose config validation
# (rtsp-ingest and inference bind-mount it, but are NOT started by this smoke test).
CREATED_CAMERAS_JSON=0
if [ ! -f cameras.json ]; then
  echo '{"cameras":[]}' > cameras.json
  CREATED_CAMERAS_JSON=1
  log "  created stub cameras.json for compose config validation"
fi

# ── cleanup trap ─────────────────────────────────────────────────────────────

cleanup() {
  log "Cleanup: docker compose down -v"
  docker compose -f "$COMPOSE_FILE" down -v --remove-orphans --timeout 10 2>/dev/null || true
  # Remove stub cameras.json if we created it.
  if [ "$CREATED_CAMERAS_JSON" -eq 1 ] && [ -f cameras.json ]; then
    rm -f cameras.json
  fi
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
# Drop -f so HTTP error bodies are captured rather than silently swallowed by curl.
POST_BODY=$(curl -s -o /tmp/smoke-post-body.txt -w "%{http_code}" \
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
HTTP_STATUS="$POST_BODY"
case "$HTTP_STATUS" in
  200|201) log "  POST returned HTTP $HTTP_STATUS — OK" ;;
  401)     fail "POST returned 401 Unauthorized — check API key match between compose and smoke test" ;;
  422)     fail "POST returned 422 Unprocessable — schema validation failed: $(cat /tmp/smoke-post-body.txt)" ;;
  *)       fail "POST returned unexpected HTTP $HTTP_STATUS — body: $(cat /tmp/smoke-post-body.txt)" ;;
esac

# ── step 5: GET events and verify ────────────────────────────────────────────

log "Step 5: GET /api/v1/events filtered by journey_id and verify SMOKE-TEST event"
# Drop -f so non-2xx errors surface their body. Filter by journey_id to avoid
# false positives from leftover events in a non-freshly-wiped volume.
RESPONSE=$(curl -s \
  -H "X-API-Key: ${API_KEY}" \
  "${EVENT_STORE_URL}/api/v1/events?journey_id=SMOKE-TEST_001_20260521&limit=1"
)
# journey_id filter raises JOURNEY_NOT_FOUND if journey table has no record — use
# unfiltered GET as fallback to verify the event exists regardless.
if echo "$RESPONSE" | grep -q "JOURNEY_NOT_FOUND"; then
  RESPONSE=$(curl -s \
    -H "X-API-Key: ${API_KEY}" \
    "${EVENT_STORE_URL}/api/v1/events?limit=10"
  )
fi
if ! echo "$RESPONSE" | grep -q "SMOKE-TEST"; then
  fail "GET response does not contain SMOKE-TEST — body: $RESPONSE"
fi
log "  GET returned SMOKE-TEST event — OK"

# ── done ─────────────────────────────────────────────────────────────────────

log "OK — onboard smoke test passed"
# trap EXIT handles docker compose down -v and cameras.json cleanup
