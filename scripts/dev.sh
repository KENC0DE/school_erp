#!/usr/bin/env bash
# School ERP development launcher. See scripts/README.md.
#
# Docker is used when a daemon is reachable; otherwise the documented SQLite
# fallback runs the APIs directly. Every background process this script starts
# is recorded in data/dev.pids and `down` only stops those processes.
set -uo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT" || exit 1

DATA_DIR="$ROOT/data"
LOG_DIR="$DATA_DIR/logs"
PID_FILE="$DATA_DIR/dev.pids"
COMPOSE_FILE="$ROOT/deploy/compose/dev.yml"
COMPOSE_MARKER="$DATA_DIR/dev.compose"

mkdir -p "$DATA_DIR" "$LOG_DIR"

if [ -t 1 ]; then
  C_RESET=$'\033[0m'; C_DIM=$'\033[2m'; C_GREEN=$'\033[32m'; C_YELLOW=$'\033[33m'; C_RED=$'\033[31m'; C_BOLD=$'\033[1m'
else
  C_RESET=""; C_DIM=""; C_GREEN=""; C_YELLOW=""; C_RED=""; C_BOLD=""
fi
log()  { printf '%s[dev]%s %s\n' "$C_GREEN" "$C_RESET" "$*"; }
warn() { printf '%s[dev]%s %s\n' "$C_YELLOW" "$C_RESET" "$*" >&2; }
err()  { printf '%s[dev]%s %s\n' "$C_RED" "$C_RESET" "$*" >&2; }
step() { printf '\n%s==> %s%s\n' "$C_BOLD" "$*" "$C_RESET"; }

# ---------------------------------------------------------------- tool lookup
find_pnpm() {
  if command -v pnpm >/dev/null 2>&1; then
    PNPM=(pnpm)
    return 0
  fi
  for candidate in \
    "$HOME/.local/lib/node_modules/pnpm/bin/pnpm.cjs" \
    "$HOME/.local/share/pnpm/pnpm.cjs" \
    "/usr/local/lib/node_modules/pnpm/bin/pnpm.cjs" \
    "/usr/lib/node_modules/pnpm/bin/pnpm.cjs"; do
    if [ -f "$candidate" ]; then
      PNPM=(node "$candidate")
      return 0
    fi
  done
  return 1
}

if find_pnpm; then HAVE_PNPM=1; else HAVE_PNPM=0; PNPM=(pnpm); fi

python_has_deps() {
  [ -n "${1:-}" ] && [ -x "$1" ] && "$1" -c 'import fastapi, sqlalchemy, uvicorn, aiosqlite' >/dev/null 2>&1
}

PYTHON_BIN=""
PYTHON_MODE=""
resolve_python() {
  if [ -n "${ERP_PYTHON:-}" ]; then
    if python_has_deps "$ERP_PYTHON"; then PYTHON_BIN="$ERP_PYTHON"; PYTHON_MODE="bin"; return 0; fi
    warn "ERP_PYTHON=$ERP_PYTHON is not a suitable interpreter (missing fastapi/sqlalchemy/uvicorn/aiosqlite)"
  fi
  local candidates=(
    "$ROOT/.venv/bin/python"
    "$ROOT/school-erp/backend/.venv/bin/python"
    "$ROOT/owner/controller-api/.venv/bin/python"
  )
  local candidate
  for candidate in "${candidates[@]}"; do
    if python_has_deps "$candidate"; then PYTHON_BIN="$candidate"; PYTHON_MODE="bin"; return 0; fi
  done
  if command -v uv >/dev/null 2>&1 && [ -x "$ROOT/.venv/bin/python" ]; then
    PYTHON_MODE="uv"; return 0
  fi
  if python_has_deps "$(command -v python3 2>/dev/null)"; then
    PYTHON_BIN="$(command -v python3)"; PYTHON_MODE="bin"; return 0
  fi
  return 1
}

if ! resolve_python; then
  err "No Python environment with the backend dependencies was found."
  err "Run 'uv sync --all-packages' (or set ERP_PYTHON=/path/to/python) first."
  exit 1
