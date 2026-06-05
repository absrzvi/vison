# inference — Hailo-8 detection + tracking container
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
# inference MUST use this base — hailort bindings and TAPPAS GStreamer plugins
# (hailonet, hailofilter, hailotracker) cannot be pip-installed from PyPI.
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

# Install inference package.
COPY inference/pyproject.toml .
COPY inference/src/ src/
RUN pip install --no-cache-dir -e .

# Volume-mount targets — .hef model and cameras.json are never baked into the image.
# Wire the mounts in docker-compose.onboard.yml (story 1-5-3).
# Required runtime volumes:
#   /models  — bind-mount yolox_s_leaky.hef here (INFERENCE_MODEL_HEF_PATH)
#   /config  — bind-mount cameras.json here (INFERENCE_CAMERAS_JSON_PATH)
# Required runtime env vars (not in this file — provide in docker-compose or --env):
#   INFERENCE_EVENT_STORE_API_KEY  — X-API-Key for event-store /api/v1/* endpoints
#   INFERENCE_VEHICLE_ID           — e.g. OBB-4711 (overrides OBB-TEST default)
#   INFERENCE_JOURNEY_ID           — set by vlan-pollers via POST /context
# Required host device (in docker-compose.onboard.yml, story 1-5-3):
#   /dev/hailo0  — Hailo-8 M.2 PCIe device (--device=/dev/hailo0 --group-add video)
RUN mkdir -p /models /config
VOLUME ["/models", "/config"]

# Documented env-var defaults for mount paths.
# All other runtime config (event_store_url, fusion_url, vehicle_id, journey_id, etc.)
# is provided at container startup via docker-compose env or --env flags.
# Do NOT override GST_PLUGIN_PATH here — the Hailo base image sets it correctly.
ENV INFERENCE_MODEL_HEF_PATH=/models/yolox_s_leaky.hef \
    INFERENCE_CAMERAS_JSON_PATH=/config/cameras.json

# Context-push port (health + /context endpoint for vlan-pollers journey_id push).
# uvicorn binds 0.0.0.0 so vlan-pollers can reach /context from sibling containers.
EXPOSE 8081

# main.py starts GStreamer on a daemon thread then runs uvicorn on the asyncio loop.
# Do NOT replace with `uvicorn inference.health:build_app ...` —
# build_app is a factory that requires runtime arguments provided by main().
CMD ["python", "-m", "inference.main"]
