#!/bin/sh
# Docker container entry point
# Run generate_secret.py first (exits immediately if JWT_SECRET is already in the environment)
# then starts the ASGI server with the appropriate settings

set -e

echo "[Entrypoint] Running generate_secret.py to ensure JWT_SECRET is set"
python generate_secret.py

if [ "$APP_ENV" = "production" ]; then
    echo "[Entrypoint] Starting ASGI server in production mode"
    exec uvicorn main:app --host 0.0.0.0 --port 8000 --workers 2
else
    echo "[Entrypoint] Starting ASGI server in development mode with auto-reload"
    exec uvicorn main:app --host 0.0.0.0 --port 8000 --reload
fi