fi

RUN_PY=()
if [ "$PYTHON_MODE" = "uv" ]; then RUN_PY=(uv run --no-sync python); else RUN_PY=("$PYTHON_BIN"); fi

RUFF_BIN=""
if [ -x "$ROOT/.venv/bin/ruff" ]; then RUFF_BIN="$ROOT/.venv/bin/ruff";
elif command -v ruff >/dev/null 2>&1; then RUFF_BIN="$(command -v ruff)";
elif [ "$PYTHON_MODE" = "bin" ]; then RUFF_BIN="$PYTHON_BIN -m ruff"; fi

LINT_IMPORTS_BIN=""
if [ -x "$ROOT/.venv/bin/lint-imports" ]; then LINT_IMPORTS_BIN="$ROOT/.venv/bin/lint-imports";
elif command -v lint-imports >/dev/null 2>&1; then LINT_IMPORTS_BIN="$(command -v lint-imports)";
elif [ "$PYTHON_MODE" = "bin" ]; then LINT_IMPORTS_BIN="$PYTHON_BIN -m importlinter.cli"; fi

export PYTHONPATH_APP="$ROOT/school-erp/backend:$ROOT/shared/py"
export PYTHONPATH_CONTROLLER="$ROOT/owner/controller-api:$ROOT/shared/py"
export PYTHONPATH_ALL="$ROOT/school-erp/backend:$ROOT/owner/controller-api:$ROOT/shared/py"

# ------------------------------------------------------------------ processes
proc_start_time() {
  ps -o lstart= -p "${1:-0}" 2>/dev/null | sed 's/^ *//;s/ *$//'
}

tracked_pid() {
  [ -f "$PID_FILE" ] || return 1
  awk -F'\t' -v name="$1" '$1 == name { pid = $2 } END { if (pid != "") print pid }' "$PID_FILE"
}

tracked_start_time() {
  [ -f "$PID_FILE" ] || return 1
  awk -F'\t' -v name="$1" '$1 == name { line = $4 } END { if (line != "") print line }' "$PID_FILE"
}

remove_tracked() {
  [ -f "$PID_FILE" ] || return 0
  local tmp="$PID_FILE.tmp"
  awk -F'\t' -v name="$1" '$1 != name' "$PID_FILE" > "$tmp" || true
  mv "$tmp" "$PID_FILE"
}

record_pid() {
  local name="$1" pid="$2" port="$3"
  remove_tracked "$name"
  printf '%s\t%s\t%s\t%s\n' "$name" "$pid" "$port" "$(proc_start_time "$pid")" >> "$PID_FILE"
}

is_alive() {
  local pid="${1:-}"
  case "$pid" in
    ''|0|*[!0-9]*) return 1 ;;
  esac
  kill -0 "$pid" 2>/dev/null
}

port_in_use() {
  local port="$1"
  (exec 3<>"/dev/tcp/127.0.0.1/$port") >/dev/null 2>&1
}

wait_http() {
  local url="$1" timeout="${2:-40}" i
  for ((i = 0; i < timeout * 2; i++)); do
    if curl -fsS --max-time 2 "$url" >/dev/null 2>&1; then return 0; fi
    sleep 0.5
  done
  return 1
}

start_process() {
  local name="$1" port="$2" workdir="$3" logfile="$4"
  shift 4
  local pid
  if pid="$(tracked_pid "$name")" && is_alive "$pid"; then
    log "$name already running (pid $pid)"
    return 0
  fi
  remove_tracked "$name"
  if [ "$port" != "-" ] && port_in_use "$port"; then
    warn "$name: port $port is already in use by an untracked process; not starting it"
    return 0
  fi
  mkdir -p "$(dirname "$logfile")"
  printf '\n%s--- %s started %s ---%s\n' "$C_DIM" "$name" "$(date -Is)" "$C_RESET" >> "$logfile"
  ( cd "$workdir" && exec "$@" >>"$logfile" 2>&1 ) &
  pid=$!
  sleep 0.4
  if is_alive "$pid"; then
    record_pid "$name" "$pid" "$port"
    log "$name started (pid $pid, port ${port}, log ${logfile#"$ROOT"/})"
    return 0
  fi
  err "$name failed to start. Last log lines:"
  tail -n 20 "$logfile" >&2 || true
  return 1
}

