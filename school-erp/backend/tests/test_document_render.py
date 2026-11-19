"""P5-03: layout + data -> HTML/CSS -> PDF.

Two layers of tests:

* HTML tests are deterministic and run everywhere. They pin the page geometry,
  token binding, escaping, conditions, formats, tables and font declarations.
* PDF tests print with the host's Chromium. A known layout from the shared
  fixture corpus is printed and compared against
  ``tests/golden/document_render.json``: page box, media box and extractable
  text. The Amharic test proves the Ethiopic text survives and the font is
  embedded (``FontFile2``), which is the acceptance criterion for P5-03.

The PDF tests are skipped only when the machine has no Chromium at all, the
same condition P0-23 documented; set ``DOCUMENTS_CHROMIUM_PATH`` to choose one.
"""

from __future__ import annotations

import io
import json
from pathlib import Path

import pytest
from core.documents.chromium import RenderError, find_chromium
from core.documents.layout import ImageElement, validate_layout
from core.documents.render import (
    BUNDLED_FONTS,
    FONT_DIR,
    RenderAsset,
    RenderContext,
    layout_to_html,
    page_trim_mm,
    render_layout,
)
from pypdf import PdfReader

TESTS = Path(__file__).resolve().parent
ROOT = TESTS.parents[2]
GOLDEN = json.loads((TESTS / "golden" / "document_render.json").read_text())
CORPUS = json.loads((ROOT / "shared" / "schema" / "document-layout.fixtures.json").read_text())
FIXTURES = {entry["name"]: entry["layout"] for entry in CORPUS["valid"]}

DATA = {
    "student": {
        "full_name": "Abebe Bekele",
        "full_name_am": "አበበ በቀለ",
        "guardian_name": "Bekele Tesfaye",
        "status": "promoted",
        "rank": 1,
        "total": 88,
        "next_grade": "Grade 9",
        "photo": "photo-file",
        "marks": {
            "subjects": [
                {"subject": "Maths", "score": "88.5", "grade": "A"},
                {"subject": "English", "score": "72", "grade": "B"},
            ]
        },
    },
    "document": {"code": "DOC-1", "number": "SN-0001"},
    "date": {"issued": "2026-11-19"},
    "fees": {"balance": "1234.50"},
}


def _png(width: int, height: int, colour: str) -> bytes:
    from PIL import Image

    buffer = io.BytesIO()
    Image.new("RGB", (width, height), colour).save(buffer, format="PNG")
    return buffer.getvalue()


def _assets() -> dict[str, RenderAsset]:
    return {
        "photo-file": RenderAsset(_png(200, 240, "#3b6ea5"), "photo.png", "image/png"),
        "logo-file": RenderAsset(_png(300, 120, "#a33b3b"), "logo.png", "image/png"),
    }


def _layout(elements: list[dict], page: dict | None = None, **extra) -> object:
    return validate_layout(
        {
            "version": 1,
            "page": page or {"size": "A4"},
            "elements": elements,
            **extra,
        }
    )


def _text(
    element_id: str,
    content: str,
    *,
    x: float = 10,
    y: float = 10,
    w: float = 120,
    h: float = 12,
    **style,
) -> dict:
    return {
        "id": element_id,
        "type": "text",
        "rect": {"x_mm": x, "y_mm": y, "w_mm": w, "h_mm": h},
        "content": content,
        "style": {"font_family": "Inter", "font_size_pt": 11, **style},
    }


def _normalise(text: str) -> str:
    return " ".join(text.split())


def _pdf_text(raw: bytes) -> str:
    reader = PdfReader(io.BytesIO(raw))
    return _normalise("\n".join(page.extract_text() or "" for page in reader.pages))


def _box_mm(page) -> tuple[float, float]:
    return (
        float(page.mediabox.width) / 72 * 25.4,
        float(page.mediabox.height) / 72 * 25.4,
    )


@pytest.fixture(scope="session")
def chromium() -> str:
    try:
        return find_chromium()
    except RenderError as error:  # pragma: no cover - depends on the host
        pytest.skip(f"no Chromium on this host: {error}")


# --- HTML (no browser) ------------------------------------------------------


@pytest.mark.parametrize(
    ("page", "expected"),
    [
        ({"size": "A4"}, (210.0, 297.0)),
        ({"size": "A4", "orientation": "landscape"}, (297.0, 210.0)),
        ({"size": "A5"}, (148.0, 210.0)),
        ({"size": "Letter"}, (215.9, 279.4)),
        ({"size": "Letter", "orientation": "landscape"}, (279.4, 215.9)),
        (
            {"size": "custom", "width_mm": 85.6, "height_mm": 54},
            (85.6, 54.0),
        ),
        (
            # A custom size is authored, not rotated: orientation applies to
            # presets, so the ID card keeps the dimensions it declares.
            {"size": "custom", "width_mm": 85.6, "height_mm": 54, "orientation": "portrait"},
            (85.6, 54.0),
        ),
    ],
)
def test_page_presets_and_custom_sizes(page: dict, expected: tuple[float, float]) -> None:
    assert page_trim_mm(validate_layout({"version": 1, "page": page}).page) == expected


