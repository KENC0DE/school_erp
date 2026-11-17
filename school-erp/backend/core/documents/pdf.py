"""PDF spike: Chromium first, WeasyPrint second, ReportLab fallback (P0-23).

Document Studio reuses this interface in Phase 5. The renderer chosen for
production is recorded in docs/DECISIONS.md.
"""

from __future__ import annotations

import base64
import io
from dataclasses import dataclass
from pathlib import Path

FONT_PATH = Path(__file__).resolve().parents[2] / "app" / "assets" / "fonts" / "NotoSansEthiopic-Regular.ttf"
AMHARIC = "ሰላም ዓለም! ይህ የአማርኛ ጽሑፍ ናሙና ነው።"
LATIN = "School ERP — Amharic rendering spike"


@dataclass
class PdfResult:
    content: bytes
    engine: str


def _qr_png(data: str) -> bytes:
    import qrcode

    qr = qrcode.QRCode(box_size=6, border=2)
    qr.add_data(data)
    qr.make(fit=True)
    image = qr.make_image(fill_color="black", back_color="white")
    buffer = io.BytesIO()
    image.save(buffer, format="PNG")
    return buffer.getvalue()


def build_html(*, title: str = "Demo Academy", qr_data: str = "erpapp://school/DEMO") -> str:
    font_url = FONT_PATH.as_uri()
    qr = base64.b64encode(_qr_png(qr_data)).decode()
    return f"""<!doctype html>
<html lang="am">
<head>
<meta charset="utf-8">
<style>
@font-face {{ font-family: 'Ethiopic'; src: url('{font_url}') format('truetype'); }}
@page {{ size: A4; margin: 20mm; }}
body {{ font-family: 'Ethiopic', sans-serif; color: #14231c; }}
h1 {{ font-size: 26px; margin-bottom: 4px; }}
.latin {{ font-family: 'Helvetica', sans-serif; }}
.card {{ border: 1px solid #c8d6cf; border-radius: 12px; padding: 24px; }}
.qr {{ width: 120px; height: 120px; margin-top: 24px; }}
</style>
</head>
<body>
<div class="card">
  <h1>{AMHARIC}</h1>
  <p class="latin">{LATIN}</p>
  <p>{title}</p>
  <p class="latin">Generated for the Phase 0 PDF spike. This document proves embedded Ethiopic text and a QR code.</p>
  <img class="qr" alt="QR" src="data:image/png;base64,{qr}">
</div>
</body>
</html>"""


async def render_with_playwright(html: str) -> bytes:
    from playwright.async_api import async_playwright

    async with async_playwright() as playwright:
        browser = await playwright.chromium.launch()
        try:
            page = await browser.new_page()
            await page.set_content(html, wait_until="load")
            pdf = await page.pdf(format="A4", print_background=True)
            return pdf
        finally:
            await browser.close()


def render_with_weasyprint(html: str) -> bytes:
    from weasyprint import HTML

    return HTML(string=html, base_url=str(FONT_PATH.parent)).write_pdf()


def render_with_reportlab(*, title: str = "Demo Academy", qr_data: str = "erpapp://school/DEMO") -> bytes:
    from reportlab.lib.pagesizes import A4
    from reportlab.lib.utils import ImageReader
    from reportlab.pdfbase import pdfmetrics
    from reportlab.pdfbase.ttfonts import TTFont
    from reportlab.pdfgen import canvas

    if "Ethiopic" not in pdfmetrics.getRegisteredFontNames():
        pdfmetrics.registerFont(TTFont("Ethiopic", str(FONT_PATH)))
    buffer = io.BytesIO()
    pdf = canvas.Canvas(buffer, pagesize=A4)
    width, height = A4
    pdf.setTitle(title)
    pdf.setFont("Ethiopic", 18)
    pdf.drawString(52, height - 80, AMHARIC)
    pdf.setFont("Helvetica-Bold", 15)
    pdf.drawString(52, height - 112, LATIN)
    pdf.setFont("Helvetica", 10)
    pdf.drawString(52, height - 136, "Embedded Ethiopic font + QR code, generated for the Phase 0 spike.")
    pdf.drawString(52, height - 152, "Scan the QR code to test the school deep link.")
    qr = ImageReader(io.BytesIO(_qr_png(qr_data)))
    pdf.drawImage(qr, 52, height - 320, width=130, height=130)
    pdf.showPage()
    pdf.save()
    return buffer.getvalue()


async def render_sample_pdf(
    *, title: str = "Demo Academy", qr_data: str = "erpapp://school/DEMO"
) -> PdfResult:
    html = build_html(title=title, qr_data=qr_data)
    try:
        return PdfResult(content=await render_with_playwright(html), engine="playwright")
    except Exception:
        pass
    try:
        return PdfResult(content=render_with_weasyprint(html), engine="weasyprint")
    except Exception:
        pass
    return PdfResult(content=render_with_reportlab(title=title, qr_data=qr_data), engine="reportlab")
