# ── Stage 1: Build React frontend ─────────────────────────────────────────
FROM node:20-alpine AS frontend

WORKDIR /frontend
COPY package*.json ./
RUN npm ci --silent
COPY . .
RUN npm run build

# ── Stage 2: Python backend + built frontend ───────────────────────────────
FROM python:3.11-slim

WORKDIR /app

RUN apt-get update && apt-get install -y --no-install-recommends \
    curl \
    libnss3 libnspr4 libatk1.0-0 libatk-bridge2.0-0 libcups2 \
    libdrm2 libxkbcommon0 libxcomposite1 libxdamage1 libxfixes3 \
    libxrandr2 libgbm1 libasound2 libpango-1.0-0 libcairo2 \
    libx11-6 libxcb1 libxext6 fonts-liberation fonts-unifont \
    && rm -rf /var/lib/apt/lists/*

COPY backend/requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Install chromium without --with-deps (deps already installed above)
RUN playwright install chromium

# Copy backend source
COPY backend/ .
COPY apps/ ./apps

# Copy React build output into backend dist/
COPY --from=frontend /frontend/dist ./dist

# Copy Chrome extension zip (served as static download)
COPY chrome-extension-v2.zip ./chrome-extension-v2.zip

EXPOSE 8000
CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8000"]
