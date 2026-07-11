#!/bin/bash
# Launch backend (FastAPI) and frontend (Vite) dev servers together.
set -e
cd "$(dirname "$0")"

trap 'kill 0' EXIT

(cd backend && .venv/bin/uvicorn app.main:app --reload --port 8000) &
(cd frontend && npm run dev) &

wait
