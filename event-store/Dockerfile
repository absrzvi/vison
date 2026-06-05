FROM python:3.11-slim

WORKDIR /app

COPY shared/src/oebb_shared shared_src/src/oebb_shared
COPY shared/pyproject.toml shared_src/pyproject.toml
RUN pip install --no-cache-dir ./shared_src

COPY event-store/pyproject.toml .
COPY event-store/src/ src/

RUN pip install --no-cache-dir -e .

VOLUME ["/data"]

EXPOSE 8001

CMD ["uvicorn", "event_store.main:app", "--host", "0.0.0.0", "--port", "8001"]