kill_tree() {
  local pid="$1" child
  for child in $(pgrep -P "$pid" 2>/dev/null || true); do
    kill_tree "$child"
  done
  kill -TERM "$pid" 2>/dev/null || true
}

stop_process() {
  local name="$1" pid start now i
  pid="$(tracked_pid "$name" || true)"
  [ -n "${pid:-}" ] || return 0
  if ! is_alive "$pid"; then
    warn "$name was not running (stale pid $pid); removing entry"
    remove_tracked "$name"
    return 0
  fi
  start="$(tracked_start_time "$name" || true)"
  now="$(proc_start_time "$pid")"
  if [ -n "$start" ] && [ -n "$now" ] && [ "$start" != "$now" ]; then
    warn "$name pid $pid was reused by another process; not killing it"
    remove_tracked "$name"
    return 0
  fi
  local cmdline
  cmdline="$(tr '\0' ' ' < "/proc/$pid/cmdline" 2>/dev/null || true)"
  case "$cmdline" in
    *uvicorn*|*vite*|*expo*|*pnpm*|*node*|*"$ROOT"*) ;;
    *) warn "$name pid $pid does not look like a dev process; not killing it"; remove_tracked "$name"; return 0 ;;
  esac
  log "stopping $name (pid $pid)"
  kill_tree "$pid"
  for ((i = 0; i < 20; i++)); do
    is_alive "$pid" || break
    sleep 0.2
  done
  if is_alive "$pid"; then
    kill -KILL "$pid" 2>/dev/null || true
  fi
  remove_tracked "$name"
}

docker_available() {
  command -v docker >/dev/null 2>&1 && docker info >/dev/null 2>&1
}

# -------------------------------------------------------------------- database
USE_COMPOSE=0
if docker_available && [ -f "$COMPOSE_FILE" ]; then USE_COMPOSE=1; fi

setup_env() {
  export APP_ENV="${APP_ENV:-development}"
  export DEV_MODE=true
  export SECRET_KEY="${SECRET_KEY:-dev-only-change-me-please-0123456789abcdef}"
  export REFRESH_SECRET="${REFRESH_SECRET:-dev-only-change-me-too-0123456789abcdef}"
  export CONTROLLER_SECRET_KEY="${CONTROLLER_SECRET_KEY:-controller-dev-only-change-me-0123456789}"
  # Dev-only directory signing key; the mobile app embeds the matching public key
  # (owner/mobile/src/config/keys.ts) so `./scripts/dev.sh mobile` works on a
  # clean clone. Override in production. Existing databases keep their first key,
  # so run `./scripts/dev.sh reset` once if the controller was seeded before.
  export DIRECTORY_KID="${DIRECTORY_KID:-k1}"
  if [ -z "${DIRECTORY_PRIVATE_KEY:-}" ]; then
    export DIRECTORY_PRIVATE_KEY='-----BEGIN PRIVATE KEY-----
MC4CAQAwBQYDK2VwBCIEICxiIR4mAY6IMg9u6c0KnMJEJIAc30HftQ7nLcOCwLDx
-----END PRIVATE KEY-----'
  fi
  export CORS_ORIGINS="http://localhost:5173,http://localhost:5174,http://localhost:8081"
  export PUBLIC_BASE_URL="http://localhost:8000"
  export CONTROLLER_URL="http://localhost:8100"
  export CONTROLLER_PUBLIC_BASE_URL="http://localhost:8100"
  export CONTROLLER_API_BASE_URL="http://localhost:8100"
  export VITE_API_URL="http://localhost:8000"
  export VITE_CONTROLLER_API_URL="http://localhost:8100"
  export STORAGE_DRIVER="${STORAGE_DRIVER:-local}"
  export STORAGE_DIR="$DATA_DIR/storage"
  if [ "$USE_COMPOSE" = 1 ]; then
    export DATABASE_URL="${DATABASE_URL:-postgresql+psycopg://erp:erp_dev_password@localhost:5432/erp_demo}"
    export CONTROLLER_DATABASE_URL="${CONTROLLER_DATABASE_URL:-postgresql+psycopg://erp:erp_dev_password@localhost:5432/controller}"
    export REDIS_URL="${REDIS_URL:-redis://localhost:6379/0}"
  else
    export DATABASE_URL="${DATABASE_URL:-sqlite+aiosqlite:///$DATA_DIR/erp_demo.db}"
    export CONTROLLER_DATABASE_URL="${CONTROLLER_DATABASE_URL:-sqlite+aiosqlite:///$DATA_DIR/controller.db}"
  fi
}

