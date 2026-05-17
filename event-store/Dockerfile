FROM python:3.11-slim

WORKDIR /app

COPY ../shared/src /app/shared_src
RUN pip install --no-cache-dir /app/shared_src/../..

COPY pyproject.toml .
COPY src/ src/
COPY schema.sql .

RUN pip install --no-cache-dir -e .

VOLUME ["/data"]

EXPOSE 8001

CMD ["uvicorn", "event_store.main:app", "--host", "0.0.0.0", "--port", "8001"]
