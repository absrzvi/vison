# Story 10.1: Alert Confidence Metadata, Kill-Switch & AI Pipeline Health

Status: ready-for-dev

<!-- Created 2026-05-30 via grill-me + party-mode session. Code-only scope — exec-failure playbook content moved to E10-S3. Renamed from "exec-failure-playbook-and-confidence-metadata" → "alert-confidence-and-ai-pipeline-health" to reflect actual shipped surface. -->

## Story

As an AI PM closing the gap between "the system works" and "the operator changes how they run trains because of it,"
I want every `ALERT_RAISED` event to carry per-alert confidence and model-provenance metadata, every inference container to emit a 60-second heartbeat, three surfaces in Control Centre that consume them (per-alert confidence chip, fleet-degraded banner, AI pipeline row on System Health), and a cloud-backend kill-switch that suppresses new alerts of a disabled class at the API/SSE fan-out layer,
so that procurement conversations have a credible answer to "what happens when the AI is wrong," operators have a per-alert trust signal, and Nomad on-call has an emergency rollback path during PoC.

## Acceptance Criteria

### Schema changes (shared package)

1. **`AlertRaisedPayload` gains three required fields** in `shared/src/oebb_shared/events/payloads.py`:
   - `confidence_score: float | None` — value `None` only when `confidence_basis == "sensor"`.
   - `confidence_basis: Literal["model", "sensor", "fused"]` — required.
   - `model_versions: dict[str, str]` — required; empty dict allowed only when `confidence_basis == "sensor"`.

   A `model_validator(mode="after")` enforces:
   - `basis == "model"` → `score` is `float` in `[0.0, 1.0]` AND `model_versions` is non-empty.
   - `basis == "sensor"` → `score is None` AND `model_versions == {}`.
   - `basis == "fused"` → `score` is `float` in `[0.0, 1.0]` AND `len(model_versions) >= 2`.

   Violations raise `ValidationError` (no silent coercion).

2. **Detection payloads gain `model_versions: dict[str, str]`** as a required field on `DoorObstructionPayload`, `UnattendedBagPayload`, `AccessibilityDetectedPayload`, `OccupancyUpdatePayload`, `LuggageRackSaturationPayload`. Inference is the producer (AC8). Existing optional `confidence` fields on these payloads are unchanged.

3. **New event type `INFERENCE_HEARTBEAT`** added to `EventType` StrEnum and to the `EVENT_TYPE_TO_PAYLOAD` dispatch. Payload model `InferenceHeartbeatPayload` in `shared/src/oebb_shared/events/payloads.py`:
   ```python
   class InferenceHeartbeatPayload(_BasePayload):
       train_id: _NonEmptyStr
       model_versions: dict[str, str]            # same shape as on AlertRaisedPayload
       frames_processed_window: _NonNegInt        # frames processed since last heartbeat
       last_inference_at: datetime                # ISO-8601 UTC, with Z suffix
       hailo_device_ok: bool
   ```

4. **Contract tests** in `shared/tests/contract/test_alert_raised_compat.py`:
   - Round-trip serialise/deserialise for each of the three valid `(basis, score, models)` combinations.
   - Each of the invalid combinations raises `ValidationError` (covered by parameterised test).
   - `InferenceHeartbeatPayload` round-trips with strict-mode envelope.
   - `mypy --strict shared/` zero errors.

### Inference: model provenance (onboard)

5. **New module `inference/src/inference/model_provenance.py`** exposes `compute_model_versions() -> dict[str, str]` called once at startup. Returns exactly these four keys:
   - `detector_arch`: `HEF(settings.model_hef_path).get_network_group_names()[0]` — Hailo-authoritative, lie-proof.
   - `detector_hef`: `f"{basename}.hef@{sha256(hef_bytes)[:12]}"`.
   - `detector_code`: `f"git:{settings.git_sha[:8]}"` — injected via `ARG GIT_SHA` build arg in `inference/Dockerfile`. Building without `GIT_SHA` raises `RuntimeError("model provenance requires GIT_SHA build arg")` at app startup.
   - `detector_labels`: `f"labels@{sha256(labels_bytes)[:12]}"`. Labels file path comes from `settings.model_labels_path` (default `/models/yolov8m.labels`). Missing file → startup `RuntimeError`.

   Result is module-level cached. Stamped onto every candidate payload at emit time (AC6).

