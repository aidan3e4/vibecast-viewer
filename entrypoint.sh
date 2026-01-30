#!/bin/bash
set -e

echo "Starting Vibecast Viewer..."
echo "Port: ${PORT:-8001}"

exec uvicorn app.main:app --host 0.0.0.0 --port "${PORT:-8001}"
