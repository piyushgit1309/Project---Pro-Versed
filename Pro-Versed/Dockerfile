# ==============================================================================
# PRO-VERSED — Production Container Definition
# Optimized Python 3.11 Slim Image for Cloud & Container Deployments
# ==============================================================================
FROM python:3.11-slim

# Set environment variables
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PROVERSED_DB_PATH=/tmp/proversed.db \
    PORT=8000 \
    HOST=0.0.0.0

# Set working directory
WORKDIR /app

# Install minimal OS dependencies for compilation and healthchecks
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    curl \
    sqlite3 \
    && rm -rf /var/lib/apt/lists/*

# Install Python dependencies
COPY backend/requirements.txt /app/backend/requirements.txt
COPY requirements.txt /app/requirements.txt
RUN pip install --no-cache-dir -r /app/backend/requirements.txt

# Copy codebase
COPY backend/ /app/backend/
COPY frontend/ /app/frontend/
COPY main.py /app/main.py

# Expose standard port
EXPOSE 8000

# Health check probe
HEALTHCHECK --interval=30s --timeout=5s --start-period=5s --retries=3 \
    CMD curl -f http://localhost:${PORT:-8000}/health || exit 1

# Start FastAPI Application
CMD ["sh", "-c", "uvicorn backend.main:app --host 0.0.0.0 --port ${PORT:-8000}"]
