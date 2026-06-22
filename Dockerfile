FROM python:3.11-slim

LABEL maintainer="VaultWatch <dev@vaultwatch.io>"
LABEL description="VaultWatch — DeFi Risk Intelligence on Casper"
LABEL version="4.0.0"

# System deps
RUN apt-get update && apt-get install -y --no-install-recommends \
    curl \
    build-essential \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

# Copy requirements first (Docker cache layer)
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy project
COPY . .

# Install SDK in editable mode
RUN pip install --no-cache-dir -e sdk/

# Create non-root user
RUN useradd -m -u 1000 vaultwatch && chown -R vaultwatch:vaultwatch /app
USER vaultwatch

# Expose API port
EXPOSE 8000

# Environment defaults
ENV PYTHONUNBUFFERED=1
ENV PYTHONPATH=/app
ENV CASPER_MOCK=true

# Health check
HEALTHCHECK --interval=30s --timeout=10s --start-period=5s --retries=3 \
    CMD curl -f http://localhost:8000/health || exit 1

# Default: run the API
CMD ["uvicorn", "api.main:app", "--host", "0.0.0.0", "--port", "8000", "--workers", "2"]