def test_html_uses_trim_margins_bleed_and_background() -> None:
    layout = _layout(
        [_text("note", "Hello")],
        page={
            "size": "A4",
            "margins_mm": {"top": 10, "right": 20, "bottom": 30, "left": 15},
            "bleed_mm": 3,
            "background_colour": "#fdfaf3",
        },
    )
    document = layout_to_html(layout)
    assert "@page { size: 216mm 303mm; margin: 0; }" in document
    assert ".page { position: relative; width: 216mm; height: 303mm;" in document
    assert "background: #fdfaf3;" in document
    # Content starts inside the bleed and is the trim area minus the margins.
    assert "left: 18mm; top: 13mm; width: 175mm; height: 257mm;" in document


def test_html_binds_tokens_and_escapes_literals() -> None:
    layout = _layout(
        [
            _text("name", "Dear {{student.full_name}} <b>"),
            _text("missing", "Rank {{student.unknown}}."),
            {**_text("am", "{{student.full_name}}"), "format": {"script": "am"}},
        ]
    )
    document = layout_to_html(layout, RenderContext(data=DATA))
    assert "Dear Abebe Bekele &lt;b&gt;" in document
    assert "Rank ." in document
    assert "አበበ በቀለ" in document


def test_html_formats_use_the_ethiopian_calendar_and_etb() -> None:
    layout = _layout(
        [
            {
                **_text("issued", "Issued {{date.issued|ec}}"),
                "format": {"calendar": "ec"},
            },
            {
                **_text("balance", "{{fees.balance|etb}}"),
                "format": {"money": "etb", "number_decimals": 2},
            },
            {
                **_text("both", "{{date.issued}}"),
                "format": {"calendar": "both"},
            },
        ]
    )
    document = layout_to_html(layout, RenderContext(data=DATA))
    assert "Issued Hidar 10, 2019" in document
    assert "ETB 1,234.50" in document
    assert "Hidar 10, 2019 (19 Nov 2026)" in document


def test_amharic_document_defaults_to_the_amharic_script() -> None:
    layout = _layout(
        [
            _text("name", "{{student.full_name}}", font_family="Noto Sans Ethiopic"),
            _text("active", "{{student.active}}"),
        ]
    )
    data = {**DATA, "student": {**DATA["student"], "active": True}}
    english = layout_to_html(layout, RenderContext(data=data))
    amharic = layout_to_html(layout, RenderContext(data=data, locale="am"))
    assert '<html lang="en">' in english
    assert "Abebe Bekele" in english and "Yes" in english
    assert '<html lang="am">' in amharic
    # No format option names a script: the document language decides.
    assert "አበበ በቀለ" in amharic and "አዎ" in amharic


def test_html_hides_elements_whose_condition_is_false() -> None:
    layout = _layout(
        [
            {
                **_text("promoted", "Promoted to {{student.next_grade}}"),
                "visible_when": {"op": "eq", "field": "student.status", "value": "promoted"},
            },
            {
                **_text("ranked", "Ranked"),
                "visible_when": {"op": "exists", "field": "student.missing"},
            },
            {
                **_text("group", "Grouped"),
                "visible_when": {
                    "all": [
                        {"op": "gte", "field": "student.total", "value": 50},
                        {"op": "empty", "field": "student.missing"},
                    ]
                },
            },
        ]
    )
    document = layout_to_html(layout, RenderContext(data=DATA))
    assert "Promoted to Grade 9" in document
    assert "Grouped" in document
    assert "Ranked" not in document


def test_html_declares_bundled_faces_and_embeds_uploaded_fonts() -> None:
    upload_id = "3f0e8f5e-2c2f-4d3c-9b0a-5b6f6b7c8d9e"
    layout = _layout(
        [_text("brand", "Bekele", font_family="Brand Sans")],
        fonts=[{"family": "Brand Sans", "file_id": upload_id}],
    )
    document = layout_to_html(
        layout,
        RenderContext(
            assets={
                upload_id: RenderAsset((FONT_DIR / "Inter-Bold.ttf").read_bytes(), "Brand.ttf", "font/ttf")
            }
        ),
    )
    assert {name for name, _, _ in BUNDLED_FONTS["Inter"]} == {
        "Inter-Regular.ttf",
        "Inter-Bold.ttf",
    }
    assert "font-weight: 400;" in document
    assert "font-weight: 700;" in document
    assert "font-family: 'Noto Sans Ethiopic';" in document
    assert "font-family: 'Brand Sans';" in document
    assert "data:font/ttf;base64," in document
    assert document.count("@font-face") == 4  # 3 bundled faces + the upload


