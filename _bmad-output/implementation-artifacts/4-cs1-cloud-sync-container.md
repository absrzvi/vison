# Story 4.CS1: `cloud-sync` Container — Onboard MQTT Gateway

Status: ready-for-dev

<!-- Created 2026-05-20 by bmad-create-story. NEW container that bridges
onboard event-store ↔ landside Mosquitto broker. Adds a small companion HTTP
endpoint on event-store (`POST /api/v1/sync/cursor`) so cloud-sync can advance
sync_state without violating the single-writer SQLite rule (ADR-4). -->

## Story

As a system operator,
I want a `cloud-sync` container on the train that buffers events locally and publishes them to the landside Mosquitto broker,
so that no event data is lost during cellular dead zones or tunnel traversals, and the upstream pipeline containers are never blocked waiting for a network connection.

## Acceptance Criteria

1. **New `cloud-sync/` container exists** (mirrors `event-store/`, `fusion/` layout): `pyproject.toml`, `Dockerfile` (`FROM python:3.11-slim-bookworm`), `.env.example`, `src/cloud_sync/`, `tests/{unit,integration,contract}/`. Python 3.11, FastAPI for the `/health` endpoint, `aiomqtt>=2.0` for the MQTT client, `httpx` for the event-store REST client. Coverage gate ≥90%; mypy strict; ruff clean.

2. **Reads events from event-store** via authenticated REST: `cloud-sync` polls `GET {event_store_url}/api/v1/events?after=<last_pulled_event_id>&limit=N` (default N=200) with `X-API-Key`. Uses the existing event-store cursor pagination semantics. Cursor advances locally per pulled batch BEFORE publish — see AC4 for ack/truncate behavior. Source = `event-store` REST API, NOT direct SQLite read (single-writer rule, ADR-4).

3. **Local SQLite buffer queues each pulled event before publish** (new DB file owned by cloud-sync, e.g. `/var/lib/cloud-sync/queue.db`). Schema:
   ```sql
   PRAGMA journal_mode=WAL;
   CREATE TABLE publish_queue (
       event_id      TEXT PRIMARY KEY,         -- UUID4 from EventEnvelope
       vehicle_id    TEXT NOT NULL,
       event_type    TEXT NOT NULL,
       timestamp     TEXT NOT NULL,            -- source timestamp for ordering
       envelope_json TEXT NOT NULL,            -- full EventEnvelope serialised
       enqueued_at   TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%fZ','now')),
       published_at  TEXT,                     -- NULL until broker PUBACK
       attempts      INTEGER NOT NULL DEFAULT 0,
       last_error    TEXT
   );
   CREATE INDEX idx_queue_pending ON publish_queue (timestamp, event_id) WHERE published_at IS NULL;
   CREATE TABLE cursor_state (
       id INTEGER PRIMARY KEY CHECK (id = 1),
       last_pulled_event_id TEXT,
       last_acked_event_id  TEXT,
       updated_at TEXT
   );
   INSERT OR IGNORE INTO cursor_state (id) VALUES (1);
   ```
   `INSERT OR IGNORE` on event_id PK is the dedup gate — re-pulling the same row from event-store on restart is a no-op locally.

