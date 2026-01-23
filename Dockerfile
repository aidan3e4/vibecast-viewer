# Multi-stage build for Reolink Camera Clients Service
FROM python:3.13-slim as builder

ARG DEBIAN_FRONTEND=noninteractive

# # Install build tools only (runtime libs will be in final stage)
# RUN apt-get update && apt-get install -y --no-install-recommends \
#     # gcc \
#     # g++ \
#     && rm -rf /var/lib/apt/lists/*

# Copy uv from official image
COPY --from=ghcr.io/astral-sh/uv:latest /uv /uvx /bin/

# Set working directory
WORKDIR /app

# Copy and install dependencies
COPY pyproject.toml uv.lock README.md ./
ENV UV_PROJECT_ENVIRONMENT=/usr/local
RUN uv sync --frozen --no-dev --no-cache

# Final stage
FROM python:3.13-slim as runtime

# Install runtime dependencies for OpenCV
RUN apt-get update && apt-get install -y --no-install-recommends \
    libglib2.0-0 \
    libsm6 \
    libxext6 \
    libxrender1 \
    libgomp1 \
    libgl1 \
    make \
    && rm -rf /var/lib/apt/lists/*

# Set working directory
WORKDIR /app

# Copy installed packages from builder
COPY --from=builder /usr/local/lib/python3.13/site-packages /usr/local/lib/python3.13/site-packages
COPY --from=builder /usr/local/bin /usr/local/bin

# Copy application code
COPY reolinkapi/ ./reolinkapi/
COPY vision_llm/ ./vision_llm/
COPY app/ ./app/
COPY ftp_server/ ./ftp_server/
COPY pyproject.toml constants.py Makefile ./

# Copy entrypoint script
COPY entrypoint.sh ./
RUN chmod +x ./entrypoint.sh

# Create data directory for output
RUN mkdir -p ./data

# Set environment variables
ENV PYTHONUNBUFFERED=1
ENV PYTHONPATH=/app

# Run as non-root user for security
RUN useradd -m -u 1000 camera && chown -R camera:camera /app
USER camera

# Expose ports
EXPOSE 2121 8001

# Run the entrypoint script
CMD ["./entrypoint.sh"]