apply_school_migrations() {
  local migrations
  migrations=$(find "$ROOT/school-erp/backend/alembic/versions" -maxdepth 1 -name '*.py' 2>/dev/null | head -n 1)
  if [ -z "$migrations" ]; then
    log "no Alembic revisions yet; the app factory creates the schema on startup"
    return 0
  fi
  step "applying school migrations"
  ( cd "$ROOT/school-erp/backend" && PYTHONPATH="$PYTHONPATH_APP" "${RUN_PY[@]}" -m alembic upgrade heads )
}

# -------------------------------------------------------------------- commands
cmd_up() {
  setup_env
  if [ "$USE_COMPOSE" = 1 ]; then
    step "starting docker compose services"
    if docker compose -f "$COMPOSE_FILE" up -d --wait; then
      touch "$COMPOSE_MARKER"
    else
      warn "docker compose did not become healthy; falling back to SQLite"
      USE_COMPOSE=0
      unset DATABASE_URL CONTROLLER_DATABASE_URL REDIS_URL
      setup_env
    fi
  else
    warn "Docker daemon unavailable or compose file missing: using the documented SQLite dev fallback"
  fi

  if [ "$USE_COMPOSE" = 1 ]; then apply_school_migrations; fi

  step "starting APIs"
  # The schools app only imports its own zone plus shared/.
  start_process "school-api" 8000 "$ROOT/school-erp/backend" "$LOG_DIR/school-api.log" \
    env PYTHONPATH="$PYTHONPATH_APP" "${RUN_PY[@]}" -m uvicorn app.entrypoint:app --host 0.0.0.0 --port 8000
  start_process "controller-api" 8100 "$ROOT/owner/controller-api" "$LOG_DIR/controller-api.log" \
    env PYTHONPATH="$PYTHONPATH_CONTROLLER" "${RUN_PY[@]}" -m uvicorn controller_api.entrypoint:app --host 0.0.0.0 --port 8100

  step "waiting for the APIs"
  local ok=1
  if wait_http "http://localhost:8000/health" 60; then log "school API is healthy"; else err "school API did not become healthy"; ok=0; fi
  if wait_http "http://localhost:8100/health" 60; then log "controller API is healthy"; else err "controller API did not become healthy"; ok=0; fi

  if [ "$HAVE_PNPM" = 1 ]; then
    step "starting web apps"
    if [ -f "$ROOT/school-erp/web/package.json" ]; then
      start_process "school-web" 5173 "$ROOT" "$LOG_DIR/school-web.log" \
        "${PNPM[@]}" --filter @erp/school-web dev
    else
      warn "school-erp/web/package.json is missing; skipping school web"
    fi
    if [ -f "$ROOT/owner/controller-web/package.json" ]; then
      start_process "controller-web" 5174 "$ROOT" "$LOG_DIR/controller-web.log" \
        "${PNPM[@]}" --filter @erp/controller-web dev
    else
      warn "owner/controller-web/package.json is missing; skipping controller web"
    fi
  else
    warn "pnpm was not found; skipping the web apps (install pnpm or corepack)"
  fi

  step "ready"
  printf '  School API      http://localhost:8000       (docs /api/docs)\n'
  printf '  Controller API  http://localhost:8100       (docs /controller/docs)\n'
  printf '  School web      http://localhost:5173\n'
  printf '  Controller web  http://localhost:5174\n'
  printf '  Database mode   %s\n' "$([ "$USE_COMPOSE" = 1 ] && echo 'PostgreSQL (compose)' || echo 'SQLite fallback')"
  printf '  Logs            %s\n' "$LOG_DIR"
  printf '  Next            ./scripts/dev.sh seed\n'
  [ "$ok" = 1 ] || return 1
}