6. **Inference stamps `model_versions` on every detection payload** in `inference/src/inference/callback.py` and any other emit site producing `DoorObstructionPayload`, `UnattendedBagPayload`, `AccessibilityDetectedPayload`, `OccupancyUpdatePayload`, `LuggageRackSaturationPayload`. A structured `inference.model_provenance` log event is emitted exactly once at startup with all four values plus `hef_bottleneck_fps` (read but not stamped).

7. **Inference emits `INFERENCE_HEARTBEAT` every 60s** independently of detections. Cadence is `INFERENCE_HEARTBEAT_INTERVAL_S = 60` (settings, configurable for test). The heartbeat is POSTed to event-store with `source="inference"`. `frames_processed_window` is the count since the previous heartbeat (counter reset after emit). `hailo_device_ok` reflects the Hailo device handle health at emit time. Failure to emit (event-store unreachable) is logged at WARNING and does not crash the loop.

### Fusion: plumb confidence/basis/model_versions through emit_alert

8. **`Enrichment.emit_alert` signature** in `fusion/src/fusion/enrichment.py` changes to:
   ```python
   async def emit_alert(
       self,
       *,
       alert_code: str,
       car_id: str,
       description: str,
       confidence_basis: Literal["model", "sensor", "fused"],   # required
       zone: str | None = None,
       confidence_score: float | None = None,
       model_versions: dict[str, str] | None = None,
   ) -> None: ...
   ```
   `confidence_basis` is keyword-only and required — a handler that forgets it fails `mypy --strict`.

9. **Per-handler call-site updates:**
   - `door_obstruction.py` — passes `confidence_basis="fused"`, `confidence_score=payload.confidence` (read from upstream `DoorObstructionPayload` before AC9 car_id resolve), `model_versions = {**payload.model_versions, "door_sensor_firmware": ctx.door_firmware_version}`. `ctx.door_firmware_version` is read from `context_state` (sourced from vlan-pollers SNMP; default `"unknown"` until populated).
   - `accessibility.py` — passes `confidence_basis="model"`, `confidence_score=payload.confidence`, `model_versions=payload.model_versions`.
   - Slip-fall path in `health.py` (via existing `enricher.emit_alert` call) — passes `confidence_basis="model"`, `confidence_score` from the inbound dict (new field on the slip-fall candidate body), `model_versions` from inbound dict.
   - Any future VLAN-only alert path (out of scope for E10-S1 but verified at typing layer) — must pass `confidence_basis="sensor"`, `confidence_score=None`, `model_versions={}`.

10. **Two-phase emit discipline preserved** (fusion CLAUDE.md Pattern 1): `confidence_basis`/`score`/`model_versions` are computed before the `await enricher.emit_alert(...)` call; no state mutation occurs on failure.

### Cloud-backend: kill-switch table + fan-out enforcement

11. **New table `alert_class_state`** via Alembic migration `cloud-backend/migrations/versions/00XX_alert_class_state.py`:
    ```sql
    CREATE TABLE alert_class_state (
        alert_code        TEXT PRIMARY KEY,
        state             TEXT NOT NULL CHECK (state IN ('enabled', 'disabled')),
        disabled_by       TEXT,
        disabled_at       TIMESTAMPTZ,
        enabled_by        TEXT,
        enabled_at        TIMESTAMPTZ
    );
    ```
    No seed data — empty table means all alert codes default to `enabled`. Migration is safe under concurrent reads (no `DEFAULT` on existing tables; new table only).

