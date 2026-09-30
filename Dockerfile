# syntax=docker/dockerfile:1

################################################################################
# Stage 1: Frontend Build (Next.js 16 + React 19)
################################################################################
FROM node:20-alpine AS frontend-builder
WORKDIR /app/frontend

# Install dependencies with frozen lockfile
COPY frontend/package.json frontend/package-lock.json ./
RUN npm ci

# Copy source and build static/production output
COPY frontend/ ./
ENV NEXT_TELEMETRY_DISABLED=1
ARG NEXT_PUBLIC_API_URL=http://localhost:8000
ENV NEXT_PUBLIC_API_URL=${NEXT_PUBLIC_API_URL}

RUN npm run build

################################################################################
# Stage 2: Backend Runtime & Native Clang++ Sandbox
################################################################################
FROM python:3.11-slim-bookworm AS backend

ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    DEBIAN_FRONTEND=noninteractive \
    PORT=8000 \
    LANG=C.UTF-8 \
    LC_ALL=C.UTF-8

# Install LLVM / Clang++ toolchain (clang, clang++, lld, libclang-dev) and build tools
RUN apt-get update && apt-get install -y --no-install-recommends \
    clang \
    lld \
    libclang-dev \
    build-essential \
    curl \
    ca-certificates \
    && clang++ --version \
    && rm -rf /var/lib/apt/lists/*

# Create unprivileged sandbox user for isolated user code execution
RUN groupadd -g 1001 algolens && \
    useradd -u 1001 -g algolens -m -s /bin/bash algolens-sandbox

# Setup application working directory
WORKDIR /app/backend

# Create compilation cache and scratch spaces with strict permissions
RUN mkdir -p /tmp/.build_cache /app/backend/.build_cache && \
    chown -R algolens-sandbox:algolens /tmp/.build_cache /app/backend/.build_cache && \
    chmod 777 /tmp/.build_cache /app/backend/.build_cache

# Install Python backend dependencies
COPY backend/requirements.txt /app/backend/
RUN pip install --no-cache-dir -r requirements.txt

# Copy backend source code
COPY backend/ /app/backend/

# Ensure appropriate ownership
RUN chown -R algolens-sandbox:algolens /app/backend

# Expose backend API port
EXPOSE 8000

# Health check endpoint
HEALTHCHECK --interval=20s --timeout=5s --start-period=5s --retries=3 \
    CMD curl -f http://localhost:8000/api/version || exit 1

# Start Uvicorn FastAPI server
CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8000"]