cmd_seed() {
  if [ "${APP_ENV:-}" = "production" ]; then
    err "seed refuses to run with APP_ENV=production"
    return 2
  fi
  setup_env
  step "seeding demo data"
  ( cd "$ROOT" && env PYTHONPATH="$PYTHONPATH_ALL" "${RUN_PY[@]}" "$ROOT/scripts/seed.py" )
}

cmd_down() {
  step "stopping dev processes"
  if [ -f "$PID_FILE" ]; then
    local names=()
    mapfile -t names < <(awk -F'\t' '{print $1}' "$PID_FILE")
    local name
    for name in "${names[@]}"; do
      [ -n "$name" ] && stop_process "$name"
    done
  else
    log "no tracked processes"
  fi
  rm -f "$PID_FILE"
  if [ -f "$COMPOSE_MARKER" ]; then
    if docker_available; then
      log "stopping docker compose services"
      if [ "${1:-}" = "volumes" ]; then
        docker compose -f "$COMPOSE_FILE" down --volumes --remove-orphans || warn "docker compose down failed"
      else
        docker compose -f "$COMPOSE_FILE" down --remove-orphans || warn "docker compose down failed"
      fi
    else
      warn "docker daemon is unavailable; compose services cannot be stopped from here"
    fi
  fi
  rm -f "$COMPOSE_MARKER"
}

cmd_reset() {
  cmd_down volumes
  step "deleting local generated data"
  case "$DATA_DIR" in
    "$ROOT"/data) rm -rf "$DATA_DIR"; log "removed $DATA_DIR";;
    *) err "refusing to delete unexpected data path: $DATA_DIR"; return 1;;
  esac
  mkdir -p "$DATA_DIR" "$LOG_DIR"
  cmd_up
  cmd_seed
}

run_step() {
  local name="$1"; shift
  step "$name"
  if "$@"; then
    PASSED+=("$name")
  else
    FAILED+=("$name")
  fi
}

cmd_test() {
  setup_env
  export APP_ENV="test"
  local -a PASSED=() FAILED=()
  local py_test=()
  if [ "$PYTHON_MODE" = "uv" ]; then py_test=(uv run --no-sync pytest); else py_test=("$PYTHON_BIN" -m pytest); fi

  run_step "school backend pytest" bash -c "cd '$ROOT/school-erp/backend' && PYTHONPATH='$PYTHONPATH_ALL' $(printf '%q ' "${py_test[@]}")"
  run_step "controller pytest" bash -c "cd '$ROOT/owner/controller-api' && PYTHONPATH='$PYTHONPATH_ALL' $(printf '%q ' "${py_test[@]}")"
  run_step "shared python pytest" bash -c "cd '$ROOT/shared/py' && PYTHONPATH='$ROOT/shared/py' $(printf '%q ' "${py_test[@]}")"
  run_step "zone boundary pytest" bash -c "cd '$ROOT' && PYTHONPATH='$PYTHONPATH_ALL' $(printf '%q ' "${py_test[@]}") tests"

  if [ -n "$RUFF_BIN" ]; then
    run_step "ruff check" bash -c "$RUFF_BIN check scripts school-erp/backend owner/controller-api shared/py"
    run_step "ruff format --check" bash -c "$RUFF_BIN format --check scripts school-erp/backend owner/controller-api shared/py"
  else
    warn "ruff was not found; skipping ruff steps"
  fi

  if [ -n "$LINT_IMPORTS_BIN" ]; then
    run_step "import-linter" bash -c "cd '$ROOT' && PYTHONPATH='$PYTHONPATH_ALL' $LINT_IMPORTS_BIN"
  else
    warn "lint-imports was not found; skipping the boundary check"
  fi

  if [ "$HAVE_PNPM" = 1 ]; then
    run_step "pnpm -r test" bash -c "cd '$ROOT' && $(printf '%q ' "${PNPM[@]}") -r --if-present test"
  else
    warn "pnpm was not found; skipping JavaScript tests"
  fi

  printf '\n%sSummary%s\n' "$C_BOLD" "$C_RESET"
  local item
  if [ "${#PASSED[@]}" -gt 0 ]; then
    for item in "${PASSED[@]}"; do printf '  %sPASS%s %s\n' "$C_GREEN" "$C_RESET" "$item"; done
  fi
  if [ "${#FAILED[@]}" -gt 0 ]; then
    for item in "${FAILED[@]}"; do printf '  %sFAIL%s %s\n' "$C_RED" "$C_RESET" "$item"; done
  fi
  if [ "${#FAILED[@]}" -gt 0 ]; then
    err "${#FAILED[@]} step(s) failed"
    return 1
  fi
  log "all steps passed"
}