12. **`X-Admin-Key`-protected admin endpoints** on `cloud-backend`:
    - `POST /api/v1/admin/alert-classes/{alert_code}/disable` — body `{"actor_name": str}` (non-empty). Header `X-Admin-Key` must match env var `CC_ADMIN_KEY`; missing/mismatched → 401. Empty `actor_name` → 422. On success: upserts row with `state='disabled', disabled_by=actor_name, disabled_at=now()`; emits structured log `admin.alert_class_disabled` with `alert_code, actor_name, request_source_ip`; emits `ALERT_CLASS_DISABLED` event envelope (new event type, payload `{alert_code, actor_name, source_ip}`). Returns `200 {"alert_code": ..., "state": "disabled"}`.
    - `POST /api/v1/admin/alert-classes/{alert_code}/enable` — same auth + body shape. Sets `state='enabled', enabled_by, enabled_at`; emits `ALERT_CLASS_REENABLED` event.
    - `GET /api/v1/admin/alert-classes` — same auth; returns current state of all rows.

    `CC_ADMIN_KEY` MUST come from env; CI grep check fails the build if any string matching the env var's value appears hardcoded in repo.

13. **Fan-out enforcement at the API/SSE layer:** On every fan-out of `ALERT_RAISED` events to Control Centre (REST `GET /api/v1/escalations`, REST `GET /api/v1/alerts`, SSE/WS streams), cloud-backend filters out events whose `alert_code` is currently `disabled` in `alert_class_state`. Lookup is cached in-process for 60s (cache invalidated on admin endpoint write). **In-flight escalations stay visible** — only events whose `t_raised > disabled_at` are filtered. Already-raised, not-yet-resolved escalations are unaffected.

14. **`ALERT_CLASS_DISABLED` and `ALERT_CLASS_REENABLED` event types** added to `shared/src/oebb_shared/events/types.py` and to `EVENT_TYPE_TO_PAYLOAD` dispatch. Payload: `{alert_code: str, actor_name: str, source_ip: str}` (both event types share the shape).

### Cloud-backend: confidence thresholds config + health flag

15. **New module `cloud-backend/src/cloud_backend/config/confidence_thresholds.py`** exporting:
    ```python
    DEFAULT_CONFIDENCE_THRESHOLDS: dict[str, float] = {
        "unattended_bag":           0.75,  # CALIBRATE — placeholder pending PoC data
        "door_obstruction":         0.85,  # CALIBRATE
        "accessibility_detected":   0.70,  # CALIBRATE
        "slip_fall":                0.75,  # CALIBRATE
        "luggage_rack_saturation":  0.70,  # CALIBRATE
    }
    DEGRADED_BANNER_FLOOR: float = 0.60     # CALIBRATE — fleet-wide rolling-1h mean trigger
    ```
    Every value carries a `# CALIBRATE` comment. Mutability deferred to Epic 11.

16. **`GET /api/v1/config/confidence-thresholds`** returns `{"per_class": {...}, "degraded_banner_floor": 0.60}`. Read-only (no POST endpoint in E10-S1). Open to any authenticated CC client (PoC: no auth — same posture as existing endpoints).

17. **Existing `GET /api/v1/health` endpoint gains a server-computed `ai_quality_degraded: bool` flag.** Rule:
    ```sql
    SELECT AVG(confidence_score) FROM events
    WHERE event_type = 'ALERT_RAISED'
      AND timestamp > NOW() - INTERVAL '1 hour'
      AND (payload->>'confidence_basis') = 'model'
    ```
    Flag is `true` when the mean is non-null AND `< DEGRADED_BANNER_FLOOR`. Computed inline in the health handler with 30s in-process cache. Empty result (no model-basis alerts in window) → flag is `false`.

### Cloud-backend: heartbeat ingest + AI pipeline health

18. **New table `train_inference_heartbeat`** via Alembic migration:
    ```sql
    CREATE TABLE train_inference_heartbeat (
        train_id        TEXT PRIMARY KEY,
        last_seen       TIMESTAMPTZ NOT NULL,
        model_versions  JSONB NOT NULL,
        hailo_device_ok BOOLEAN NOT NULL
    );
    ```
    Upserted on every `INFERENCE_HEARTBEAT` event ingest (ingestor reads `payload.train_id` as key, `now()` server-side as `last_seen`, persists `payload.model_versions` and `payload.hailo_device_ok`).

