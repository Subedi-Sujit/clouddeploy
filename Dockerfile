# ============================================================
# Stage 1: Builder
# We install dependencies into a virtual environment in this stage.
# This keeps build tools out of the final image.
# ============================================================
FROM python:3.12-slim AS builder

WORKDIR /app

# Install build dependencies needed for psycopg2 compilation
RUN apt-get update && apt-get install -y --no-install-recommends \
    gcc \
    libpq-dev \
    && rm -rf /var/lib/apt/lists/*

# Create a virtual environment
RUN python -m venv /opt/venv
ENV PATH="/opt/venv/bin:$PATH"

# Install Python dependencies into the venv
COPY app/requirements.txt .
RUN pip install --no-cache-dir --upgrade pip && \
    pip install --no-cache-dir -r requirements.txt


# ============================================================
# Stage 2: Runtime
# Final image only contains what's needed to RUN the app.
# Smaller image = faster pulls, smaller attack surface.
# ============================================================
FROM python:3.12-slim

# Install only the runtime library needed for psycopg2
RUN apt-get update && apt-get install -y --no-install-recommends \
    libpq5 \
    && rm -rf /var/lib/apt/lists/* \
    && apt-get clean

# Create a non-root user. Running as root inside a container is a security risk.
RUN groupadd -r appuser && useradd -r -g appuser appuser

WORKDIR /app

# Copy the venv from the builder stage
COPY --from=builder /opt/venv /opt/venv
ENV PATH="/opt/venv/bin:$PATH"

# Copy application code
COPY --chown=appuser:appuser app/ ./app/

# Drop to non-root user
USER appuser

EXPOSE 5000

# Healthcheck for container orchestrators
HEALTHCHECK --interval=30s --timeout=3s --start-period=10s --retries=3 \
    CMD python -c "import urllib.request; urllib.request.urlopen('http://localhost:5000/health')" || exit 1

# Use gunicorn (a real WSGI server) instead of Flask's dev server
CMD ["gunicorn", "--bind", "0.0.0.0:5000", "--workers", "2", "--access-logfile", "-", "app.main:app"]
