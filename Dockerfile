# ═══════════════════════════════════════════════════════════════════════
# CodeDebt Guardian — Multi-stage Docker Build
# Optimized for production: non-root user, minimal image, layer caching.
# ═══════════════════════════════════════════════════════════════════════

# ── Stage 1: Build dependencies ──────────────────────────────────────
FROM python:3.12-slim AS builder

WORKDIR /build

# System deps for building (psycopg2, bcrypt, etc.)
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    libpq-dev \
    && rm -rf /var/lib/apt/lists/*

COPY requirements.txt .
RUN pip install --no-cache-dir --prefix=/install -r requirements.txt


# ── Stage 2: Production image ────────────────────────────────────────
FROM python:3.12-slim AS production

# Security: non-root user
RUN groupadd -r codedebt && useradd -r -g codedebt codedebt

# Runtime deps only
RUN apt-get update && apt-get install -y --no-install-recommends \
    libpq5 \
    curl \
    && rm -rf /var/lib/apt/lists/*

# Copy installed packages
COPY --from=builder /install /usr/local

WORKDIR /app

# Copy application code
COPY . .

# Ensure __init__ files exist
RUN touch api/__init__.py \
    && touch api/routes/__init__.py \
    && touch models/__init__.py \
    && touch workers/__init__.py \
    && touch services/__init__.py \
    && touch tools/__init__.py \
    && touch agents/__init__.py

# Set ownership
RUN chown -R codedebt:codedebt /app

USER codedebt

# Health check
HEALTHCHECK --interval=30s --timeout=5s --start-period=10s --retries=3 \
    CMD curl -f http://localhost:8000/health/live || exit 1

EXPOSE 8000
ENV PYTHONUNBUFFERED=1

# Default: run the API server
CMD ["uvicorn", "api.main:app", "--host", "0.0.0.0", "--port", "8000", "--workers", "4"]
