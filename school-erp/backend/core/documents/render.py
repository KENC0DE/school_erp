"""Layout + data -> HTML/CSS -> PDF (P5-03).

The canvas and the printed document must agree, so this renderer consumes the
versioned layout directly: every element becomes one absolutely positioned box
in millimetre coordinates, a table becomes a real HTML table, and Chromium
prints the page at the layout's exact size. Tokens are bound in
``core.documents.binding``; this module handles geometry, styles, fonts, images,
QR codes and barcodes.

Fonts: the bundled Inter and Noto Sans Ethiopic files are declared as
``@font-face`` resources, and uploaded fonts supplied in ``RenderContext.assets``
are embedded as data URIs. A font is only embedded in the PDF if text actually
uses it, which is what the golden test checks.
"""

from __future__ import annotations

import base64
import html
import io
from collections.abc import Mapping
from dataclasses import dataclass, field
from decimal import Decimal, InvalidOperation
from pathlib import Path
from typing import Any

from core.documents.binding import (
    MISSING,
    condition_is_true,
    format_with_options,
    render_tokens,
    resolve_field,
    resolve_path,
)
from core.documents.chromium import render_pdf
from core.documents.layout import (
    BarcodeElement,
    ImageElement,
    Layout,
    Page,
    QrElement,
    ShapeElement,
    TableElement,
    TextElement,
    TextStyle,
)

FONT_DIR = Path(__file__).resolve().parents[2] / "app" / "assets" / "fonts"
# (file, css format, weight) per bundled family. Static faces rather than the
# variable font: Chromium prints a variable face as Type 3 glyph outlines, while
# a static face becomes a proper embedded TrueType subset (FontFile2).
BUNDLED_FONTS: dict[str, tuple[tuple[str, str, str], ...]] = {
    "Inter": (
        ("Inter-Regular.ttf", "truetype", "400"),
        ("Inter-Bold.ttf", "truetype", "700"),
    ),
    "Noto Sans Ethiopic": (("NotoSansEthiopic-Regular.ttf", "truetype", "400"),),
}
PAGE_SIZES_MM: dict[str, tuple[float, float]] = {
    "A4": (210.0, 297.0),
    "A5": (148.0, 210.0),
    "Letter": (215.9, 279.4),
}
BARCODE_NAMES = {
    "code128": "Code128",
    "code39": "Standard39",
    "ean13": "EAN13",
    "ean8": "EAN8",
}


@dataclass(frozen=True)
class RenderAsset:
    """An uploaded file resolved for the renderer, keyed by file id."""

    content: bytes
    filename: str = "asset"
    media_type: str = "application/octet-stream"


@dataclass
class RenderContext:
    """The data and files one render may use."""

    data: Mapping[str, Any] = field(default_factory=dict)
    assets: Mapping[str, RenderAsset] = field(default_factory=dict)
    locale: str = "en"


@dataclass(frozen=True)
class RenderResult:
    html: str
    pdf: bytes
    engine: str
    page_mm: tuple[float, float]
    media_mm: tuple[float, float]


def _mm(value: float) -> str:
    return f"{value:g}mm"


def _pt(value: float) -> str:
    return f"{value:g}pt"


def _language(context: RenderContext) -> str:
    """The document language, used as the default script for bound values."""
    return "am" if context.locale.startswith("am") else "en"


def _family(name: str) -> str:
    return "'" + name.replace("\\", "\\\\").replace("'", "\\'") + "'"


def _font_stack(name: str) -> str:
    return f"{_family(name)}, {_family('Noto Sans Ethiopic')}, {_family('Inter')}, sans-serif"


def _data_uri(content: bytes, media_type: str) -> str:
    encoded = base64.b64encode(content).decode("ascii")
    return f"data:{media_type};base64,{encoded}"


def _asset_media_type(asset: RenderAsset) -> str:
    if asset.media_type and asset.media_type != "application/octet-stream":
        return asset.media_type
    suffix = Path(asset.filename).suffix.lower()
    return {
        ".png": "image/png",
        ".jpg": "image/jpeg",
        ".jpeg": "image/jpeg",
        ".webp": "image/webp",
        ".svg": "image/svg+xml",
        ".gif": "image/gif",
        ".woff2": "font/woff2",
        ".woff": "font/woff",
        ".ttf": "font/ttf",
        ".otf": "font/otf",
    }.get(suffix, "application/octet-stream")


