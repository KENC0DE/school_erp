"""Headless Chromium wrapper for the document renderer (P5-03).

ARCH §9.8 and the P0-23 decision call for HTML/CSS to PDF through Chromium.
This module finds a Chromium binary, prints one HTML file to PDF and returns the
bytes. It uses the browser Playwright already installs for the e2e suite
(``~/.cache/ms-playwright``) and needs no Python Playwright package, which keeps
the renderer available in the API process and in a background job alike.

Set ``DOCUMENTS_CHROMIUM_PATH`` (or ``CHROMIUM_PATH``) to choose a binary in
deployments that install Chromium system-wide.
"""

from __future__ import annotations

import os
import shutil
import subprocess
import tempfile
from pathlib import Path

CHROMIUM_ENV_VARS = ("DOCUMENTS_CHROMIUM_PATH", "CHROMIUM_PATH")
_EXECUTABLE_NAMES = (
    "chromium",
    "chromium-browser",
    "google-chrome",
    "google-chrome-stable",
    "chrome",
)


class RenderError(RuntimeError):
    """Chromium is missing or failed to produce a PDF."""


def _playwright_candidates() -> list[Path]:
    roots: list[Path] = []
    configured = os.environ.get("PLAYWRIGHT_BROWSERS_PATH")
    if configured and configured not in {"0", "1"}:
        roots.append(Path(configured))
    roots.append(Path.home() / ".cache" / "ms-playwright")
    found: list[Path] = []
    for root in roots:
        if not root.is_dir():
            continue
        for directory in sorted(root.glob("chromium-*"), reverse=True):
            found.extend(
                path
                for path in (
                    directory / "chrome-linux64" / "chrome",
                    directory / "chrome-linux" / "chrome",
                )
                if path.is_file()
            )
        for directory in sorted(root.glob("chromium_headless_shell-*"), reverse=True):
            found.extend(
                path
                for path in (
                    directory / "chrome-headless-shell-linux64" / "chrome-headless-shell",
                    directory / "chrome-headless-shell-linux" / "chrome-headless-shell",
                )
                if path.is_file()
            )
    return found


def find_chromium() -> str:
    """The first usable Chromium binary, or raise with a clear remedy."""
    for variable in CHROMIUM_ENV_VARS:
        configured = os.environ.get(variable)
        if configured:
            path = Path(configured)
            if path.is_file():
                return str(path)
            raise RenderError(f"{variable} points at a missing file: {configured}")
    for name in _EXECUTABLE_NAMES:
        resolved = shutil.which(name)
        if resolved:
            return resolved
    for path in _playwright_candidates():
        return str(path)
    raise RenderError(
        "No Chromium binary found. Install Chromium, or run "
        "'pnpm exec playwright install chromium', or set DOCUMENTS_CHROMIUM_PATH."
    )


def render_pdf(
    html: str,
    *,
    chromium_path: str | None = None,
    timeout: int = 120,
) -> bytes:
    """Print one HTML document to PDF with CSS page sizes honoured."""
    binary = chromium_path or find_chromium()
    with tempfile.TemporaryDirectory(prefix="erp-document-") as tmp:
        source = Path(tmp) / "document.html"
        target = Path(tmp) / "document.pdf"
        source.write_text(html, encoding="utf-8")
        command = [
            binary,
            "--headless",
            "--no-sandbox",
            "--disable-gpu",
            "--disable-dev-shm-usage",
            "--allow-file-access-from-files",
            "--no-pdf-header-footer",
            "--run-all-compositor-stages-before-draw",
            f"--print-to-pdf={target}",
            source.as_uri(),
        ]
        try:
            completed = subprocess.run(
                command,
                capture_output=True,
                text=True,
                timeout=timeout,
                check=False,
            )
        except OSError as exc:
            raise RenderError(f"Chromium could not start: {exc}") from exc
        except subprocess.TimeoutExpired as exc:
            raise RenderError(f"Chromium did not finish within {timeout}s") from exc
        if completed.returncode != 0 or not target.is_file():
            detail = (completed.stderr or completed.stdout or "").strip().splitlines()
            tail = " | ".join(detail[-5:]) if detail else "no output"
            raise RenderError(f"Chromium failed to print the document: {tail}")
        content = target.read_bytes()
        if not content.startswith(b"%PDF"):
            raise RenderError("Chromium produced a file that is not a PDF")
        return content


__all__ = ["CHROMIUM_ENV_VARS", "RenderError", "find_chromium", "render_pdf"]
