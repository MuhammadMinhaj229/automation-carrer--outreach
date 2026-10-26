FROM python:3.11-slim

WORKDIR /app

# Install system dependencies (build-essential for compiling if needed)
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    curl \
    && rm -rf /var/lib/apt/lists/*

# Copy python dependencies
COPY requirements.txt pyproject.toml ./
RUN pip install --no-cache-dir -r requirements.txt

# Copy codebase
COPY . .

# Expose backend port
EXPOSE 8000

# Health check
HEALTHCHECK --interval=30s --timeout=5s --start-period=5s --retries=3 \
    CMD curl -fsS "http://localhost:${PORT:-8000}/healthz" || exit 1

# Default command
CMD ["sh", "-c", "exec python -m uvicorn acios.api:app --host 0.0.0.0 --port \"${PORT:-8000}\""]
