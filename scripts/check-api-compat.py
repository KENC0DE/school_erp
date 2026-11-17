#!/usr/bin/env python3
"""Fail when the current API breaks the last released `/api/v1` contract (P1-26).

Usage:
    python scripts/check-api-compat.py            # CI: compare against the snapshot
    python scripts/check-api-compat.py --write    # release step: snapshot the new contract

The released contract lives in ``shared/openapi/v1.json``. At a release the old
file is rotated to ``shared/openapi/v1.previous.json`` first, so a removal is
allowed only after the item has been marked ``deprecated`` in both snapshots
(the "deprecations stay for at least two releases" policy).

Additive changes pass this check and need no snapshot update. Only release
managers run ``--write``; otherwise a breaking change could be hidden by moving
the baseline in the same change set.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
BACKEND = ROOT / "school-erp" / "backend"
SHARED = ROOT / "shared" / "py"


def _load(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def _current_schema() -> dict:
    for entry in (str(BACKEND), str(SHARED)):
        if entry not in sys.path:
            sys.path.insert(0, entry)
    from app.main import create_app

    return create_app().openapi()


def _write(path: Path, schema: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(schema, indent=2, sort_keys=True, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )


def main() -> int:
    parser = argparse.ArgumentParser(description="Check /api/v1 backwards compatibility")
    parser.add_argument(
        "--write",
        action="store_true",
        help="rotate the baseline and snapshot the current contract (release step)",
    )
    parser.add_argument(
        "--baseline",
        type=Path,
        default=ROOT / "shared" / "openapi" / "v1.json",
        help="released contract to compare against",
    )
    parser.add_argument(
        "--previous",
        type=Path,
        default=ROOT / "shared" / "openapi" / "v1.previous.json",
        help="snapshot from the release before the baseline",
    )
    parser.add_argument(
        "--schema",
        type=Path,
        help="check a stored document instead of generating the current app schema",
    )
    args = parser.parse_args()

    current = _load(args.schema) if args.schema else _current_schema()

    if args.write:
        if args.baseline.exists():
            _write(args.previous, _load(args.baseline))
        _write(args.baseline, current)
        print(f"api-compat: wrote {args.baseline.relative_to(ROOT)}")
        if args.previous.exists():
            print(f"api-compat: rotated the old snapshot to {args.previous.relative_to(ROOT)}")
        return 0

    if not args.baseline.exists():
        print(
            f"api-compat: {args.baseline.relative_to(ROOT)} is missing; "
            "run scripts/check-api-compat.py --write once",
            file=sys.stderr,
        )
        return 2

    sys.path.insert(0, str(SHARED))
    from erp_shared.api_compat import compare_schemas

    baseline = _load(args.baseline)
    previous = _load(args.previous) if args.previous.exists() else None
    changes = compare_schemas(current, baseline, previous)
    if not changes:
        print(f"api-compat: ok - {len(baseline.get('paths', {}))} released paths remain compatible")
        return 0

    print(
        f"api-compat: {len(changes)} breaking change(s) inside /api/v1 "
        "(additive changes only; use /api/v2 or deprecate for two releases)",
        file=sys.stderr,
    )
    for change in changes:
        print(f"  - {change}", file=sys.stderr)
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