def page_trim_mm(page: Page) -> tuple[float, float]:
    """The trimmed page size with orientation applied, in millimetres.

    A custom size is authored, not derived: its width and height are already the
    final page, so orientation does not rotate it. A preset is a named sheet and
    orientation decides which way round it prints.
    """
    if page.size == "custom":
        return float(page.width_mm or 0), float(page.height_mm or 0)
    width, height = PAGE_SIZES_MM[page.size]
    if page.orientation == "landscape":
        return max(width, height), min(width, height)
    return min(width, height), max(width, height)


def _font_faces(layout: Layout, context: RenderContext) -> str:
    faces: list[str] = []
    for family, faces_for_family in BUNDLED_FONTS.items():
        for filename, fmt, weight in faces_for_family:
            path = FONT_DIR / filename
            if not path.is_file():
                continue
            faces.append(
                "@font-face {"
                f"font-family: {_family(family)};"
                f"src: url('{path.as_uri()}') format('{fmt}');"
                f"font-weight: {weight};"
                "}"
            )
    seen: set[str] = set()
    for font in layout.fonts:
        if font.file_id is None:
            continue
        asset = context.assets.get(str(font.file_id))
        if asset is None or font.family in seen:
            continue
        seen.add(font.family)
        media_type = _asset_media_type(asset)
        fmt = {
            "font/woff2": "woff2",
            "font/woff": "woff",
            "font/ttf": "truetype",
            "font/otf": "opentype",
        }.get(media_type, "truetype")
        faces.append(
            "@font-face {"
            f"font-family: {_family(font.family)};"
            f"src: url('{_data_uri(asset.content, media_type)}') format('{fmt}');"
            "}"
        )
    return "\n".join(faces)


def _text_css(style: TextStyle) -> str:
    decorations: list[str] = []
    if style.underline:
        decorations.append("underline")
    return "".join(
        [
            f"font-family:{_font_stack(style.font_family)};",
            f"font-size:{_pt(style.font_size_pt)};",
            "font-weight:700;" if style.bold else "font-weight:400;",
            "font-style:italic;" if style.italic else "font-style:normal;",
            f"text-decoration:{' '.join(decorations) or 'none'};",
            f"color:{style.colour};",
            f"line-height:{style.line_height};",
            f"letter-spacing:{_pt(style.letter_spacing_pt)};",
            # Inter's contextual alternates replace "-" with a glyph that has
            # no Unicode mapping, so the PDF would extract a private-use code
            # point. Documents are searchable text first, so keep the cmap.
            "font-feature-settings:'calt' 0;",
        ]
    )


def _box_css(element: Any) -> str:
    rect = element.rect
    css = (
        f"left:{_mm(rect.x_mm)};top:{_mm(rect.y_mm)};"
        f"width:{_mm(rect.w_mm)};height:{_mm(rect.h_mm)};"
        f"z-index:{element.z};"
    )
    if element.rotation_deg:
        css += f"transform:rotate({element.rotation_deg:g}deg);transform-origin:center center;"
    return css


def _image_source(source: Any, context: RenderContext) -> str | None:
    """Turn an image source into a URL the browser can load.

    A ``field`` source resolves against the bound data; the value may already be
    a URL or data URI, or the id of an uploaded file in ``context.assets``. A
    missing or empty value renders nothing at all, which is what a template with
    an optional photograph wants.
    """
    if source.kind == "url":
        # Only web and inline images: the browser runs with local file access,
        # so a layout must not be able to pull an arbitrary file into a PDF.
        if source.value.startswith(("http://", "https://", "data:image/")):
            return source.value
        return None
    if source.kind == "file":
        asset = context.assets.get(source.value)
        return None if asset is None else _data_uri(asset.content, _asset_media_type(asset))
    value = resolve_field(context.data, source.value, "en")
    if value is MISSING or value is None or value == "":
        return None
    text = str(value)
    if text.startswith(("http://", "https://", "data:")):
        return text
    asset = context.assets.get(text)
    if asset is not None:
        return _data_uri(asset.content, _asset_media_type(asset))
    return None