19. **New endpoint `GET /api/v1/health/ai-pipeline`** returns:
    ```json
    {
      "fleet_state": "green" | "amber" | "red",
      "trains": [
        {
          "train_id": "...",
          "state": "green" | "amber" | "red",
          "last_seen": "2026-05-30T14:32:00Z",
          "model_versions": {...},
          "hailo_device_ok": true
        }
      ]
    }
    ```
    Per-train state rule:
    - `green`: `now() - last_seen < 3min` AND `hailo_device_ok == true`
    - `amber`: `now() - last_seen < 3min` AND `hailo_device_ok == false`
    - `red`: `now() - last_seen >= 3min` OR no heartbeat row exists for a train that has any event in last 24h
    Fleet rule: worst-case per-train state (any red → fleet red; else any amber → amber; else green).

### Control Centre: three surfaces

20. **Per-alert confidence chip** rendered on every alert row in the alerts list (`control-centre/src/components/live/UnifiedFeed.jsx` and detail views). Computed client-side from `(confidence_basis, confidence_score, alert_code, thresholds)`:
    - Chip is rendered only when `confidence_basis === "model"`. `"sensor"` and `"fused"` alerts show no chip.
    - State:
      - `score >= thresholds[alert_code]` → label `"High confidence"`, neutral grey, no icon, no tooltip
      - `score >= thresholds[alert_code] * 0.85 && score < thresholds[alert_code]` → label `"Medium confidence"`, amber dot, tooltip: `"Model is less certain. Verify against CCTV before dispatching."`
      - `score < thresholds[alert_code] * 0.85` → label `"Verify"`, amber dot + bold, same tooltip
    - The numeric score is NEVER displayed on the chip. Numeric score IS shown in the alert detail drawer (`EscalationDetail.jsx`) under a "Model details" section along with the `model_versions` dict.
    - Thresholds fetched once on dashboard mount via `GET /api/v1/config/confidence-thresholds`, cached for the session.

21. **"Degraded" banner** rendered at the top of the alerts list when `GET /api/v1/health` returns `ai_quality_degraded: true`. Banner copy verbatim:
    > "AI alert quality is degraded. Nomad has been notified. Continue to verify alerts against CCTV as normal."
    Dismissible per-session (state in `sessionStorage`). Banner reappears on next session if flag still true. Banner is visually distinct from the existing reconnecting/connection banner (different background colour, no spinner).

22. **"AI pipeline" row on System Health page** (`control-centre/src/components/health/SystemHealth.jsx`). Single row with three states sourced from `GET /api/v1/health/ai-pipeline.fleet_state`:
    - `Green — running` (neutral, green dot)
    - `Amber — degraded` (amber dot, tooltip lists which trains are amber/red)
    - `Red — not inferencing` (red dot, tooltip lists which trains are red)
    Click opens a drawer listing per-train rows with `train_id`, `state`, `last_seen` (relative time, e.g. "14s ago"), `model_versions` dict, `hailo_device_ok`. No sparkline, no per-class breakdown.
    Cold-state copy at boot (when `trains` array is empty in the response): `"AI pipeline: starting. No inferences yet."`

### Out of scope (explicitly)

- Standalone "AI Quality" tile or section on System Health (replaced by the three surfaces above per party-mode round 2).
- New top-level "AI Quality" nav item (rejected by Saga; conceded by Freya).
- Pre-aggregated rollup table or background job (rejected by Winston; raw SQL aggregation in health handler is the precedent).
- False-positive rate, no-action rate, explicit-FP rate — all deferred to E10-S5 (alert quality measurement). The AI Quality drawer in E10-S1 shows **no** false-positive metric.
- Admin UI for kill-switch, user management, login, profile management, threshold mutability — all deferred to Epic 11 (Control Centre Admin & Identity). E10-S1 ships only the cloud-backend kill-switch endpoints + table + fan-out enforcement; operators interact via curl per the exec-failure playbook (E10-S3).
- Real auth/JWT/SSO. PoC uses a single shared `CC_ADMIN_KEY` env var. Real auth tracked under Epic 11.
- Exec-failure playbook content (`_bmad-output/operational-procedures/exec-failure-playbook.md`), RACI, ÖBB-sponsor signoff — all moved to E10-S3.
- Auto-expiry on disabled alert classes — known PoC limitation. Disabled classes remain disabled until manually re-enabled.
- Critical-alert bypass on kill-switch — PoC accepts all classes killable, including `severity="critical"`. Documented limitation; emergency override hierarchy out of scope.
- Backfill of historical alerts — greenfield deployment, no history exists.

