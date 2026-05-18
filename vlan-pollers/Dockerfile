FROM python:3.11-slim-bookworm

WORKDIR /app

COPY pyproject.toml .
RUN pip install --no-cache-dir -e .

COPY src/ src/

ENV PYTHONPATH=/app/src:/app/shared_src

CMD ["python", "-m", "vlan_pollers.main"]
