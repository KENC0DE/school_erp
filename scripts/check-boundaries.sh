#!/usr/bin/env bash
# Shared boundary check used by CI and pre-commit: Python import-linter plus the
# TypeScript zone restrictions in eslint.config.js.
set -uo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT" || exit 1

status=0

# pnpm may be installed without being on PATH on this build host. Package
# scripts such as `eslint` call `pnpm` themselves, so expose a temporary shim.
if ! command -v pnpm >/dev/null 2>&1; then
  for candidate in \
    "$HOME/.local/lib/node_modules/pnpm/bin/pnpm.cjs" \
    "/usr/local/lib/node_modules/pnpm/bin/pnpm.cjs"; do
    if [ -f "$candidate" ]; then
      SHIM_DIR="$(mktemp -d "${TMPDIR:-/tmp}/opencode/pnpm-shim.XXXXXX")"
      printf '#!/bin/sh\nexec node "%s" "$@"\n' "$candidate" > "$SHIM_DIR/pnpm"
      chmod +x "$SHIM_DIR/pnpm"
      PATH="$SHIM_DIR:$PATH"
      export PATH
      trap 'rm -rf "$SHIM_DIR"' EXIT
      break
    fi
  done
fi

PYTHONPATH="$ROOT/school-erp/backend:$ROOT/owner/controller-api:$ROOT/shared/py${PYTHONPATH:+:$PYTHONPATH}" \
  bash -c '
    if [ -x "$0/.venv/bin/lint-imports" ]; then exec "$0/.venv/bin/lint-imports"
    elif command -v lint-imports >/dev/null 2>&1; then exec lint-imports
    elif command -v uv >/dev/null 2>&1; then exec uv run --no-sync lint-imports
    else echo "check-boundaries: lint-imports not found" >&2; exit 127
    fi
  ' "$ROOT" || status=1

if command -v pnpm >/dev/null 2>&1; then
  pnpm -r --if-present lint || status=1
elif [ -f "$HOME/.local/lib/node_modules/pnpm/bin/pnpm.cjs" ]; then
  node "$HOME/.local/lib/node_modules/pnpm/bin/pnpm.cjs" -r --if-present lint || status=1
else
  echo "check-boundaries: pnpm not found; skipping TypeScript lint" >&2
fi

exit "$status"
