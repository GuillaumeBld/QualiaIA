# QualiaIA Dockerfile
# Multi-stage build for optimized production image

# ============================================
# Stage 1: Builder
# ============================================
FROM python:3.11-slim as builder

WORKDIR /app

# Install build dependencies
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    curl \
    && rm -rf /var/lib/apt/lists/*

# Install Python dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir --user -r requirements.txt

# ============================================
# Stage 2: Production
# ============================================
FROM python:3.11-slim as production

WORKDIR /app

# Create non-root user
RUN groupadd -r qualiaIA && useradd -r -g qualiaIA qualiaIA

# Copy Python packages from builder
COPY --from=builder /root/.local /home/qualiaIA/.local

# Copy application
COPY src/ ./src/
COPY config/ ./config/

# Create directories
RUN mkdir -p logs data && chown -R qualiaIA:qualiaIA /app

# Switch to non-root user
USER qualiaIA

# Environment
ENV PATH=/home/qualiaIA/.local/bin:$PATH
ENV PYTHONPATH=/app
ENV PYTHONUNBUFFERED=1

# Expose ports
EXPOSE 8080 9090

# Health check
HEALTHCHECK --interval=30s --timeout=10s --start-period=5s --retries=3 \
    CMD curl -f http://localhost:8080/health || exit 1

# Default command
CMD ["python", "-m", "src.main"]

# ============================================
# Alternative: API mode
# ============================================
# CMD ["uvicorn", "src.api:app", "--host", "0.0.0.0", "--port", "8080"]
