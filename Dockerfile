# Starfish Nifty 50 Dashboard - Production Dockerfile
FROM python:3.11-slim

# Set environment variables
ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1

# Set working directory
WORKDIR /app

# Install system dependencies
RUN apt-get update && apt-get install -y --no-install-recommends \
    gcc \
    libpq-dev \
    curl \
    && rm -rf /var/lib/apt/lists/*

# Copy requirements and install Python dependencies
COPY pyproject.toml .
RUN pip install --no-cache-dir -e .

# Copy application code
COPY analytics/ /app/analytics/
COPY api/ /app/api/
COPY dashboard/ /app/dashboard/
COPY config/ /app/config/
COPY ingestion/ /app/ingestion/
COPY scheduler/ /app/scheduler/
COPY sql/ /app/sql/
COPY data/ /app/data/ 2>/dev/null || true

# Create non-root user for security
RUN useradd --create-home -s /bin/bash appuser && \
    chown -R appuser:appuser /app
USER appuser

# Expose ports
EXPOSE 8000 8501

# Health check
HEALTHCHECK --interval=30s --timeout=10s --start-period=5s --retries=3 \
    CMD curl -f http://localhost:8000/health || exit 1

# Default command runs both API and dashboard
CMD ["sh", "-c", "uvicorn api.main:app --host 0.0.0.0 --port 8000 & \
    streamlit run dashboard/app.py --server.port 8501 --server.address 0.0.0.0 & \
    wait -n"]