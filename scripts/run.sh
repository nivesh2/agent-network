#!/usr/bin/env bash
# Run both the FastAPI backend and React frontend in parallel.
# Usage: ./scripts/run.sh

set -e

ROOT="$(cd "$(dirname "$0")/.." && pwd)"

cleanup() {
  echo ""
  echo "Shutting down..."
  kill $BACKEND_PID $FRONTEND_PID 2>/dev/null
  wait $BACKEND_PID $FRONTEND_PID 2>/dev/null
  echo "Done."
}
trap cleanup EXIT INT TERM

# ── Backend ────────────────────────────────────────────────────────────────
echo "Starting backend (uvicorn) on http://localhost:8000 ..."
cd "$ROOT"
uvicorn api:app --host 0.0.0.0 --port 8000 --reload &
BACKEND_PID=$!

# ── Frontend ───────────────────────────────────────────────────────────────
echo "Starting frontend (vite) on http://localhost:5173 ..."
cd "$ROOT/frontend"
npm run dev &
FRONTEND_PID=$!

echo ""
echo "Both services running. Press Ctrl+C to stop."
wait