def test_html_renders_table_columns_summaries_and_row_values() -> None:
    layout = _layout(
        [
            {
                "id": "marks",
                "type": "table",
                "rect": {"x_mm": 10, "y_mm": 10, "w_mm": 120, "h_mm": 80},
                "table": {
                    "source": "student.marks.subjects",
                    "row_height_mm": 7,
                    "columns": [
                        {"key": "subject", "label": "Subject", "binding": "subject", "width_mm": 70},
                        {
                            "key": "score",
                            "label": "Score",
                            "binding": "score",
                            "width_mm": 30,
                            "align": "right",
                            "format": {"number_decimals": 2},
                        },
                    ],
                    "summaries": [
                        {"column": "score", "aggregate": "sum", "label": "Total"},
                        {"column": "score", "aggregate": "average", "label": "Average"},
                        {"column": "subject", "aggregate": "count", "label": "Subjects"},
                    ],
                },
                "style": {"font_family": "Inter", "font_size_pt": 9},
            }
        ]
    )
    document = layout_to_html(layout, RenderContext(data=DATA))
    assert 'table style="' in document
    assert "table-layout:fixed" in document
    assert "width:100mm;" in document  # the declared 70 + 30, not the 120 mm box
    assert '<col style="width:70mm;" />' in document
    assert "Maths" in document and "88.50" in document
    assert "Total" in document and "160.50" in document
    assert "Average" in document and "80.25" in document
    assert "Subjects 2" in document


def test_html_resolves_image_fields_through_assets() -> None:
    layout = _layout(
        [
            {
                "id": "photo",
                "type": "image",
                "rect": {"x_mm": 10, "y_mm": 10, "w_mm": 25, "h_mm": 30},
                "source": {"kind": "field", "value": "student.photo"},
                "alt": "Student photograph",
            },
            {
                "id": "empty",
                "type": "image",
                "rect": {"x_mm": 40, "y_mm": 10, "w_mm": 25, "h_mm": 30},
                "source": {"kind": "field", "value": "student.missing"},
            },
            {
                "id": "local",
                "type": "image",
                "rect": {"x_mm": 70, "y_mm": 10, "w_mm": 25, "h_mm": 30},
                "source": {"kind": "url", "value": "file:///etc/hostname"},
            },
            {
                "id": "remote",
                "type": "image",
                "rect": {"x_mm": 100, "y_mm": 10, "w_mm": 25, "h_mm": 30},
                "source": {"kind": "url", "value": "https://erp.local/logo.png"},
            },
        ]
    )
    document = layout_to_html(layout, RenderContext(data=DATA, assets=_assets()))
    assert 'src="data:image/png;base64,' in document
    assert 'alt="Student photograph"' in document
    assert 'src="https://erp.local/logo.png"' in document
    # The missing photograph and the file:// source render nothing; the
    # browser has local file access, so a layout may not name a local file.
    assert 'src="file://' not in document
    assert document.count("<img") == 2


def test_missing_chromium_path_is_reported(monkeypatch) -> None:
    monkeypatch.setenv("DOCUMENTS_CHROMIUM_PATH", "/nonexistent/chrome")
    with pytest.raises(RenderError, match="DOCUMENTS_CHROMIUM_PATH"):
        find_chromium()


def test_configured_chromium_path_wins(monkeypatch) -> None:
    binary = find_chromium()
    monkeypatch.setenv("DOCUMENTS_CHROMIUM_PATH", binary)
    assert find_chromium() == binary


# --- golden PDF properties --------------------------------------------------


def _golden_layout(fixture: str):
    layout = validate_layout(FIXTURES[fixture])
    # The shared corpus is offline: the certificate's logo URL becomes an
    # uploaded asset so the print never waits on DNS for a placeholder domain.
    for element in layout.elements:
        if isinstance(element, ImageElement) and element.id == "logo":
            element.source.kind = "file"
            element.source.value = "logo-file"
    return layout


