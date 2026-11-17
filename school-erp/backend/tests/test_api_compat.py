"""P1-26: the committed /api/v1 snapshot and the compatibility check itself."""

from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

from erp_shared.api_compat import compare_schemas

ROOT = Path(__file__).resolve().parents[3]
SNAPSHOT = ROOT / "shared" / "openapi" / "v1.json"
PREVIOUS = ROOT / "shared" / "openapi" / "v1.previous.json"
SCRIPT = ROOT / "scripts" / "check-api-compat.py"


def _load(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def test_the_released_snapshot_is_still_compatible(app) -> None:
    baseline = _load(SNAPSHOT)
    previous = _load(PREVIOUS) if PREVIOUS.exists() else None

    # This is the CI guard as a test: additive changes pass, a breaking change
    # against the last released contract fails here.
    assert compare_schemas(app.openapi(), baseline, previous) == []
    assert "/api/v1/auth/login" in baseline["paths"]
    assert baseline["openapi"].startswith("3.")


def test_a_deliberately_breaking_change_is_detected(app) -> None:
    baseline = _load(SNAPSHOT)
    current = app.openapi()
    del current["paths"]["/api/v1/jobs"]

    changes = compare_schemas(current, baseline)
    assert {change.kind for change in changes} == {"endpoint_removed"}
    assert "GET /api/v1/jobs" in {change.location for change in changes}


def test_the_cli_exits_non_zero_on_a_breaking_change(tmp_path) -> None:
    baseline = _load(SNAPSHOT)
    del baseline["paths"]["/api/v1/notifications"]
    mutated = tmp_path / "mutated.json"
    mutated.write_text(json.dumps(baseline), encoding="utf-8")

    failed = subprocess.run(
        [sys.executable, str(SCRIPT), "--schema", str(mutated)],
        cwd=ROOT,
        capture_output=True,
        text=True,
        check=False,
    )
    assert failed.returncode == 1
    assert "breaking change" in failed.stderr
    assert "endpoint_removed" in failed.stderr

    passing = subprocess.run(
        [sys.executable, str(SCRIPT), "--schema", str(SNAPSHOT)],
        cwd=ROOT,
        capture_output=True,
        text=True,
        check=False,
    )
    assert passing.returncode == 0, passing.stderr
    assert "ok" in passing.stdout