4. **Publish to landside Mosquitto on topic `oebb/events/{vehicle_id}/{event_type}` with QoS 1**: payload is the EventEnvelope JSON verbatim (no payload interpretation, no mutation — pure transport per the epic's "Architecture note"). On broker PUBACK, set `published_at`. QoS 1 + landside event-store's `UNIQUE(journey_id, event_type, timestamp)` dedup (ADR-3) handles "at-least-once → exactly-once" semantics.

5. **Offline tolerance (72h)**: when MQTT connection is unavailable, the publish loop awaits a `broker_connected: asyncio.Event` while the pull loop continues to accumulate rows in `publish_queue` independently. No back-pressure on event-store. The publish loop wakes on reconnect and drains the pending queue **in chronological order** (`ORDER BY timestamp ASC, event_id ASC`).

6. **Rate limit publishes**: configurable `publish_rate_per_sec` (default 500). Implementation = simple token-bucket (`asyncio.Semaphore` released by a 1-second timer task, or a `last_publish_t + sleep(1/rate - elapsed)` per emit). On reconnect drain, the rate-limit applies to every publish — protects the broker from a 72h-backlog flood. **Burst handling**: a single token-bucket window so 500 publishes in any rolling 1s remain the cap.

7. **`GET /health` endpoint** (FastAPI on port `${CLOUD_SYNC_PORT:-8082}`) returns:
   ```json
   {
     "status": "ok",
     "broker_connected": true,
     "queue_depth": 142,
     "last_publish_utc": "2026-05-20T14:23:11.123Z"
   }
   ```
   - `status` is always `"ok"` while the process is alive (separate from broker connectivity)
   - `queue_depth` is `SELECT COUNT(*) FROM publish_queue WHERE published_at IS NULL`
   - `last_publish_utc` is `NULL` (JSON) until the first successful publish

8. **Structured JSON logs (structlog)** on every state transition: `cloud_sync.connect`, `cloud_sync.disconnect`, `cloud_sync.reconnect`, `cloud_sync.flush_started`, `cloud_sync.flush_complete` (with `count` + `duration_ms`), `cloud_sync.publish_error` (with `event_id` + retry attempt + `last_error`). Use `structlog.processors.JSONRenderer()` exactly as the other containers do (see `event-store/src/event_store/main.py:21-28`).

9. **Sync-then-truncate ack loop (ADR-4)**: after a contiguous prefix of rows has `published_at != NULL`, cloud-sync calls a NEW companion endpoint on event-store: `POST {event_store_url}/api/v1/sync/cursor` with body `{"last_event_id": "<uuid>"}`. The event-store endpoint:
   - Calls `event_store.sync.cursor.advance_cursor(conn, last_event_id)`
   - Calls `event_store.sync.cursor.truncate_old_journeys(conn, retain=3)` (existing helper, retains last 3 journeys as debug buffer)
   - Returns `{"data": {"acked": "<uuid>", "truncated_journeys": N}}`
   - Auth-gated by `Depends(require_api_key)` like the rest of `/api/v1/*`
   After event-store responds 200, cloud-sync updates its own `cursor_state.last_acked_event_id` AND deletes confirmed-published rows from `publish_queue` (queue is for retry only — once event-store has the ack we don't need them locally either).

10. **No event interpretation** — the "Architecture note" in the epic is law. cloud-sync MUST NOT touch the `payload` field of any envelope. The publish path serializes `envelope_json` straight through. There is NO Pydantic re-validation of payloads on the publish path. The publish loop's only structural reads are `event_id`, `vehicle_id`, `event_type`, `timestamp` (and only for routing/ordering, never for transformation).

11. **Quality gates**:
    - `tests/unit/test_queue.py`: queue DB schema + `INSERT OR IGNORE` dedup + cursor advance.
    - `tests/unit/test_rate_limit.py`: token bucket honors 500 ev/s; burst of 1000 over 2s is throttled.
    - `tests/unit/test_health.py`: `/health` shape + values from a fixture queue.
    - `tests/integration/test_offline_queue_accumulation.py`: simulate broker down 60s; pull 100 events from a fake event-store; assert all 100 land in `publish_queue` with `published_at IS NULL` and queue depth = 100.
    - `tests/integration/test_ordered_flush.py`: simulate broker drop mid-sequence (events 40-60); assert all 100 arrive at the fake broker in `(timestamp, event_id)` order. Implements the epic's flagship test.
    - `tests/integration/test_sync_cursor_ack.py`: end-to-end against a real event-store TestClient: cloud-sync pulls → publishes (fake broker PUBACK) → calls `POST /api/v1/sync/cursor` → event-store `last_synced_event_id` advances + `truncate_old_journeys` runs.
    - `tests/contract/test_topic_format.py`: every publish hits topic matching regex `^oebb/events/[A-Za-z0-9-]+/[A-Z_]+$`.
    - mypy `--strict src/`; ruff `check src/ tests/` zero violations.
    - GitLab CI: `lint:cloud-sync` + `test:cloud-sync` jobs.

12. **Companion endpoint on event-store** (NEW, in `event-store/src/event_store/routes/sync.py`): `POST /api/v1/sync/cursor` per AC9. Requires `X-API-Key`. Idempotent: re-submitting the same `last_event_id` is a no-op (still 200). Mark unsupported transitions clearly — if `last_event_id` does not exist in events table → 400 `INVALID_CURSOR` (same error shape as story 4-7). Updates `event-store/CLAUDE.md` "Key Patterns" with one line describing the new endpoint.

## Tasks / Subtasks

- [ ] Bootstrap `cloud-sync/` package (AC: 1)
  - [ ] `cloud-sync/pyproject.toml` mirror of `event-store/pyproject.toml` — deps `fastapi`, `uvicorn[standard]`, `pydantic`, `pydantic-settings`, `structlog`, `httpx>=0.27`, `aiomqtt>=2.0`, `oebb-shared`. Dev deps `pytest`, `pytest-cov`, `pytest-asyncio`, `respx>=0.21`, `mypy`, `ruff`. Coverage `fail_under = 90`. mypy strict. ruff `line-length=100`, `select=["E","F","B","DTZ","RUF","I","UP"]`. Markers `unit`/`integration`/`contract`. `asyncio_mode = "auto"`. `filterwarnings = ["ignore::ResourceWarning"]` (matches fusion's pattern for httpx-on-TestClient).
  - [ ] `cloud-sync/Dockerfile` (`FROM python:3.11-slim-bookworm`). Install shared editable first, then cloud-sync. `EXPOSE 8082`. `CMD ["python", "-m", "cloud_sync.main"]`.
  - [ ] `cloud-sync/.env.example` with all `CLOUD_SYNC_*` vars (see config below).
  - [ ] `cloud-sync/src/cloud_sync/__init__.py` (empty) + `tests/__init__.py` + `tests/{unit,integration,contract}/__init__.py`.

- [ ] Implement `config.py` (AC: 1, 2, 6, 7)
  - [ ] `class Settings(BaseSettings)` with `env_prefix="CLOUD_SYNC_"`, `env_file=".env"`, `extra="ignore"`.
  - [ ] Fields: `event_store_url: str = "http://event-store:8001"`, `event_store_api_key: SecretStr | None = None` (matches event-store's `EVENT_STORE_API_KEY` naming pattern but routed via this var so secrets don't share scope), `mqtt_host: str = "localhost"`, `mqtt_port: int = 1883`, `mqtt_username: SecretStr | None = None`, `mqtt_password: SecretStr | None = None`, `mqtt_topic_prefix: str = "oebb/events"`, `queue_db_path: str = "/var/lib/cloud-sync/queue.db"`, `host: str = "0.0.0.0"`, `port: int = 8082`, `pull_batch_size: int = 200`, `pull_poll_interval_s: float = 1.0`, `publish_rate_per_sec: int = 500`, `truncate_retain_journeys: int = 3`.
  - [ ] `_coerce_empty_to_none` validator on `event_store_api_key`, `mqtt_username`, `mqtt_password` (same pattern as event-store/config.py:26-40 — empty-string → None to avoid the Docker placeholder footgun).

- [ ] Implement `db.py` (AC: 3, 5)
  - [ ] `get_connection(path: str | None) -> sqlite3.Connection` with `PRAGMA journal_mode=WAL`. Same idiom as `event-store/src/event_store/database.py:get_connection`.
  - [ ] `init_db(conn)` runs the embedded `schema.sql` (`CREATE TABLE IF NOT EXISTS`).
  - [ ] `enqueue_event(conn, envelope_dict)` — `INSERT OR IGNORE` keyed by `event_id`. Returns `True` if inserted, `False` on duplicate. Stores `envelope_json = json.dumps(envelope, sort_keys=True)`.
  - [ ] `iter_pending(conn, limit) -> list[dict]` — `SELECT envelope_json, event_id, vehicle_id, event_type, timestamp FROM publish_queue WHERE published_at IS NULL ORDER BY timestamp ASC, event_id ASC LIMIT ?`.
  - [ ] `mark_published(conn, event_id)` — `UPDATE publish_queue SET published_at = ? WHERE event_id = ?` with ISO-8601-Z timestamp.
  - [ ] `mark_failed(conn, event_id, error)` — bump `attempts`, set `last_error`.
  - [ ] `queue_depth(conn) -> int` — count of `published_at IS NULL`.
  - [ ] `last_publish_utc(conn) -> str | None` — `SELECT MAX(published_at) FROM publish_queue`.
  - [ ] `cursor_state_get(conn) -> tuple[str | None, str | None]` returning `(last_pulled_event_id, last_acked_event_id)`.
  - [ ] `cursor_state_set_pulled(conn, event_id)` and `cursor_state_set_acked(conn, event_id)` — single-row UPDATE on `cursor_state`.
  - [ ] `delete_acked(conn, up_to_event_id)` — `DELETE FROM publish_queue WHERE published_at IS NOT NULL AND timestamp <= (SELECT timestamp FROM publish_queue WHERE event_id = ?)` — deletes the contiguous published prefix up to the acked cursor.
  - [ ] `schema.sql` in `src/cloud_sync/` with the AC3 schema verbatim.

- [ ] Implement `event_store_client.py` (AC: 2, 9)
  - [ ] `class EventStoreClient` wrapping `httpx.AsyncClient`. Constructor takes the settings and an injected client (so tests can inject `respx`).
  - [ ] `async def pull(after_event_id: str | None, limit: int) -> EventPage` — GET `/api/v1/events?after=...&limit=...` with `X-API-Key`. Parses response into a small dataclass `EventPage(data: list[dict], next_cursor: str | None, count: int)` — duck-typed off event-store's response shape. Raises `httpx.HTTPError` on transport failure (caller's pull loop catches + backs off).
  - [ ] `async def ack_cursor(last_event_id: str) -> None` — POST `/api/v1/sync/cursor` with `{"last_event_id": "..."}` body + X-API-Key. 400 → log warn + skip (cursor drift); 200 → success.
  - [ ] Retry policy: use `oebb_shared.http.retry.DEFAULT_RETRY` decorator (5 attempts, exponential backoff) for both methods. Matches the pattern in fusion/inference.

- [ ] Implement `mqtt_client.py` (AC: 4, 5, 6, 8)
  - [ ] `class MqttPublisher` wrapping `aiomqtt.Client`. Owns a `broker_connected: asyncio.Event`, a `last_publish_utc: str | None`, and a `_rate_limiter` (token bucket).
  - [ ] `async def run(stop_event: asyncio.Event, on_publish: Callable[[str], Awaitable[None]]) -> None` — the long-running coroutine. Outer loop:
    ```python
    while not stop_event.is_set():
        try:
            async with aiomqtt.Client(...) as client:
                self._broker_connected.set()
                log.info("cloud_sync.connect", host=..., port=...)
                # publish loop reads from queue + drains
                await self._publish_loop(client, on_publish)
        except aiomqtt.MqttError as exc:
            self._broker_connected.clear()
            log.warning("cloud_sync.disconnect", error=str(exc))
            await asyncio.sleep(self._reconnect_backoff())  # 1, 2, 4, ..., 60s
            log.info("cloud_sync.reconnect")
    ```
  - [ ] `async def _publish_loop(client, on_publish)`: loops reading `iter_pending(conn, limit=publish_rate_per_sec)`. For each event, `await self._rate_limiter.acquire()`; `await client.publish(f"{prefix}/{vehicle_id}/{event_type}", payload=envelope_json, qos=1)`; `await on_publish(event_id)` (callback marks the row published + bumps `last_publish_utc`). Catch `aiomqtt.MqttError` and re-raise to the outer loop so reconnect happens.
  - [ ] Topic format helper: `_topic(vehicle_id, event_type) -> str` — uses ONLY allowlist chars (slugify if vehicle_id contains anything outside `[A-Za-z0-9-]`); event_type comes from `EventType` enum so already safe.
  - [ ] Token-bucket implementation: `_TokenBucket` with `capacity = rate`, `refill_rate = rate / second`; `acquire()` sleeps until a token is available (`asyncio.sleep`). Keep it ~30 LOC.

- [ ] Implement `pull_loop.py` (AC: 2, 5)
  - [ ] `async def run(stop_event, client: EventStoreClient, conn_factory)` — independent of MQTT state. Loop:
    ```python
    while not stop_event.is_set():
        cursor, _ = cursor_state_get(conn)
        try:
            page = await client.pull(after_event_id=cursor, limit=settings.pull_batch_size)
        except httpx.HTTPError as exc:
            log.warning("cloud_sync.pull_failed", error=str(exc))
            await asyncio.sleep(5.0); continue
        if not page.data:
            await asyncio.sleep(settings.pull_poll_interval_s); continue
        for envelope in page.data:
            enqueue_event(conn, envelope)
        if page.data:
            cursor_state_set_pulled(conn, page.data[-1]["event_id"])
        # next iteration immediately if page was full (drain backlog faster)
        if page.next_cursor is None:
            await asyncio.sleep(settings.pull_poll_interval_s)
    ```
  - [ ] On startup: if `last_pulled_event_id` is set, resume from there. On a fresh DB, pull from the beginning of event-store's history (cursor=None) and rely on `INSERT OR IGNORE` to dedup against any pre-seeded rows.

- [ ] Implement `ack_loop.py` (AC: 9)
  - [ ] `async def run(stop_event, client: EventStoreClient, conn_factory, mqtt: MqttPublisher)`:
    - Wait for `mqtt.broker_connected.is_set()`.
    - Periodically (every 30s, configurable `ack_interval_s`), compute the **contiguous published prefix**: `SELECT event_id, timestamp FROM publish_queue WHERE published_at IS NOT NULL ORDER BY timestamp ASC, event_id ASC` — walk until the first gap (a `published_at IS NULL` row). The last event_id BEFORE the gap is the new acked cursor.
    - If new cursor > `last_acked_event_id`, POST it to event-store via `client.ack_cursor(...)`. On 200: `cursor_state_set_acked(conn, ...)` + `delete_acked(conn, ...)`.
    - Log `cloud_sync.flush_complete count=N duration_ms=...` after each successful ack batch.

- [ ] Implement `health.py` + FastAPI app (AC: 7)
  - [ ] Build a tiny `FastAPI(title="cloud-sync")` with one route `GET /health` returning the AC7 JSON. No auth on health — orchestrator probe.
  - [ ] Computes `queue_depth` and `last_publish_utc` from a snapshot SQLite conn opened per-request (acceptable — `/health` is low-frequency; avoids holding a connection across the pull/publish loops).
  - [ ] `broker_connected` is read from the shared `MqttPublisher.broker_connected.is_set()` — passed in via `app.state`.

- [ ] Implement `main.py` (AC: 1, 8)
  - [ ] `Settings()` instance.
  - [ ] `@asynccontextmanager async def lifespan(app)`: open the SQLite connection factory (per-task connections — sqlite3 connections are NOT thread-safe across awaits cleanly), open `httpx.AsyncClient(timeout=5.0)`, build `EventStoreClient`, `MqttPublisher`, `stop_event`. Launch `pull_loop.run`, `mqtt.run`, `ack_loop.run` as background tasks via `asyncio.create_task`. On shutdown: `stop_event.set()`, await all tasks with timeout, close httpx + SQLite.
  - [ ] `app.state.mqtt = mqtt` so `/health` can read `broker_connected`.
  - [ ] `app.state.queue_db_path = settings.queue_db_path` so `/health` can open its own snapshot conn.
  - [ ] `uvicorn.run(app, host=settings.host, port=settings.port)`.

- [ ] Add event-store companion endpoint (AC: 9, 12)
  - [ ] Create `event-store/src/event_store/routes/sync.py` with `router = APIRouter(prefix="/api/v1/sync", dependencies=[Depends(require_api_key)])` and `POST /cursor`.
  - [ ] Request model: `CursorAdvanceRequest(BaseModel)` with `last_event_id: str` (validate UUID4 via Pydantic regex matching `_UUID_RE` from `oebb_shared.events.envelope`).
  - [ ] Handler:
    1. Verify `last_event_id` exists in events table (`SELECT 1 FROM events WHERE event_id = ?`); if not → 400 `INVALID_CURSOR` (mirror shape from `routes/events.py`).
    2. Idempotency: if `last_event_id == get_sync_cursor(conn)` → return 200 with `truncated_journeys: 0` and short-circuit (no advance, no truncate).
    3. Call `advance_cursor(conn, last_event_id)`.
    4. Call `truncate_old_journeys(conn, retain=3)` — returns deleted row count.
    5. Return `{"data": {"acked": last_event_id, "truncated_journeys": deleted_count}}` status 200.
  - [ ] Wire into `main.py` via `app.include_router(sync_router)`.
  - [ ] Update `event-store/CLAUDE.md` "Key Patterns" with one paragraph describing the cloud-sync ack contract.
  - [ ] Tests in `event-store/tests/unit/test_sync_cursor_route.py`:
    - `test_post_cursor_advances_and_truncates`
    - `test_post_cursor_idempotent_on_same_id`
    - `test_post_cursor_unknown_event_id_returns_400`
    - `test_post_cursor_missing_api_key_returns_401`

- [ ] GitLab CI jobs (AC: 11)
  - [ ] `lint:cloud-sync` mirror of `lint:event-store` (ruff + mypy).
  - [ ] `test:cloud-sync` mirror with `--cov-fail-under=90`.
  - [ ] Extend `security:bandit` to include `cloud-sync/src`.

- [ ] Write tests (AC: 11)

  - [ ] `tests/unit/test_queue.py` covering enqueue dedup, ordering, depth, last_publish_utc, mark_published/failed, delete_acked.
  - [ ] `tests/unit/test_rate_limit.py` covering token bucket honors `publish_rate_per_sec=500`; 1000 ops in 2s ≥ 1.9s elapsed.
  - [ ] `tests/unit/test_topic.py` covering `_topic(...)` slug + EventType safety.
  - [ ] `tests/unit/test_health.py` covering `/health` with a pre-seeded queue.
  - [ ] `tests/unit/test_config.py` covering empty-string secret coercion (mirrors event-store 4-7 patch).
  - [ ] `tests/integration/test_offline_queue_accumulation.py` using a fake event-store ASGI app (`respx` against `GET /api/v1/events`) + a fake broker that NEVER accepts a connection. Push 100 events; assert `queue_depth == 100`, `published_at IS NULL`.
  - [ ] `tests/integration/test_ordered_flush.py` (the flagship test): fake broker accepts events 0-39, drops the connection, refuses for 1s, then accepts 40-99. Use an `asyncio` TCP server speaking minimal MQTT 3.1.1 (or a small `aiomqtt`-compatible fake). Assert all 100 PUBLISHes arrive in `(timestamp, event_id)` order.
  - [ ] `tests/integration/test_sync_cursor_ack.py` against a real event-store TestClient: seed events, run cloud-sync's ack_loop for one tick with a fake broker that ACKs everything; assert event-store's `get_sync_cursor` advances + `publish_queue` rows are deleted up to that cursor.
  - [ ] `tests/contract/test_topic_format.py` snapshots every topic emitted in an integration run against the regex `^oebb/events/[A-Za-z0-9-]+/[A-Z_]+$`.
  - [ ] Security AST tests in `tests/unit/test_security.py` — `test_no_env_get_in_<module>` per Rule 8.

- [ ] Run quality gates (AC: 11)
  - [ ] `mypy --strict src/cloud_sync/`
  - [ ] `pytest --strict-markers -q --cov=cloud_sync --cov-fail-under=90`
  - [ ] `ruff check src/ tests/`

## Security Tests

**OEBB-specific:**
- [ ] `test_no_env_get_in_<module>` AST audit on every new cloud-sync module (Rule 8)
- [ ] `test_no_raw_video_or_stream_url_in_published_payload` — fuzz: seed event-store with envelopes containing innocuous payloads; assert no published message body contains `rtsp://`, `file://`, `/dev/video`, `.mp4`, etc. (reuse the regex pattern from `event-store/tests/integration/test_websocket_fanout.py`)
- [ ] `test_mqtt_credentials_never_logged` — capture structlog output during a connect/disconnect cycle; assert `mqtt_password.get_secret_value()` never appears in any log line
- [ ] `test_payload_passed_through_verbatim` — feed an event-store envelope with an arbitrary JSON payload; assert the MQTT message body byte-equals `json.dumps(envelope, sort_keys=True)`. Pure transport.
- [ ] `test_event_store_api_key_uses_hmac_compare_digest` is N/A here — cloud-sync is the CLIENT side; verify only that the key is sent in `X-API-Key` header (`respx` capture)
- [ ] `test_topic_format_strict_allowlist` — programmatically attempt to publish with a synthetic `vehicle_id="; rm -rf /"`; assert the topic emitted matches the allowlist regex and the bad chars are slugified out

## Dev Notes

### Architecture Rules (Must Follow)

1. **Rule 8 — No `os.environ.get()`** anywhere in `src/cloud_sync/`. All config from injected `Settings`. AST test enforces per module.

2. **Pure transport — NEVER interpret payloads (Architecture note in the epic).** The publish path serialises `envelope_json` straight to the broker. No Pydantic re-validation of `payload`. The ONLY structural reads are `event_id` (PK + dedup), `vehicle_id` (topic), `event_type` (topic), `timestamp` (ordering). If you find yourself parsing `envelope["payload"]["whatever"]` in cloud-sync, you're doing it wrong — that's fusion's job.

3. **Three independent loops, not one.** `pull_loop`, `mqtt.run` (publish), `ack_loop` run as three `asyncio.create_task(...)` siblings under `lifespan`. They share the SQLite queue + the `broker_connected` event. The pull loop MUST NOT depend on broker state — that's the whole point of the 72h offline AC.

4. **SQLite connections are per-task.** Each loop opens its own `sqlite3.Connection` (single-writer + WAL allows many readers). Do NOT share a connection across `await` boundaries — sqlite3 module connections are not designed for that.

5. **`INSERT OR IGNORE` is the local dedup gate.** On restart, cloud-sync re-pulls from `last_pulled_event_id` (which is the last successfully-pulled event, NOT the last acked). If the process crashed AFTER pulling but BEFORE publishing, the re-pull will re-enqueue, and `INSERT OR IGNORE` short-circuits the duplicate. Idempotency landing — never publish twice — comes from QoS 1 + landside event-store's `UNIQUE(journey_id, event_type, timestamp)`.

6. **QoS 1, not 2.** AC4 requires "no event published twice" but the dedup is landside (ADR-3). QoS 2 (exactly-once) adds latency for no benefit when the consumer already dedupes. QoS 0 (at-most-once) would violate the AC. QoS 1 is the right choice.

7. **Topic format is strict allowlist.** `oebb/events/{vehicle_id}/{event_type}`. `vehicle_id` MUST be slugified (replace anything outside `[A-Za-z0-9-]` with `-`) to defend against injection of MQTT wildcard chars (`#`, `+`) or path traversal. `event_type` comes from `EventType.value` so already safe (the enum is `[A-Z_]+`).

8. **Rate limiter is per-process, not per-broker-session.** A reconnect does NOT reset the bucket. Otherwise a flapping broker triggers a thundering herd on each reconnect.

9. **Ack loop runs on a timer, not after every publish.** Per AC9, contiguous-prefix ack happens every 30s (configurable). This batches the event-store HTTP call to ~120 per hour rather than 1.8M (at 500 ev/s × 3600s). Sync cursor lag is at most `ack_interval_s` — acceptable.

10. **Companion endpoint goes on event-store, not cloud-sync.** AC12. Cloud-sync owns its own queue DB; event-store owns the sync_state row. Cross-process writes via HTTP, not via SQLite file sharing.

11. **`aiomqtt>=2.0`** — the 2.x API uses `async with aiomqtt.Client(...)` as the context manager. The 1.x `Client.connect()` / `client.subscribe()` style is deprecated. Pin to `>=2.0,<3.0`.

12. **`oebb_shared.http.retry.DEFAULT_RETRY`** — used for the event-store HTTP calls. Inherited from fusion's pattern.

13. **Empty-string secret coercion.** `event_store_api_key`, `mqtt_username`, `mqtt_password` all use the same `_coerce_empty_to_none` validator pattern from event-store/config.py (post-code-review-4-7 fix) — prevents the Docker `KEY=` footgun.

### Files to Create (NEW)

```
cloud-sync/pyproject.toml
cloud-sync/Dockerfile
cloud-sync/.env.example
cloud-sync/CLAUDE.md
cloud-sync/src/cloud_sync/__init__.py
cloud-sync/src/cloud_sync/main.py
cloud-sync/src/cloud_sync/config.py
cloud-sync/src/cloud_sync/db.py
cloud-sync/src/cloud_sync/schema.sql
cloud-sync/src/cloud_sync/event_store_client.py
cloud-sync/src/cloud_sync/mqtt_client.py
cloud-sync/src/cloud_sync/pull_loop.py
cloud-sync/src/cloud_sync/ack_loop.py
cloud-sync/src/cloud_sync/health.py
cloud-sync/tests/__init__.py
cloud-sync/tests/unit/__init__.py
cloud-sync/tests/unit/test_security.py
cloud-sync/tests/unit/test_queue.py
cloud-sync/tests/unit/test_rate_limit.py
cloud-sync/tests/unit/test_topic.py
cloud-sync/tests/unit/test_health.py
cloud-sync/tests/unit/test_config.py
cloud-sync/tests/contract/__init__.py
cloud-sync/tests/contract/test_topic_format.py
cloud-sync/tests/integration/__init__.py
cloud-sync/tests/integration/test_offline_queue_accumulation.py
cloud-sync/tests/integration/test_ordered_flush.py
cloud-sync/tests/integration/test_sync_cursor_ack.py

event-store/src/event_store/routes/sync.py
event-store/tests/unit/test_sync_cursor_route.py
```

### Files to Update (READ FIRST — current state documented)

**`event-store/src/event_store/main.py`** (READ all)
- Current: lifespan inits DB + broadcaster; includes events/journeys/health routers; WS endpoint at `/ws`.
- Add: `from .routes.sync import router as sync_router` + `app.include_router(sync_router)`.
- Preserve: everything else.

**`event-store/CLAUDE.md`** (audit + update)
- Current: documents idempotency contract, cursor pagination, filters, auth, WebSocket fan-out (post-4-7).
- Add: a "Key Patterns" subsection — `POST /api/v1/sync/cursor` advances `sync_state.last_synced_event_id` and triggers `truncate_old_journeys(retain=3)`. Idempotent on same id. Auth-gated. Used by `cloud-sync` only.

**`.gitlab-ci.yml`** (READ first; pattern from event-store + fusion)
- Add `lint:cloud-sync` mirroring `lint:event-store`.
- Add `test:cloud-sync` mirroring `test:event-store` with `--cov-fail-under=90` and the test markers.
- Extend `security:bandit` to include `cloud-sync/src`.

### Reference Patterns

**Settings pattern with empty-string coercion** — from `event-store/src/event_store/config.py:26-40` (post-4-7-review). Apply to `event_store_api_key`, `mqtt_username`, `mqtt_password`.

**Three-tasks-under-lifespan pattern** — from `event-store/src/event_store/main.py:32-58`. Adapt to launch pull/publish/ack as three `asyncio.create_task` siblings.

**HTTP client + DEFAULT_RETRY** — from `fusion/src/fusion/enrichment.py:_post_envelope`. Decorator + `resp.raise_for_status()` + httpx async.

**Token-bucket rate limiter** — small enough to write inline. Reference pattern (no library):
```python
class _TokenBucket:
    def __init__(self, rate: int) -> None:
        self._rate = rate
        self._tokens = float(rate)
        self._last = time.monotonic()
        self._lock = asyncio.Lock()
    async def acquire(self) -> None:
        async with self._lock:
            now = time.monotonic()
            self._tokens = min(self._rate, self._tokens + (now - self._last) * self._rate)
            self._last = now
            if self._tokens < 1.0:
                wait = (1.0 - self._tokens) / self._rate
                await asyncio.sleep(wait)
                self._tokens = 0.0
            else:
                self._tokens -= 1.0
```
Total ~20 LOC; no `aiolimiter` dep.

**aiomqtt 2.x usage** — canonical:
```python
import aiomqtt

async with aiomqtt.Client(
    hostname=settings.mqtt_host,
    port=settings.mqtt_port,
    username=settings.mqtt_username.get_secret_value() if settings.mqtt_username else None,
    password=settings.mqtt_password.get_secret_value() if settings.mqtt_password else None,
) as client:
    await client.publish(topic, payload=envelope_json.encode(), qos=1)
```
The `async with` handles connect/disconnect cleanly; on `MqttError` exit, the outer reconnect loop runs.

### Shared Models Available

- `oebb_shared.events.envelope.EventEnvelope` — we DESERIALIZE (json.loads) but do NOT re-validate payloads. Only `event_id`, `vehicle_id`, `event_type`, `timestamp` are read.
- `oebb_shared.events.types.EventType` (StrEnum) — used to validate `event_type` is a known label before forming the topic. If unknown, log WARN + skip (defence-in-depth against schema drift).
- `oebb_shared.http.retry.DEFAULT_RETRY` — wraps `EventStoreClient.pull` and `.ack_cursor`.

### Previous Story Intelligence

From `4-7-event-store-onboard-rest-api-websocket` (just completed + code-reviewed):
- **`SecretStr` empty-string coercion** is now the canonical config pattern. Don't repeat the footgun.
- **ADR-10 envelope shape** for errors: `{"error": "CODE", "detail": "...", "recoverable": bool}` wrapped in `{"detail": {...}}` by FastAPI. The new sync endpoint follows the same convention.
- **`?after=<unknown>` cursor returns 400 INVALID_CURSOR** (not silent page-1). Mirror that in `POST /api/v1/sync/cursor`.
- **`response_model=...` Pydantic envelope** is the canonical wrap for 200 responses — restore the typed model for the sync ack response.
- **`time.perf_counter` for latency measurements** — only used in the rate-limit test, not the hot path.
- **pytest-asyncio + `asyncio_mode = "auto"`** is required; don't try to drop it.
- **`filterwarnings = ["ignore::ResourceWarning"]`** in pyproject — fusion + event-store both ship with this for `httpx.AsyncClient` in `TestClient` fixtures.

From `4-6-fusion-alert-correlation-suppression`:
- **Single `asyncio.Lock` for state mutation across `await`** — relevant for the three-loops coordination; the SQLite queue has its own WAL serialization but the in-memory `broker_connected: asyncio.Event` is the primary cross-task signal.

### Latest Tech Notes

- **aiomqtt 2.x** (released 2024) — drop-in for the 1.x deprecated `Client.connect/disconnect` shape. Uses `async with` context manager. `MqttError` covers connect refused, broker drop, and auth failure. PyPI `aiomqtt==2.x.x`.
- **paho-mqtt** internally — aiomqtt wraps paho 2.0+. No need to depend on paho directly.
- **MQTT 3.1.1** is what aiomqtt speaks by default; MQTT 5 is opt-in via `protocol=ProtocolVersion.V5`. Stick to 3.1.1 for Mosquitto compat unless the landside story 1.L1 dictates otherwise.
- **Mosquitto default port 1883** (no TLS), 8883 (TLS). For PoC use 1883 + VLAN isolation; production should layer TLS — flag as a follow-up if landside Mosquitto doesn't yet have TLS configured.

### References

- [Source: _bmad-output/planning-artifacts/epics.md#Story 4.CS1 (L1436-1454)] — epic spec
- [Source: _bmad-output/planning-artifacts/architecture.md#ADR-4 (L330-348)] — sync-then-truncate + WAL contract
- [Source: _bmad-output/planning-artifacts/architecture.md#ADR-3 (L318-328)] — landside idempotency dedup
- [Source: event-store/src/event_store/schema.sql:39-46] — sync_state table cloud-sync targets
- [Source: event-store/src/event_store/sync/cursor.py] — `advance_cursor` + `truncate_old_journeys` helpers to expose via the new endpoint
- [Source: event-store/src/event_store/routes/events.py] — cursor pagination contract cloud-sync consumes
- [Source: event-store/src/event_store/auth.py] — X-API-Key dep cloud-sync sends + new sync route requires
- [Source: event-store/CLAUDE.md] — idempotency + cursor patterns to honor
- [Source: shared/src/oebb_shared/events/envelope.py:54-131] — EventEnvelope shape cloud-sync transports verbatim
- [Source: shared/src/oebb_shared/http/retry.py] — DEFAULT_RETRY decorator
- [Source: project-context.md] — Karpathy Rules; CSS tokens (N/A here)
- [Source: _bmad-output/implementation-artifacts/4-7-event-store-onboard-rest-api-websocket.md] — most recent neighbouring story; config pattern, security tests, ADR-10 envelope shape

### Project Structure Notes

- New container at `cloud-sync/` — root of repo, peer to `event-store/`, `fusion/`, `inference/`, `vlan-pollers/`, `shared/`, `cloud-backend/`.
- Companion endpoint added to existing `event-store/` package (not a separate container).
- `cloud-sync/` has its own SQLite file (`/var/lib/cloud-sync/queue.db`), NEVER touches event-store's `/data/events.db` directly.

### Testing Standards Summary

- **Framework:** pytest, `asyncio_mode = "auto"`, markers `unit`/`integration`/`contract`.
- **Coverage:** `fail_under = 90` for `src/cloud_sync/`.
- **Type checking:** `mypy --strict` for `src/`.
- **Linting:** `ruff check` zero violations (`select=["E","F","B","DTZ","RUF","I","UP"]`).
- **HTTP mocking:** `respx` for event-store; in-process MQTT fake for broker.
- **Security AST checks:** every new module under `src/cloud_sync/` gets a `test_no_env_get_in_<module>` test in `test_security.py`.
- **Time:** `time.monotonic()` for token-bucket; `datetime.now(timezone.utc)` for ISO timestamps.
- **MQTT fake**: a small asyncio TCP server accepting MQTT 3.1.1 CONNECT/CONNACK/PUBLISH/PUBACK; ~80 LOC; lives in `tests/_fakebroker.py`. Avoid testcontainers/Docker-in-CI for now.

## Dev Agent Record

### Agent Model Used

claude-opus-4-7[1m]

### Debug Log References

### Completion Notes List

### File List