@pytest.mark.parametrize("case", GOLDEN["cases"], ids=lambda case: case["name"])
def test_golden_document_properties(chromium: str, case: dict) -> None:
    layout = _golden_layout(case["fixture"])
    result = render_layout(
        layout,
        RenderContext(data=DATA, assets=_assets()),
        chromium_path=chromium,
    )

    assert result.engine == "chromium"
    assert list(result.page_mm) == case["page_mm"]
    assert list(result.media_mm) == case["media_mm"]
    assert result.pdf.startswith(b"%PDF")

    reader = PdfReader(io.BytesIO(result.pdf))
    assert len(reader.pages) == 1
    width, height = _box_mm(reader.pages[0])
    tolerance = GOLDEN["tolerance_mm"]
    assert abs(width - case["media_mm"][0]) <= tolerance, (width, case["media_mm"])
    assert abs(height - case["media_mm"][1]) <= tolerance, (height, case["media_mm"])

    text = _pdf_text(result.pdf)
    for expected in case["text"]:
        assert _normalise(expected) in text, f"{expected!r} missing from\n{text}"


def test_amharic_text_is_extracted_and_the_ethiopic_font_is_embedded(chromium: str) -> None:
    layout = _layout(
        [
            {
                **_text("am", "{{student.full_name}}", font_family="Noto Sans Ethiopic"),
                "format": {"script": "am"},
            },
            _text("mixed", "ትምህርት ቤት — School"),
        ]
    )
    result = render_layout(layout, RenderContext(data=DATA), chromium_path=chromium)
    text = _pdf_text(result.pdf)
    assert "አበበ በቀለ" in text
    assert "ትምህርት ቤት — School" in text
    assert b"FontFile2" in result.pdf

    fonts = [
        font.get("/BaseFont")
        for page in PdfReader(io.BytesIO(result.pdf)).pages
        for font in (page["/Resources"].get("/Font") or {}).values()
    ]
    assert any("NotoSansEthiopic" in str(name) for name in fonts), fonts


def test_qr_and_barcodes_are_drawn_with_our_own_caption(chromium: str) -> None:
    layout = _layout(
        [
            {
                "id": "qr",
                "type": "qr",
                "rect": {"x_mm": 20, "y_mm": 20, "w_mm": 40, "h_mm": 40},
                "data": "https://erp.local/verify/{{document.code}}",
            },
            {
                "id": "serial",
                "type": "barcode",
                "rect": {"x_mm": 20, "y_mm": 80, "w_mm": 80, "h_mm": 20},
                "data": "{{document.number}}",
                "symbology": "code128",
            },
            {
                "id": "ean",
                "type": "barcode",
                "rect": {"x_mm": 20, "y_mm": 120, "w_mm": 80, "h_mm": 20},
                "data": "4006381333931",
                "symbology": "ean13",
            },
        ]
    )
    result = render_layout(layout, RenderContext(data=DATA), chromium_path=chromium)
    page = PdfReader(io.BytesIO(result.pdf)).pages[0]
    assert page.images, "the QR code raster must be embedded"
    # reportlab draws barcodes as filled rectangles, so both codes are vector
    # content rather than images; the count proves bars were drawn.
    assert page.get_contents().get_data().count(b"re") > 30

    text = _pdf_text(result.pdf)
    # Our caption prints once; reportlab's own human-readable line is disabled.
    assert text.count("SN-0001") == 1, text
    assert text.count("4006381333931") == 1, text


def test_uploaded_font_is_embedded_in_the_pdf(chromium: str) -> None:
    upload_id = "3f0e8f5e-2c2f-4d3c-9b0a-5b6f6b7c8d9e"
    layout = _layout(
        [_text("brand", "Bekele", font_family="Brand Sans")],
        fonts=[{"family": "Brand Sans", "file_id": upload_id}],
    )
    result = render_layout(
        layout,
        RenderContext(
            data=DATA,
            assets={
                upload_id: RenderAsset((FONT_DIR / "Inter-Bold.ttf").read_bytes(), "Brand.ttf", "font/ttf")
            },
        ),
        chromium_path=chromium,
    )
    # The used face is the uploaded file (Inter Bold), not the bundled Inter
    # Regular that the fallback stack would otherwise supply.
    assert b"Inter-Bold" in result.pdf
    assert b"Inter-Regular" not in result.pdf
    assert _pdf_text(result.pdf) == "Bekele"


def test_a_layout_without_elements_still_prints_a_blank_page(chromium: str) -> None:
    layout = validate_layout({"version": 1, "page": {"size": "A5", "background_colour": "#f2efe6"}})
    result = render_layout(layout, chromium_path=chromium)
    page = PdfReader(io.BytesIO(result.pdf)).pages[0]
    width, height = _box_mm(page)
    assert abs(width - 148.0) <= GOLDEN["tolerance_mm"]
    assert abs(height - 210.0) <= GOLDEN["tolerance_mm"]
    assert _pdf_text(result.pdf) == ""
