#!/usr/bin/env bash
# Export the FastAPI schema without starting a server, regenerate the TypeScript
# API client into a temporary file and fail when the committed file differs.
#
#   ./scripts/gen-api.sh                 # check (CI)
#   ./scripts/gen-api.sh --write         # update shared/ts/api-client/src/schema.d.ts
#   ./scripts/gen-api.sh --controller    # also export controller OpenAPI to data/openapi/
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT"

CLIENT_DIR="$ROOT/shared/ts/api-client"
SCHEMA="$CLIENT_DIR/src/schema.d.ts"
WRITE=0
CONTROLLER=0
CONTROLLER_OUT="$ROOT/data/openapi/controller.json"

while [ $# -gt 0 ]; do
  case "$1" in
    --write) WRITE=1 ;;
    --controller) CONTROLLER=1 ;;
    --controller-out)
      shift
      CONTROLLER_OUT="${1:?--controller-out needs a path}"
      CONTROLLER=1
      ;;
    -h|--help)
      sed -n '2,9p' "$0" | sed 's/^# \{0,1\}//'
      exit 0
      ;;
    *) echo "gen-api: unknown argument $1" >&2; exit 2 ;;
  esac
  shift
done

TMP_ROOT="${TMPDIR:-/tmp}/opencode"
mkdir -p "$TMP_ROOT"
TMP="$(mktemp -d "$TMP_ROOT/erp-gen-api.XXXXXX")"
trap 'rm -rf "$TMP"' EXIT

python_has_deps() {
  [ -n "${1:-}" ] && [ -x "$1" ] && "$1" -c 'import fastapi, sqlalchemy' >/dev/null 2>&1
}

resolve_python() {
  if [ -n "${ERP_PYTHON:-}" ] && python_has_deps "$ERP_PYTHON"; then
    PYTHON_MODE="bin"; PYTHON_BIN="$ERP_PYTHON"; return 0
  fi
  for candidate in "$ROOT/.venv/bin/python" "$ROOT/school-erp/backend/.venv/bin/python"; do
    if python_has_deps "$candidate"; then
      PYTHON_MODE="bin"; PYTHON_BIN="$candidate"; return 0
    fi
  done
  if command -v uv >/dev/null 2>&1 && [ -x "$ROOT/.venv/bin/python" ]; then
    PYTHON_MODE="uv"; return 0
  fi
  return 1
}

if ! resolve_python; then
  echo "gen-api: no Python environment with FastAPI/SQLAlchemy; run 'uv sync --all-packages' or set ERP_PYTHON" >&2
  exit 1
fi

if [ "$PYTHON_MODE" = "uv" ]; then
  RUN_PY=(uv run --no-sync python)
else
  RUN_PY=("$PYTHON_BIN")
fi

GEN_BIN="$CLIENT_DIR/node_modules/.bin/openapi-typescript"
if [ ! -x "$GEN_BIN" ]; then
  GEN_BIN="$ROOT/node_modules/.bin/openapi-typescript"
fi
if [ ! -x "$GEN_BIN" ]; then
  echo "gen-api: openapi-typescript is not installed; run 'pnpm install'" >&2
  exit 1
fi

echo "==> exporting school OpenAPI (no server)"
(
  cd "$ROOT/school-erp/backend"
  PYTHONPATH="$ROOT/school-erp/backend:$ROOT/shared/py" "${RUN_PY[@]}" -c '
import json
from app.main import create_app
json.dump(create_app().openapi(), open("'"$TMP"'/openapi.json", "w"), indent=2, sort_keys=True)
'
)

if [ "$CONTROLLER" = 1 ]; then
  echo "==> exporting controller OpenAPI (no server)"
  mkdir -p "$(dirname "$CONTROLLER_OUT")"
  (
    cd "$ROOT/owner/controller-api"
    PYTHONPATH="$ROOT/owner/controller-api:$ROOT/shared/py" "${RUN_PY[@]}" -c '
import json
from controller_api.main import create_controller_app
json.dump(create_controller_app().openapi(), open("'"$CONTROLLER_OUT"'", "w"), indent=2, sort_keys=True)
'
  )
  echo "    wrote ${CONTROLLER_OUT#"$ROOT"/}"
fi

if [ "$WRITE" = 1 ]; then
  echo "==> regenerating ${SCHEMA#"$ROOT"/}"
  "$GEN_BIN" "$TMP/openapi.json" -o "$SCHEMA"
  echo "gen-api: updated ${SCHEMA#"$ROOT"/}"
  exit 0
fi

echo "==> generating client into a temporary file (diff check)"
"$GEN_BIN" "$TMP/openapi.json" -o "$TMP/schema.d.ts"
if [ ! -f "$SCHEMA" ]; then
  echo "gen-api: $SCHEMA is missing; run ./scripts/gen-api.sh --write" >&2
  exit 1
fi
if cmp -s "$TMP/schema.d.ts" "$SCHEMA"; then
  echo "gen-api: $SCHEMA is up to date"
  exit 0
fi

echo "gen-api: the committed client is stale. Run ./scripts/gen-api.sh --write" >&2
diff -u "$SCHEMA" "$TMP/schema.d.ts" | head -n 200 >&2 || true
exit 1