def _qr_png(data: str, foreground: str, background: str, level: str) -> str:
    import qrcode

    code = qrcode.QRCode(
        error_correction=getattr(qrcode.constants, f"ERROR_CORRECT_{level}"),
        box_size=8,
        border=2,
    )
    code.add_data(data)
    code.make(fit=True)
    image = code.make_image(fill_color=foreground, back_color=background)
    buffer = io.BytesIO()
    image.save(buffer, format="PNG")
    return _data_uri(buffer.getvalue(), "image/png")


def _barcode_svg(symbology: str, data: str, foreground: str) -> str:
    from reportlab.graphics import renderSVG
    from reportlab.graphics.barcode import createBarcodeDrawing

    drawing = createBarcodeDrawing(
        BARCODE_NAMES[symbology],
        value=data,
        barHeight=30,
        barWidth=1,
        # The caption is our own HTML: it uses the template's font and colour,
        # and disabling it here avoids reportlab printing a second copy.
        humanReadable=False,
    )
    svg = renderSVG.drawToString(drawing)
    # Paths inherit fill from the root, so one attribute recolours every bar.
    svg = svg.replace("<svg ", f'<svg fill="{foreground}" ', 1)
    return _data_uri(svg.encode("utf-8"), "image/svg+xml")


def _render_text(element: TextElement, context: RenderContext) -> str:
    content = render_tokens(
        element.content,
        context.data,
        element.format,
        default_script=_language(context),
    )
    align = {"left": "flex-start", "center": "center", "right": "flex-end"}[element.align]
    vertical = {"top": "flex-start", "middle": "center", "bottom": "flex-end"}[element.vertical_align]
    white_space = "pre-wrap" if element.wrap else "nowrap"
    inner = (
        f"display:flex;align-items:{vertical};height:100%;width:100%;"
        f"justify-content:{align};overflow:{'visible' if not element.wrap else 'hidden'};"
    )
    text_style = _text_css(element.style) + (
        f"text-align:{element.align};white-space:{white_space};overflow-wrap:anywhere;"
    )
    return (
        f'<div class="el" style="{_box_css(element)}">'
        f'<div style="{inner}"><div style="{text_style}">{html.escape(content)}</div></div>'
        "</div>"
    )


def _render_image(element: ImageElement, context: RenderContext) -> str:
    source = _image_source(element.source, context)
    if source is None:
        return ""
    alt = html.escape(element.alt or "", quote=True)
    return (
        f'<div class="el" style="{_box_css(element)}">'
        f'<img src="{html.escape(source, quote=True)}" alt="{alt}" '
        f'style="width:100%;height:100%;object-fit:{element.fit};" />'
        "</div>"
    )


def _render_shape(element: ShapeElement) -> str:
    rect = element.rect
    stroke_css = ""
    if element.stroke is not None:
        stroke_css = f"border:{_mm(element.stroke.width_mm)} solid {element.stroke.colour};"
    if element.shape == "line":
        stroke = element.stroke
        colour = stroke.colour if stroke else "#111111"
        width = stroke.width_mm if stroke else 0.2
        svg = (
            f'<svg width="100%" height="100%" viewBox="0 0 {rect.w_mm:g} {rect.h_mm:g}" '
            'preserveAspectRatio="none" xmlns="http://www.w3.org/2000/svg">'
            f'<line x1="0" y1="{rect.h_mm / 2:g}" x2="{rect.w_mm:g}" '
            f'y2="{rect.h_mm / 2:g}" stroke="{colour}" stroke-width="{width:g}" />'
            "</svg>"
        )
        return f'<div class="el" style="{_box_css(element)}">{svg}</div>'
    fill = f"background:{element.fill};" if element.fill else ""
    radius = (
        "border-radius:50%;" if element.shape == "ellipse" else f"border-radius:{_mm(element.radius_mm)};"
    )
    return f'<div class="el" style="{_box_css(element)}{fill}{stroke_css}{radius}"></div>'


def _render_qr(element: QrElement, context: RenderContext) -> str:
    data = render_tokens(element.data, context.data)
    image = _qr_png(data, element.foreground, element.background, element.error_correction)
    return (
        f'<div class="el" style="{_box_css(element)}background:{element.background};">'
        f'<img src="{image}" alt="QR code" style="width:100%;height:100%;image-rendering:pixelated;" />'
        "</div>"
    )


