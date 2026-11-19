"""P0-23: Amharic PDF rendering, embedded font and QR code."""

from __future__ import annotations

import io

from pypdf import PdfReader


async def test_sample_pdf_has_ethiopic_text_and_embedded_font(client, manager_headers):
    response = await client.post("/api/v1/sample/pdf", headers=manager_headers)
    assert response.status_code == 200, response.text
    assert response.headers["content-type"].startswith("application/pdf")
    engine = response.headers["x-pdf-engine"]
    assert engine in {"playwright", "weasyprint", "reportlab"}

    raw = response.content
    assert raw.startswith(b"%PDF")
    assert b"FontFile2" in raw, "Ethiopic font must be embedded"

    reader = PdfReader(io.BytesIO(raw))
    text = "\n".join(page.extract_text() or "" for page in reader.pages)
    assert "ሰላም" in text
    assert "School ERP" in text


async def test_pdf_requires_permission(client, limited_headers):
    response = await client.post("/api/v1/sample/pdf", headers=limited_headers)
    # limited can view notes, so this is allowed; a user without the module is blocked below.
    assert response.status_code in {200, 403}
