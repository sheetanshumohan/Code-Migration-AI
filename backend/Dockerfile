# syntax=docker/dockerfile:1
# ==============================================================================
# CodeMorph AI Backend Dockerfile
# Python 3.12 Production Image - Multi-stage, Non-Root, BuildKit-Optimized
# ==============================================================================

# Stage 1: Build dependencies
FROM python:3.12-slim AS builder

RUN rm -f /etc/apt/apt.conf.d/docker-clean; echo 'Binary::apt::APT::Keep-Downloaded-Packages "true";' > /etc/apt/apt.conf.d/keep-cache
RUN --mount=type=cache,target=/var/cache/apt,sharing=locked \
    --mount=type=cache,target=/var/lib/apt,sharing=locked \
    apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    curl \
    git \
    libpq-dev \
    gcc \
    pkg-config

WORKDIR /build

# Install requirements into a virtual environment with pip cache
RUN python -m venv /opt/venv
ENV PATH="/opt/venv/bin:$PATH"

COPY requirements.txt .
RUN --mount=type=cache,target=/root/.cache/pip \
    pip install --upgrade pip uv && \
    uv pip install -r requirements.txt

# Stage 2: Production runtime
FROM python:3.12-slim

# Install runtime dependencies and standalone Docker CLI client (no heavy daemon/systemd)
RUN rm -f /etc/apt/apt.conf.d/docker-clean; echo 'Binary::apt::APT::Keep-Downloaded-Packages "true";' > /etc/apt/apt.conf.d/keep-cache
RUN --mount=type=cache,target=/var/cache/apt,sharing=locked \
    --mount=type=cache,target=/var/lib/apt,sharing=locked \
    apt-get update && apt-get install -y --no-install-recommends \
    curl \
    git \
    ripgrep \
    libpq5 \
    ca-certificates \
    && curl -fsSL https://download.docker.com/linux/static/stable/x86_64/docker-27.5.1.tgz | tar -xzC /usr/local/bin --strip-components=1 docker/docker \
    && chmod +x /usr/local/bin/docker

# Create non-root user
RUN useradd -m -s /bin/bash appuser

WORKDIR /app

# Copy virtual environment from builder
COPY --from=builder /opt/venv /opt/venv
ENV PATH="/opt/venv/bin:$PATH"

# Copy backend application source (respecting .dockerignore)
COPY . .

# Create workspace sandboxes directory and set permissions
RUN mkdir -p /app/data/workspace_sandboxes && \
    sed -i 's/\r$//' /app/entrypoint.sh && \
    chmod +x /app/entrypoint.sh && \
    chown -R appuser:appuser /app

# Set non-root user
USER appuser

EXPOSE 8000

CMD ["/app/entrypoint.sh"]
