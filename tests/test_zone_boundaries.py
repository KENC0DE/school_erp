"""P0-01b: the real zone rules reject deliberately violating fixtures.

The fixtures live in `tests/boundary_fixtures/`. Python probes are evaluated in a
temporary copy of the package tree so the working tree is never modified; the
TypeScript probe lints the fixture text under the target path through the real
`eslint.config.mjs`.
"""

from __future__ import annotations

import os
import shutil
import subprocess
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
FIXTURES = ROOT / "tests" / "boundary_fixtures"

PYTHON_PACKAGES = (
    ("school-erp/backend/app", "school-erp/backend"),
    ("school-erp/backend/core", "school-erp/backend"),
    ("school-erp/backend/modules", "school-erp/backend"),
    ("owner/controller-api/controller_api", "owner/controller-api"),
    ("shared/py/erp_shared", "shared/py"),
)


def _lint_imports_binary() -> str:
    candidate = Path(sys.executable).with_name("lint-imports")
    if candidate.exists():
        return str(candidate)
    found = shutil.which("lint-imports")
    if found:
        return found
    pytest.skip("lint-imports is not installed")


@pytest.fixture()
def boundary_copy(tmp_path: Path) -> Path:
    """A throwaway tree holding the real packages and the real .importlinter."""
    root = tmp_path / "repo"
    for relative, _ in PYTHON_PACKAGES:
        shutil.copytree(
            ROOT / relative,
            root / relative,
            ignore=shutil.ignore_patterns("__pycache__", "*.pyc"),
        )
    shutil.copy(ROOT / ".importlinter", root / ".importlinter")
    return root


def _run_lint_imports(root: Path) -> subprocess.CompletedProcess[str]:
    env = os.environ.copy()
    python_path = [str(root / parent) for _, parent in PYTHON_PACKAGES]
    env["PYTHONPATH"] = os.pathsep.join(python_path)
    return subprocess.run(
        [_lint_imports_binary()],
        cwd=root,
        env=env,
        capture_output=True,
        text=True,
        timeout=180,
    )


@pytest.mark.parametrize(
    ("fixture", "target"),
    [
        ("py_school_imports_owner.py", "school-erp/backend/core/_zone_probe.py"),
        ("py_owner_imports_school.py", "owner/controller-api/controller_api/_zone_probe.py"),
        ("py_shared_imports_school.py", "shared/py/erp_shared/_zone_probe.py"),
        ("py_core_imports_modules.py", "school-erp/backend/core/_zone_probe.py"),
    ],
)
def test_python_zone_violation_is_rejected(boundary_copy: Path, fixture: str, target: str) -> None:
    probe = boundary_copy / target
    probe.write_text((FIXTURES / fixture).read_text(encoding="utf-8"), encoding="utf-8")

    result = _run_lint_imports(boundary_copy)

    assert result.returncode != 0, result.stdout + result.stderr
    assert "BROKEN" in result.stdout.upper()


def test_python_zone_baseline_passes(boundary_copy: Path) -> None:
    result = _run_lint_imports(boundary_copy)
    assert result.returncode == 0, result.stdout + result.stderr


@pytest.mark.parametrize(
    ("fixture", "target"),
    [
        (
            "ts_school_imports_owner.ts",
            "school-erp/web/src/__zone_probe.ts",
        ),
        (
            "ts_owner_imports_school.ts",
            "owner/controller-web/src/__zone_probe.ts",
        ),
        (
            "ts_shared_imports_owner.ts",
            "shared/ts/api-client/src/__zone_probe.ts",
        ),
    ],
)
def test_typescript_zone_violation_is_rejected(fixture: str, target: str) -> None:
    result = subprocess.run(
        ["node", str(ROOT / "tests" / "boundary_probe.mjs"), str(FIXTURES / fixture), target],
        cwd=ROOT,
        capture_output=True,
        text=True,
        timeout=180,
    )
    assert result.returncode == 0, result.stdout + result.stderr
    assert "no-restricted-imports" in result.stdout


def test_typescript_zone_baseline_passes() -> None:
    result = subprocess.run(
        [
            "node",
            str(ROOT / "tests" / "boundary_probe.mjs"),
            str(FIXTURES / "ts_allowed_local.ts"),
            "school-erp/web/src/__zone_probe.ts",
        ],
        cwd=ROOT,
        capture_output=True,
        text=True,
        timeout=180,
    )
    # The probe script exits 1 when the rule does not fire, which is the
    # expected outcome for a file that stays inside its zone.
    assert result.returncode == 1, result.stdout + result.stderr
    assert "no zone violation reported" in result.stderr
