FROM python:3.11-slim-bookworm

WORKDIR /app

# Install shared package (editable) then fusion. Mirrors inference/ Dockerfile pattern.
COPY shared /shared
RUN pip install --no-cache-dir -e /shared

COPY fusion/pyproject.toml /app/pyproject.toml
COPY fusion/src /app/src
RUN pip install --no-cache-dir -e .

ENV FUSION_HOST=0.0.0.0 \
    FUSION_PORT=8090

EXPOSE 8090

CMD ["python", "-m", "fusion.main"]