### Quality gates

23. **Tests:**
    - `shared/tests/contract/test_alert_raised_compat.py` — round-trip + invalid-combo rejection (AC4).
    - `shared/tests/contract/test_inference_heartbeat.py` — round-trip + envelope strict-mode validation.
    - `inference/tests/unit/test_model_provenance.py` — four keys produced from a fixture HEF + labels file; missing `GIT_SHA` → `RuntimeError`; missing labels file → `RuntimeError`.
    - `inference/tests/unit/test_heartbeat.py` — emit cadence honoured; counter resets after emit; event-store unreachable does not crash loop.
    - `fusion/tests/unit/test_enrichment_confidence.py` — `emit_alert` requires `confidence_basis`; mypy fails when omitted (mypy-side test via `[tool.mypy.overrides]` test fixture or `pytest --mypy-only-config`).
    - `fusion/tests/unit/test_door_obstruction.py` (existing, extended) — fused-basis with `door_sensor_firmware` in `model_versions`.
    - `cloud-backend/tests/unit/test_admin_alert_classes.py` — auth (missing key → 401), empty actor → 422, disable + enable emits paired events, GET returns current state.
    - `cloud-backend/tests/integration/test_killswitch_fanout.py` — `ALERT_RAISED` with disabled `alert_code` raised AFTER `disabled_at` is filtered from `GET /api/v1/escalations` and SSE stream; in-flight escalation raised BEFORE `disabled_at` is NOT filtered.
    - `cloud-backend/tests/unit/test_confidence_thresholds.py` — config endpoint returns expected shape; every threshold has a `# CALIBRATE` comment in the source (grep test).
    - `cloud-backend/tests/unit/test_health_degraded_flag.py` — flag is false on empty, true when mean below floor, cached for 30s.
    - `cloud-backend/tests/unit/test_ai_pipeline_health.py` — per-train state rules; fleet rollup; cold-state empty response.
    - `cloud-backend/tests/integration/test_inference_heartbeat_ingest.py` — heartbeat event ingest upserts the table.
    - `control-centre/src/__tests__/ConfidenceChip.test.jsx` — three states by score; chip absent when `basis !== "model"`; numeric score never visible on chip.
    - `control-centre/src/__tests__/DegradedBanner.test.jsx` — banner shows on `ai_quality_degraded: true`; dismissible per-session; copy matches AC21 verbatim.
    - `control-centre/src/__tests__/AIPipelineRow.test.jsx` — three states by fleet_state; drawer lists per-train rows; cold-state copy.
    - `mypy --strict` zero errors in `shared/`, `inference/`, `fusion/`, `cloud-backend/`.
    - `ruff check` zero violations.
    - Coverage gate ≥80% (90% for `fusion/`) per per-package thresholds.

24. **CI grep check:** no string matching the literal value of `CC_ADMIN_KEY` appears anywhere under repo except `.env.example` (placeholder) and test fixtures (test value).

## Dependencies

- E4-S5 (inference safety/accessibility), E4-S6 (fusion alert correlation), E2-S5 (escalation acknowledge/resolve), E2-S9/E3-S6 (system health page).
- Hailo Python `pyhailort` package available in `inference` container (already present per Story 1-5-1).
- Existing `httpx` async client pattern in inference + fusion (already present).

## Deliverables

