#!/bin/bash
set -e
cd "$(dirname "$0")"

echo "▶ Build frontend..."
npm run build

echo "▶ Build Docker image..."
docker build -t autopilot:latest .

echo "▶ Deployando serviços..."
docker service update --force autonavegador_autopilot_api
docker service update --force autonavegador_autopilot_worker

echo "✓ Deploy concluído"
