FROM python:3.11-slim

WORKDIR /app

COPY shared/src/oebb_shared shared_src/oebb_shared
COPY shared/pyproject.toml shared_src/pyproject.toml
RUN pip install --no-cache-dir ./shared_src

COPY cloud-backend/pyproject.toml .
COPY cloud-backend/src/ src/
COPY cloud-backend/migrations/ migrations/

RUN pip install --no-cache-dir -e .

EXPOSE 8002

CMD ["uvicorn", "cloud_backend.main:app", "--host", "0.0.0.0", "--port", "8002"]