lan_ip() {
  local ip=""
  if command -v ip >/dev/null 2>&1; then
    ip=$(ip route get 1.1.1.1 2>/dev/null | awk '{for (i = 1; i <= NF; i++) if ($i == "src") { print $(i + 1); exit }}')
  fi
  if [ -z "$ip" ] && command -v hostname >/dev/null 2>&1; then
    ip=$(hostname -I 2>/dev/null | awk '{print $1}')
  fi
  echo "${ip:-127.0.0.1}"
}

cmd_mobile() {
  if [ "$HAVE_PNPM" != 1 ]; then err "pnpm is required to start Expo"; return 1; fi
  if [ ! -f "$ROOT/owner/mobile/package.json" ]; then
    err "owner/mobile/package.json is missing; cannot start Expo"
    return 1
  fi
  setup_env
  local ip controller_url
  ip="$(lan_ip)"
  controller_url="http://$ip:8100"
  step "starting Expo on port 8081"
  log "controller URL advertised to the app: $controller_url"
  start_process "expo" 8081 "$ROOT/owner/mobile" "$LOG_DIR/expo.log" \
    env EXPO_PUBLIC_CONTROLLER_URL="$controller_url" EXPO_PUBLIC_API_URL="http://$ip:8000" \
    "${PNPM[@]}" --dir "$ROOT/owner/mobile" exec expo start --lan --port 8081
  log "Scan the QR code with Expo Go (phone on the same network). Logs: ${LOG_DIR#"$ROOT"/}/expo.log"
}

cmd_logs() {
  local files=("$LOG_DIR"/*.log)
  if [ ! -e "${files[0]}" ]; then
    err "no logs in $LOG_DIR yet"
    return 1
  fi
  log "tailing ${#files[@]} log file(s); Ctrl-C to stop"
  tail -n 40 -f "${files[@]}"
}

usage() {
  cat <<'EOF'
Usage: ./scripts/dev.sh <command>

  up       Start compose (when Docker is available) or the SQLite fallback,
           then the school API :8000, controller API :8100 and both webs.
  seed     Load the demo controller + school data. Refuses APP_ENV=production.
  reset    Stop everything, delete local data inside the repo, then up + seed.
  test     Run backend, controller, shared and JS tests plus ruff/import-linter.
  mobile   Start Expo :8081 pointed at this machine's LAN address.
  logs     Tail the logs written by this launcher.
  down     Stop only the processes this launcher tracked (and compose if used).

Environment overrides: ERP_PYTHON=/path/to/python (interpreter with backend deps).
EOF
}

case "${1:-}" in
  up) cmd_up ;;
  seed) cmd_seed ;;
  reset) cmd_reset ;;
  test) cmd_test ;;
  mobile) cmd_mobile ;;
  logs) cmd_logs ;;
  down) cmd_down ;;
  ""|-h|--help|help) usage ;;
  *) err "unknown command: $1"; usage; exit 2 ;;
esac
