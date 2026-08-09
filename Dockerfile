# INFRA-AGAIN Backend Dockerfile — Fly.io Deployment
FROM python:3.11-slim

WORKDIR /app

# Install system deps
RUN apt-get update && apt-get install -y --no-install-recommends \
    curl ca-certificates \
    && rm -rf /var/lib/apt/lists/*

# Install OpenTofu
RUN curl -fsSL https://get.opentofu.org/install-opentofu.sh | sh && \
    mv tofu /usr/local/bin/

# Install Python deps
COPY pyproject.toml .
RUN pip install --no-cache-dir -e ".[dev]" && \
    pip install --no-cache-dir fastapi uvicorn

# Copy source
COPY src/ src/
COPY README.md .

# Create data directory
RUN mkdir -p /data

EXPOSE 8080

CMD ["uvicorn", "infra_again.api:app", "--host", "0.0.0.0", "--port", "8080"]
