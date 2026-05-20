FROM python:3.11-slim-bookworm

WORKDIR /app

# Install shared package (editable) then cloud-sync.
COPY shared /shared
RUN pip install --no-cache-dir -e /shared

COPY cloud-sync/pyproject.toml /app/pyproject.toml
COPY cloud-sync/src /app/src
RUN pip install --no-cache-dir -e .

# Default writable buffer location; mount a host path in production.
RUN mkdir -p /var/lib/cloud-sync

ENV CLOUD_SYNC_HOST=0.0.0.0 \
    CLOUD_SYNC_PORT=8082 \
    CLOUD_SYNC_QUEUE_DB_PATH=/var/lib/cloud-sync/queue.db

EXPOSE 8082

CMD ["python", "-m", "cloud_sync.main"]
