#!/usr/bin/env python3
"""Deterministic i18n checks for CI.

1. Every literal key used through ``t("...")`` in the web/mobile source exists in
   the default English bundle (core or a module's namespace). This is fatal.
2. An Amharic bundle must never contain a key that English does not (a stale or
   misspelled key). This is fatal.
3. Missing Amharic keys are reported so the Translation Editor backlog is
   visible in CI, but they do not fail the build while translation is in
   progress. ``--strict-am`` promotes them to failures.

The check is offline and does not need the API running: it reads the JSON files
that the seed/startup loads into ``translation_entries``.
"""

from __future__ import annotations

import json
import os
import re
import sys
from pathlib import Path

ROOT = Path(os.environ.get("ERP_I18N_ROOT") or Path(__file__).resolve().parents[1]).resolve()
BACKEND = ROOT / "school-erp" / "backend"
CORE_I18N = BACKEND / "core" / "i18n"
MODULES_DIR = BACKEND / "modules"
UI_DIRS = [
    ROOT / "school-erp" / "web" / "src",
    ROOT / "owner" / "controller-web" / "src",
    ROOT / "owner" / "mobile" / "src",
]
# Client-local message maps are legitimate for apps that do not load a bundle
# from the school API yet (for example the controller web, per DECISIONS.md).
LOCAL_MESSAGE_FILES = [
    ROOT / "owner" / "controller-web" / "src" / "i18n.ts",
    ROOT / "owner" / "mobile" / "src" / "i18n" / "ui-messages.ts",
]
LOCAL_KEY_PATTERN = re.compile(r"^\s*['\"]([^'\"]+)['\"]\s*:", re.MULTILINE)

SOURCE_SUFFIXES = {".ts", ".tsx", ".js", ".jsx"}
# t("key"), t('key'), $t("key"), i18n.t("key") - literals only; dynamic keys are skipped.
KEY_PATTERN = re.compile(r"(?:\bt|\$t|i18n\.t)\(\s*(['\"])([^'\"]+)\1")


def load_json(path: Path) -> dict[str, str]:
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        raise SystemExit(f"i18n: {path.relative_to(ROOT)} is not valid JSON: {exc}") from exc
    if not isinstance(data, dict):
        raise SystemExit(f"i18n: {path.relative_to(ROOT)} must contain a JSON object")
    return {str(key): str(value) for key, value in data.items()}


def bundles() -> list[tuple[str, Path, Path]]:
    """Return (namespace, en_path, am_path) for every default bundle."""
    found: list[tuple[str, Path, Path]] = []
    core_en, core_am = CORE_I18N / "en.json", CORE_I18N / "am.json"
    if core_en.exists() and core_am.exists():
        found.append(("core", core_en, core_am))
    if MODULES_DIR.exists():
        for module_dir in sorted(p for p in MODULES_DIR.iterdir() if p.is_dir()):
            en, am = module_dir / "i18n" / "en.json", module_dir / "i18n" / "am.json"
            if en.exists() and am.exists():
                found.append((module_dir.name, en, am))
    return found


def collect_keys() -> tuple[set[str], list[str], list[str]]:
    problems: list[str] = []
    missing_am: list[str] = []
    keys: set[str] = set()
    for namespace, en_path, am_path in bundles():
        en = load_json(en_path)
        am = load_json(am_path)
        if namespace == "core":
            keys.update(en)
        else:
            keys.update(f"{namespace}.{key}" for key in en)
        for key in sorted(set(en) - set(am)):
            missing_am.append(f"{namespace}:{key}")
        for key in sorted(set(am) - set(en)):
            problems.append(f"{am_path.relative_to(ROOT)}: unknown key '{key}' (missing in en)")

    for path in LOCAL_MESSAGE_FILES:
        if not path.exists():
            continue
        text = path.read_text(encoding="utf-8", errors="replace")
        keys.update(match.group(1) for match in LOCAL_KEY_PATTERN.finditer(text))
    return keys, problems, missing_am


def collect_references() -> dict[str, list[str]]:
    references: dict[str, list[str]] = {}
    for directory in UI_DIRS:
        if not directory.exists():
            continue
        for path in sorted(directory.rglob("*")):
            if not path.is_file() or path.suffix not in SOURCE_SUFFIXES:
                continue
            text = path.read_text(encoding="utf-8", errors="replace")
            for match in KEY_PATTERN.finditer(text):
                references.setdefault(match.group(2), []).append(str(path.relative_to(ROOT)))
    return references


def main() -> int:
    strict_am = "--strict-am" in sys.argv[1:]
    keys, problems, missing_am = collect_keys()
    references = collect_references()

    for key in sorted(references):
        if key not in keys:
            locations = ", ".join(sorted(set(references[key])))
            problems.append(f"missing i18n key '{key}' (used in {locations})")

    if missing_am:
        label = "problem" if strict_am else "report"
        print(
            f"i18n {label}: {len(missing_am)} missing Amharic key(s) "
            "(use the Translation Editor to fill them)"
        )
        for key in missing_am:
            print(f"  - {key}")
        if strict_am:
            problems.extend(f"missing am key '{key}'" for key in missing_am)

    scanned = sum(1 for directory in UI_DIRS if directory.exists())
    if problems:
        print(f"i18n: {len(problems)} problem(s) found", file=sys.stderr)
        for problem in problems:
            print(f"  - {problem}", file=sys.stderr)
        return 1

    print(
        f"i18n: ok - {len(keys)} keys across {len(bundles())} bundle(s), "
        f"{len(references)} referenced key(s), {scanned} UI source dir(s)"
    )
    if missing_am:
        print(f"i18n: {len(missing_am)} Amharic key(s) still need translation")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
