# Multi-stage Dockerfile for Backend (FastAPI) & Frontend (Vite) Production Builds

# === Stage 1: Build Frontend ===
FROM node:18-alpine AS frontend-builder
WORKDIR /app/frontend
COPY frontend/package*.json ./
RUN npm ci
COPY frontend/ ./
RUN npm run build

# === Stage 2: Python Backend & Final Image ===
FROM python:3.11-slim AS runner

WORKDIR /app

# Install system dependencies
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    curl \
    && rm -rf /var/lib/apt/lists/*

# Copy backend requirements
COPY backend/requirements.txt ./backend/requirements.txt
RUN pip install --no-cache-dir -r backend/requirements.txt

# Copy backend application code
COPY backend/ ./backend

# Copy built static frontend assets to serve or deliver via Nginx/FastAPI
COPY --from=frontend-builder /app/frontend/dist ./frontend/dist

ENV ENV=production \
    PORT=8000 \
    PYTHONPATH=/app

EXPOSE 8000

CMD ["python", "-m", "backend.main"]