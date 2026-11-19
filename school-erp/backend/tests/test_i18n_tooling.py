"""P1-20: i18n CI checks and the Amharic backlog report."""

from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
SCRIPT = ROOT / "scripts" / "check-i18n.py"


def build_tree(tmp_path: Path, en: dict[str, str], am: dict[str, str], source: str) -> Path:
    backend = tmp_path / "school-erp" / "backend"
    i18n = backend / "core" / "i18n"
    i18n.mkdir(parents=True)
    (i18n / "en.json").write_text(json.dumps(en), encoding="utf-8")
    (i18n / "am.json").write_text(json.dumps(am), encoding="utf-8")
    (backend / "modules").mkdir()
    web = tmp_path / "school-erp" / "web" / "src"
    web.mkdir(parents=True)
    (web / "app.tsx").write_text(source, encoding="utf-8")
    return tmp_path


def run(root: Path, *args: str) -> subprocess.CompletedProcess[str]:
    env = {**os.environ, "ERP_I18N_ROOT": str(root)}
    return subprocess.run(
        [sys.executable, str(SCRIPT), *args],
        cwd=ROOT,
        env=env,
        text=True,
        capture_output=True,
        check=False,
    )


def test_the_repository_bundles_pass():
    result = run(ROOT)
    assert result.returncode == 0, result.stderr
    assert "i18n: ok" in result.stdout


def test_missing_amharic_keys_are_reported_but_do_not_fail(tmp_path):
    root = build_tree(
        tmp_path,
        {"app.name": "School ERP", "nav.home": "Home"},
        {"app.name": "የትምህርት ቤት ኢአርፒ"},
        'const label = t("nav.home");\n',
    )
    result = run(root)
    assert result.returncode == 0, result.stderr
    assert "1 missing Amharic key(s)" in result.stdout
    assert "core:nav.home" in result.stdout
    assert "still need translation" in result.stdout


def test_strict_am_turns_the_report_into_a_failure(tmp_path):
    root = build_tree(
        tmp_path,
        {"app.name": "School ERP"},
        {"app.name": "የትምህርት ቤት ኢአርፒ", "nav.home": "መነሻ"},
        "const label = 1;\n",
    )
    # An Amharic key with no English source is always fatal.
    result = run(root)
    assert result.returncode == 1
    assert "unknown key 'nav.home'" in result.stderr

    am = {"app.name": "የትምህርት ቤት ኢአርፒ"}
    en = {"app.name": "School ERP", "nav.home": "Home"}
    (root / "school-erp/backend/core/i18n/en.json").write_text(json.dumps(en))
    (root / "school-erp/backend/core/i18n/am.json").write_text(json.dumps(am))
    strict = run(root, "--strict-am")
    assert strict.returncode == 1
    assert "missing am key 'core:nav.home'" in strict.stderr


def test_a_referenced_key_missing_from_english_fails(tmp_path):
    root = build_tree(
        tmp_path,
        {"app.name": "School ERP"},
        {"app.name": "የትምህርት ቤት ኢአርፒ"},
        'const label = t("nav.home");\n',
    )
    result = run(root)
    assert result.returncode == 1
    assert "missing i18n key 'nav.home'" in result.stderr
    assert "app.tsx" in result.stderr


def test_the_ethiopic_font_ships_with_web_and_mobile():
    web_font = ROOT / "school-erp/web/public/fonts/NotoSansEthiopic-Regular.ttf"
    mobile_font = ROOT / "owner/mobile/assets/fonts/NotoSansEthiopic-Regular.ttf"
    assert web_font.is_file() and web_font.stat().st_size > 100_000
    assert mobile_font.is_file() and mobile_font.stat().st_size > 100_000
    assert (web_font.parent / "OFL.txt").is_file()
    assert (mobile_font.parent / "OFL.txt").is_file()

    css = (ROOT / "school-erp/web/src/styles.css").read_text(encoding="utf-8")
    assert "@font-face" in css
    assert "/fonts/NotoSansEthiopic-Regular.ttf" in css
    layout = (ROOT / "owner/mobile/app/_layout.tsx").read_text(encoding="utf-8")
    assert "useFonts" in layout
    assert "NotoSansEthiopic-Regular.ttf" in layout
