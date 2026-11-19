#!/usr/bin/env bash
# P0-26 smoke e2e runner. Brings up a disposable SQLite stack (school API,
# controller API, both web apps), seeds it, runs the Playwright smoke test and
# tears everything down again.
#
#   ./e2e/run.sh                 # fresh stack on the standard dev ports
#   E2E_EXTERNAL=1 ./e2e/run.sh  # use a stack already started by scripts/dev.sh
set -uo pipefail
set -m

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT" || exit 1

DATA_DIR="$ROOT/data/e2e"
LOG_DIR="$DATA_DIR/logs"
PID_DIR="$DATA_DIR/pids"

PYTHON="$ROOT/.venv/bin/python"
if [ ! -x "$PYTHON" ]; then
  echo "e2e: $PYTHON is missing; run 'uv sync --all-packages' first" >&2
  exit 1
fi

PNPM=(pnpm)
if ! command -v pnpm >/dev/null 2>&1; then
  PNPM=(node "$HOME/.local/lib/node_modules/pnpm/bin/pnpm.cjs")
fi

port_busy() {
  (exec 3<>"/dev/tcp/127.0.0.1/$1") 2>/dev/null && exec 3>&- && return 0
  return 1
}

EXTERNAL="${E2E_EXTERNAL:-0}"
if [ "$EXTERNAL" = "1" ]; then
  echo "e2e: using the already-running dev stack"
else
  for port in 8000 8100 5173 5174; do
    if port_busy "$port"; then
      echo "e2e: port $port is already in use." >&2
      echo "     Stop it (./scripts/dev.sh down) or run E2E_EXTERNAL=1 ./e2e/run.sh." >&2
      exit 1
    fi
  done

  rm -rf "$DATA_DIR"
  mkdir -p "$DATA_DIR" "$LOG_DIR" "$PID_DIR"
  : > "$DATA_DIR/empty.env"

  export ENV_FILE="$DATA_DIR/empty.env"
  export APP_ENV=development
  export DEV_MODE=true
  export SECRET_KEY="e2e-school-secret-0123456789abcdef012345"
  export REFRESH_SECRET="e2e-refresh-secret-0123456789abcdef"
  export CONTROLLER_SECRET_KEY="e2e-controller-secret-0123456789abcdef"
  export DATABASE_URL="sqlite+aiosqlite:///$DATA_DIR/school.db"
  export CONTROLLER_DATABASE_URL="sqlite+aiosqlite:///$DATA_DIR/controller.db"
  export CONTROLLER_URL="http://localhost:8100"
  export CONTROLLER_API_BASE_URL="http://localhost:8100"
  export CONTROLLER_PUBLIC_BASE_URL="http://localhost:8100"
  export PUBLIC_BASE_URL="http://localhost:8000"
  export WEB_BASE_URL="http://localhost:5173"
  export CORS_ORIGINS="http://localhost:5173,http://localhost:5174"
  export STORAGE_DRIVER=local
  export STORAGE_DIR="$DATA_DIR/storage"
  export VITE_API_URL="http://localhost:8000"
  export VITE_CONTROLLER_API_URL="http://localhost:8100"
  export VITE_SCHOOL_WEB_URL="http://localhost:5173"
  # The demo seed writes several hundred audit rows. Ship them in one batch so
  # the smoke test's three syncs always reach the newest entry it asserts on.
  export AUDIT_SHIP_BATCH=1000

  echo "e2e: seeding demo data"
  if ! PYTHONPATH="$ROOT/school-erp/backend:$ROOT/owner/controller-api:$ROOT/shared/py" \
    "$PYTHON" "$ROOT/scripts/seed.py" >"$LOG_DIR/seed.log" 2>&1; then
    tail -30 "$LOG_DIR/seed.log" >&2
    echo "e2e: seeding failed" >&2
    exit 1
  fi
fi

PIDS=()

start() {
  local name="$1"
  shift
  echo "e2e: starting $name"
  "$@" >"$LOG_DIR/$name.log" 2>&1 &
  local pid=$!
  PIDS+=("$pid")
  echo "$pid" > "$PID_DIR/$name.pid"
}

wait_for() {
  local url="$1" name="$2"
  for _ in $(seq 1 120); do
    if curl -fsS -o /dev/null --max-time 2 "$url"; then
      return 0
    fi
    sleep 0.5
  done
  echo "e2e: $name did not become ready ($url)" >&2
  return 1
}

cleanup() {
  local status=$?
  local pid
  for pid in "${PIDS[@]:-}"; do
    [ -n "$pid" ] || continue
    # Each background job is its own process group (set -m), so this also stops
    # the vite/uvicorn children.
    kill -TERM -- "-$pid" 2>/dev/null || kill "$pid" 2>/dev/null || true
  done
  wait 2>/dev/null || true
  if [ "$EXTERNAL" != "1" ] && [ "$status" -ne 0 ]; then
    echo "e2e: logs are in $LOG_DIR" >&2
  fi
  exit "$status"
}
trap cleanup EXIT INT TERM

if [ "$EXTERNAL" != "1" ]; then
  mkdir -p "$LOG_DIR"
  start school-api env PYTHONPATH="$ROOT/school-erp/backend:$ROOT/shared/py" \
    "$PYTHON" -m uvicorn app.entrypoint:app --host 127.0.0.1 --port 8000
  start controller-api env PYTHONPATH="$ROOT/owner/controller-api:$ROOT/shared/py" \
    "$PYTHON" -m uvicorn controller_api.entrypoint:app --host 127.0.0.1 --port 8100
  wait_for "http://127.0.0.1:8000/health" "school API" || exit 1
  wait_for "http://127.0.0.1:8100/health" "controller API" || exit 1

  start school-web "${PNPM[@]}" --filter @erp/school-web dev
  start controller-web "${PNPM[@]}" --filter @erp/controller-web dev
  wait_for "http://127.0.0.1:5173" "school web" || exit 1
  wait_for "http://127.0.0.1:5174" "controller web" || exit 1
fi

echo "e2e: running Playwright"
"${PNPM[@]}" --filter @erp/e2e e2e "$@"
