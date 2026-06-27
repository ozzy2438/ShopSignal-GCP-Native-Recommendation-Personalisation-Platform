# ─────────────────────────────────────────────────────────────────────────────
# ShopSignal API — Dockerfile
# Multi-stage build:  builder installs deps, runtime is a lean final image.
# ─────────────────────────────────────────────────────────────────────────────

# ── Stage 1: builder ─────────────────────────────────────────────────────────
FROM python:3.11-slim AS builder

WORKDIR /build

# Install build tools
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    && rm -rf /var/lib/apt/lists/*

# Copy dependency files first (layer-cache optimisation)
COPY requirements.txt .

# Install into a prefix so we can copy them cleanly to the final stage
RUN pip install --no-cache-dir --prefix=/install -r requirements.txt

# ── Stage 2: runtime ─────────────────────────────────────────────────────────
FROM python:3.11-slim AS runtime

# Create a non-root user for security
RUN useradd --create-home --shell /bin/bash appuser

WORKDIR /app

# Copy installed packages from builder
COPY --from=builder /install /usr/local

# Copy application source
COPY src/ ./src/
COPY pyproject.toml .

# Ownership
RUN chown -R appuser:appuser /app
USER appuser

# Build-time arguments injected by CI/CD
ARG APP_VERSION=0.1.0
ARG BUILD_DATE

# Cloud Run expects the server on PORT env var (default 8080)
ENV APP_VERSION=${APP_VERSION} \
    BUILD_DATE=${BUILD_DATE} \
    API_HOST=0.0.0.0 \
    API_PORT=8080 \
    APP_ENV=production \
    LOG_LEVEL=INFO \
    PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1

EXPOSE 8080

# Health check — Cloud Run uses /health
HEALTHCHECK --interval=30s --timeout=5s --start-period=10s --retries=3 \
    CMD python -c "import urllib.request; urllib.request.urlopen('http://localhost:8080/health')"

# Entry point
CMD ["python", "-m", "uvicorn", "src.serve.app:app", \
     "--host", "0.0.0.0", "--port", "8080", "--workers", "1"]