def _render_barcode(element: BarcodeElement, context: RenderContext) -> str:
    data = render_tokens(element.data, context.data)
    svg = _barcode_svg(element.symbology, data, element.foreground)
    caption = ""
    if element.show_text:
        caption = (
            '<div style="font-family:'
            + _font_stack("Inter")
            + f";font-size:8pt;text-align:center;color:{element.foreground};"
            "white-space:nowrap;font-feature-settings:'calt' 0;\">" + html.escape(data) + "</div>"
        )
    return (
        f'<div class="el" style="{_box_css(element)}background:{element.background};'
        'display:flex;flex-direction:column;">'
        f'<img src="{svg}" alt="Barcode" style="width:100%;flex:1 1 auto;object-fit:fill;" />'
        f"{caption}</div>"
    )


def _table_rows(element: TableElement, context: RenderContext) -> list[Mapping[str, Any]]:
    rows = resolve_path(context.data, element.table.source)
    if isinstance(rows, Mapping):
        rows = rows.get("items")
    if not isinstance(rows, (list, tuple)):
        return []
    return [row for row in rows if isinstance(row, Mapping)]


def _cell(row: Mapping[str, Any], binding: str | None, script: str) -> Any:
    if binding is None:
        return ""
    if binding.startswith("items."):
        binding = binding[len("items.") :]
    return resolve_field(row, binding, script)


def _summary_value(
    rows: list[Mapping[str, Any]],
    column: Any,
    aggregate: str,
    language: str,
) -> str:
    script = (column.format.script if column.format else None) or language
    values = [_cell(row, column.binding, script) for row in rows]
    if aggregate == "count":
        return str(sum(1 for value in values if value not in (None, "", MISSING)))
    numbers: list[Decimal] = []
    for value in values:
        text = format_with_options(value, None, default_script=language)
        try:
            numbers.append(Decimal(text.replace(",", "")))
        except (InvalidOperation, AttributeError):
            continue
    if not numbers:
        return "0"
    total = sum(numbers, Decimal(0))
    if aggregate == "average":
        # Exact decimal division, rounded to the column's advertised precision.
        places = getattr(column.format, "number_decimals", None)
        places = 2 if places is None else places
        total = (total / len(numbers)).quantize(Decimal(1).scaleb(-places))
    return format_with_options(total, column.format, default_script=language)


def _column_script(column: Any, language: str) -> str:
    return (column.format.script if column.format else None) or language


def _render_table(element: TableElement, context: RenderContext) -> str:
    table = element.table
    language = _language(context)
    rows = _table_rows(element, context)
    widths = [column.width_mm for column in table.columns]
    if all(widths):
        # Honour the author's column widths instead of stretching them to the
        # element box; a table narrower than its box simply leaves space.
        table_width = min(sum(widths), element.rect.w_mm)
    else:
        table_width = element.rect.w_mm
    colgroup = "".join(
        f'<col style="width:{_mm(column.width_mm)};" />' if column.width_mm else "<col />"
        for column in table.columns
    )
    headers = "".join(
        f'<th style="text-align:{column.align};padding:0 1mm;">{html.escape(column.label)}</th>'
        for column in table.columns
    )
    head = ""
    if table.show_header:
        group = "table-header-group" if table.repeat_header else "table-row-group"
        head = f'<thead style="display:{group};"><tr>{headers}</tr></thead>'
    body_rows = []
    for row in rows:
        cells = []
        for column in table.columns:
            value = _cell(row, column.binding, _column_script(column, language))
            text = format_with_options(value, column.format, default_script=language)
            cells.append(
                f'<td style="text-align:{column.align};height:{_mm(table.row_height_mm)};'
                f'padding:0 1mm;">{html.escape(text)}</td>'
            )
        body_rows.append(f"<tr>{''.join(cells)}</tr>")
    body = f"<tbody>{''.join(body_rows)}</tbody>" if body_rows else ""
    foot_rows = []
    for summary in table.summaries:
        column = next(item for item in table.columns if item.key == summary.column)
        value = _summary_value(rows, column, summary.aggregate, language)
        cells = []
        for index, item in enumerate(table.columns):
            if index == 0 and item.key != summary.column:
                cells.append(
                    f'<td style="text-align:{item.align};padding:0 1mm;">{html.escape(summary.label)}</td>'
                )
            elif item.key == summary.column:
                label = f"{summary.label} " if index == 0 else ""
                cells.append(
                    f'<td style="text-align:{item.align};padding:0 1mm;">'
                    f"{html.escape(label)}{html.escape(value)}</td>"
                )
            else:
                cells.append('<td style="padding:0 1mm;"></td>')
        foot_rows.append(f"<tr>{''.join(cells)}</tr>")
    foot = f"<tfoot>{''.join(foot_rows)}</tfoot>" if foot_rows else ""
    style = _text_css(element.style)
    return (
        f'<div class="el" style="{_box_css(element)}overflow:hidden;">'
        f'<table style="{style}width:{_mm(table_width)};table-layout:fixed;border-collapse:collapse;">'
        f"<colgroup>{colgroup}</colgroup>{head}{body}{foot}</table>"
        "</div>"
    )


