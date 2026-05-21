# rtsp-ingest — RTSP camera ingestion + priority scheduling container
#
# Base image: Hailo Software Suite (HailoRT 4.23 + TAPPAS 5.1.0).
# Available from the Hailo Developer Zone registry:
#   https://hailo.ai/developer-zone/
#
# On a standard dev machine without access to the Hailo registry this build
# will fail at the FROM pull step. Substitute a local stub image via:
#   docker build --build-arg HAILO_BASE=my-local-stub:latest .
#
# All other onboard/landside containers use python:3.11-slim-bookworm.
# rtsp-ingest MUST use this base — GStreamer RTSP source plugins (rtspsrc,
# rtph264depay, avdec_h264) and TAPPAS integration are pre-installed here
# and cannot be pip-installed from PyPI.
#
# SECURITY NOTE (PoC): Container runs as root. Hailo device permissions on the
# R5001C SYS2 must be validated on first hardware bring-up day before adding
# a non-root USER with video/render group membership.
#
# SECURITY NOTE (PoC): POST /context is protected by VLAN isolation (VLAN 5/7/8)
# rather than token auth. Upgrade to X-API-Key auth at fleet rollout.

ARG HAILO_BASE=hailo-software-suite:4.23
FROM ${HAILO_BASE}

WORKDIR /app

# Assert Python 3.11 is the active interpreter. hailo-software-suite:4.23 bundles
# Python 3.11, but this guard catches version drift on base image updates.
RUN python --version 2>&1 | grep -q "Python 3.11" || \
    (echo "ERROR: expected Python 3.11, got $(python --version 2>&1)" && exit 1)

# Install oebb-shared (two-step pattern used by all containers in this monorepo).
# Build context is the monorepo root.
COPY shared/src/oebb_shared shared_src/src/oebb_shared
COPY shared/pyproject.toml shared_src/pyproject.toml
RUN pip install --no-cache-dir ./shared_src

# Install rtsp-ingest package.
COPY rtsp-ingest/pyproject.toml .
COPY rtsp-ingest/src/ src/
RUN pip install --no-cache-dir -e .

# Volume-mount target — cameras.json is never baked into the image.
# Wire the mount in docker-compose.onboard.yml (story 1-5-3).
# Required runtime volume:
#   /config  — bind-mount cameras.json here (RTSP_INGEST_CAMERAS_JSON_PATH)
# Required runtime env vars (not in this file — provide in docker-compose or --env):
#   RTSP_INGEST_VEHICLE_ID  — e.g. OBB-4711 (overrides OBB-TEST default)
#   RTSP_INGEST_EVENT_STORE_URL  — e.g. http://event-store:8000
RUN mkdir -p /config
VOLUME ["/config"]

# Documented env-var default for cameras.json mount path.
# All other runtime config (event_store_url, vehicle_id, tops_budget_pct_threshold, etc.)
# is provided at container startup via docker-compose env or --env flags.
# Do NOT override GST_PLUGIN_PATH here — the Hailo base image sets it correctly.
ENV RTSP_INGEST_CAMERAS_JSON_PATH=/config/cameras.json

# Context-push port (health + /context endpoint for vlan-pollers journey_id / door-release push).
# uvicorn binds 0.0.0.0 so vlan-pollers can reach /context from sibling containers.
EXPOSE 8080

# main.py module-level code initialises Scheduler, Gate, Pipeline, and the FastAPI app object.
# uvicorn serves rtsp_ingest.main:app directly — no custom entry-point wrapper needed.
CMD ["python", "-m", "uvicorn", "rtsp_ingest.main:app", "--host", "0.0.0.0", "--port", "8080"]
