# ─── Build stage ─────────────────────────────────────────────
FROM python:3.11-slim AS builder

WORKDIR /app

# Install build deps (needed for some Python packages)
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    libpq-dev \
    && rm -rf /var/lib/apt/lists/*

COPY requirements.txt .
RUN pip install --no-cache-dir --prefix=/install -r requirements.txt

# ─── Runtime stage ────────────────────────────────────────────
FROM python:3.11-slim AS runtime

WORKDIR /app

# Runtime system deps only
RUN apt-get update && apt-get install -y --no-install-recommends \
    libpq5 curl \
    && rm -rf /var/lib/apt/lists/*

# Copy installed packages from builder to system site-packages
COPY --from=builder /install /usr/local

# Copy application source
COPY app/ ./app/

# Create data directories
RUN mkdir -p ./data/faiss_indexes

# Non-root user for security
RUN useradd -m -u 1001 documind && chown -R documind:documind /app
USER documind

ENV PYTHONPATH=/app
ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1

EXPOSE 8000

HEALTHCHECK --interval=30s --timeout=10s --retries=3 \
    CMD curl -f http://localhost:${PORT:-8000}/health || exit 1

# Uvicorn with 2 workers for production concurrency
# WebSocket connections require --ws websockets (included via uvicorn[standard])
# Shell form allows $PORT expansion (Render injects PORT dynamically)
CMD uvicorn app.main:app --host 0.0.0.0 --port ${PORT:-8000} --workers 2