def _render_element(element: Any, context: RenderContext) -> str:
    if element.type == "text":
        return _render_text(element, context)
    if element.type == "image":
        return _render_image(element, context)
    if element.type == "shape":
        return _render_shape(element)
    if element.type == "table":
        return _render_table(element, context)
    if element.type == "qr":
        return _render_qr(element, context)
    if element.type == "barcode":
        return _render_barcode(element, context)
    return ""  # pragma: no cover - the schema has no other type


def layout_to_html(layout: Layout, context: RenderContext | None = None) -> str:
    """Render the layout's HTML at its exact physical size."""
    context = context or RenderContext()
    page = layout.page
    trim_w, trim_h = page_trim_mm(page)
    bleed = float(page.bleed_mm)
    media_w = trim_w + 2 * bleed
    media_h = trim_h + 2 * bleed
    content_w = max(trim_w - float(page.margins_mm.left) - float(page.margins_mm.right), 1.0)
    content_h = max(trim_h - float(page.margins_mm.top) - float(page.margins_mm.bottom), 1.0)
    background = page.background_colour or "#ffffff"
    language = "am" if context.locale.startswith("am") else "en"
    elements = "".join(
        _render_element(element, context)
        for element in layout.elements
        if condition_is_true(element.visible_when, context.data)
    )
    fonts = _font_faces(layout, context)
    return f"""<!doctype html>
<html lang="{language}">
<head>
<meta charset="utf-8">
<style>
@page {{ size: {_mm(media_w)} {_mm(media_h)}; margin: 0; }}
* {{ box-sizing: border-box; }}
html, body {{ margin: 0; padding: 0; }}
body {{ -webkit-print-color-adjust: exact; print-color-adjust: exact; }}
{fonts}
.page {{ position: relative; width: {_mm(media_w)}; height: {_mm(media_h)}; background: {background}; overflow: hidden; }}
.content {{ position: absolute; left: {_mm(bleed + float(page.margins_mm.left))}; top: {_mm(bleed + float(page.margins_mm.top))}; width: {_mm(content_w)}; height: {_mm(content_h)}; }}
.el {{ position: absolute; overflow: visible; }}
</style>
</head>
<body>
<div class="page"><div class="content">{elements}</div></div>
</body>
</html>"""


def render_layout(
    layout: Layout,
    context: RenderContext | None = None,
    *,
    chromium_path: str | None = None,
) -> RenderResult:
    """Render the layout to HTML and PDF, returning both and the page size."""
    context = context or RenderContext()
    document = layout_to_html(layout, context)
    pdf = render_pdf(document, chromium_path=chromium_path)
    trim = page_trim_mm(layout.page)
    bleed = float(layout.page.bleed_mm)
    return RenderResult(
        html=document,
        pdf=pdf,
        engine="chromium",
        page_mm=trim,
        media_mm=(trim[0] + 2 * bleed, trim[1] + 2 * bleed),
    )


__all__ = [
    "BARCODE_NAMES",
    "BUNDLED_FONTS",
    "PAGE_SIZES_MM",
    "RenderAsset",
    "RenderContext",
    "RenderResult",
    "layout_to_html",
    "page_trim_mm",
    "render_layout",
]