**Shared:**
- `shared/src/oebb_shared/events/payloads.py` — AlertRaisedPayload + 5 detection payloads (model_versions added) + InferenceHeartbeatPayload + ALERT_CLASS_DISABLED/REENABLED payloads.
- `shared/src/oebb_shared/events/types.py` — 3 new EventType members.
- `shared/tests/contract/test_alert_raised_compat.py`, `test_inference_heartbeat.py`.

**Inference:**
- `inference/src/inference/model_provenance.py` (new).
- `inference/src/inference/heartbeat.py` (new — 60s loop).
- Updates to `inference/src/inference/callback.py` and other emit sites for `model_versions` stamping.
- `inference/Dockerfile` — `ARG GIT_SHA` + propagation to env.
- `inference/tests/unit/test_model_provenance.py`, `test_heartbeat.py`.

**Fusion:**
- `fusion/src/fusion/enrichment.py` — `emit_alert` signature change.
- `fusion/src/fusion/door_obstruction.py`, `accessibility.py`, `health.py` (slip-fall) — call-site updates.
- `fusion/src/fusion/context_state.py` — add `door_firmware_version` field.
- `fusion/tests/unit/test_enrichment_confidence.py` (new), updates to existing handler tests.

**Cloud-backend:**
- `cloud-backend/migrations/versions/00XX_alert_class_state.py` (new).
- `cloud-backend/migrations/versions/00XX_train_inference_heartbeat.py` (new).
- `cloud-backend/src/cloud_backend/api/admin/alert_classes.py` (new router).
- `cloud-backend/src/cloud_backend/api/health.py` (updated — `ai_quality_degraded` flag).
- `cloud-backend/src/cloud_backend/api/ai_pipeline.py` (new — `/health/ai-pipeline`).
- `cloud-backend/src/cloud_backend/config/confidence_thresholds.py` (new).
- `cloud-backend/src/cloud_backend/api/config.py` (new — `/config/confidence-thresholds`).
- `cloud-backend/src/cloud_backend/services/fanout_filter.py` (new — fan-out kill-switch logic).
- `cloud-backend/src/cloud_backend/ingest/heartbeat.py` (new — heartbeat event handler).
- Updates to existing fan-out paths (REST + SSE).
- Tests per AC23.

**Control Centre:**
- `control-centre/src/components/alerts/ConfidenceChip.jsx` (new).
- `control-centre/src/components/alerts/DegradedBanner.jsx` (new).
- `control-centre/src/components/health/AIPipelineRow.jsx` (new).
- `control-centre/src/components/health/AIPipelineDrawer.jsx` (new).
- Updates to `UnifiedFeed.jsx`, `EscalationDetail.jsx`, `SystemHealth.jsx` to mount the new components.
- `control-centre/src/api/confidenceThresholds.js`, `aiPipeline.js` (new clients).
- Tests per AC23.

## Permission tier

- **Tier 3** (default permission mode required) for:
  - Shared event schema changes (`AlertRaisedPayload` + new event types).
  - Two Alembic migrations on cloud-backend (`alert_class_state`, `train_inference_heartbeat`).
  - Inference Dockerfile change (`GIT_SHA` build arg — CI variable propagation).
- **Tier 2** for the remainder (local file edits, frontend components, fusion handler updates, cloud-backend endpoints).

## Open implementation decisions deferred to dev

- Per-handler fusion migration order: recommend `door_obstruction.py` first (most established test coverage), then `accessibility.py`, then slip-fall in `health.py`.
- Heartbeat event retention: covered by existing TimescaleDB retention policy (90-day chunk drop) — no separate policy needed.
- `EscalationDetail.jsx` "Model details" section placement — Freya to spec in design review before merge.

## Known limitations (documented in operational notes)

- No auto-expiry on disabled alert classes (PoC scope).
- All alert classes killable including critical (PoC scope; emergency override deferred).
- Confidence thresholds require code deploy to change (mutability deferred to Epic 11).
- Kill-switch operated by Nomad on-call via curl during PoC (UI deferred to Epic 11).
- "Degraded" banner copy includes "Nomad has been notified" — Saga flagged this still leaks Nomad-shaped vocabulary into ÖBB's surface. WDS Phase 4 review item before pilot.
