# NanoCoop Core Backend Container
FROM python:3.12-slim

ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    NANOCOOP_DB_PATH=/data/nanocoop.db \
    NANOCOOP_PORT=8000 \
    NANOCOOP_HOST=0.0.0.0

WORKDIR /app

# Install curl and uv
RUN apt-get update && apt-get install -y --no-install-recommends curl ca-certificates \
    && rm -rf /var/lib/apt/lists/* \
    && pip install --no-cache-dir uv

# Create non-root user and data volume
RUN useradd -u 1001 -m -s /bin/bash nanocoop \
    && mkdir -p /data /app \
    && chown -R nanocoop:nanocoop /data /app

# Copy dependency files
COPY pyproject.toml requirements.txt README.md /app/
RUN uv venv --python 3.12 && uv pip install -e ".[dev]"

# Copy source code and tests
COPY app/ /app/app/
COPY tests/ /app/tests/

RUN chown -R nanocoop:nanocoop /app
USER nanocoop

VOLUME ["/data"]

EXPOSE 8000

HEALTHCHECK --interval=5s --timeout=3s --retries=5 \
    CMD curl -f http://localhost:8000/health || exit 1

CMD ["uv", "run", "uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
