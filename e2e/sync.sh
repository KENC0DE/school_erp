#!/usr/bin/env bash
# One controller synchronisation step for the e2e stack: heartbeat (which pulls
# module/license changes) followed by audit shipping. Mirrors what Celery beat
# does every `heartbeat_seconds` in a full deployment.
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT"

PYTHON="${ERP_PYTHON:-$ROOT/.venv/bin/python}"
if [ ! -x "$PYTHON" ]; then
  PYTHON="$(command -v python3)"
fi

export PYTHONPATH="$ROOT/school-erp/backend:$ROOT/shared/py:$ROOT/owner/controller-api${PYTHONPATH:+:$PYTHONPATH}"

exec "$PYTHON" - <<'PY'
import asyncio

from app.settings import get_settings
from core.controller_link.service import heartbeat, ship_audit
from core.db.session import Database


async def main() -> None:
    settings = get_settings()
    database = Database(settings.database_url)
    try:
        async with database.session() as session:
            await heartbeat(session, settings)
            await ship_audit(session, settings)
    finally:
        await database.dispose()


asyncio.run(main())
PY
