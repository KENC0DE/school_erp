"""P5-01: the Pydantic side of the version 1 document layout schema.

The canonical definition and the generated JSON Schema live in
``shared/schema``. This suite validates the same fixture corpus as the Zod
suite (``shared/ts/documents/tests/layout.test.ts``) and checks the models
against the canonical artifact, so the two implementations cannot drift.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any, get_args

import pytest
from core.documents.layout import (
    ELEMENT_TYPES,
    LAYOUT_SCHEMA_ID,
    LAYOUT_SCHEMA_VERSION,
    Element,
    Layout,
    Page,
    validate_layout,
)
from pydantic import ValidationError

ROOT = Path(__file__).resolve().parents[3]
SCHEMA_PATH = ROOT / "shared" / "schema" / "document-layout.v1.json"
FIXTURES_PATH = ROOT / "shared" / "schema" / "document-layout.fixtures.json"

CORPUS: dict[str, list[dict[str, Any]]] = json.loads(FIXTURES_PATH.read_text())
CANONICAL: dict[str, Any] = json.loads(SCHEMA_PATH.read_text())


def _element_schemas() -> dict[str, dict[str, Any]]:
    entries = CANONICAL["properties"]["elements"]["items"]["oneOf"]
    return {entry["properties"]["type"]["const"]: entry for entry in entries}


def _assert_subset(actual: Any, expected: Any, path: str = "$") -> None:
    """Every value the fixture declares must survive validation unchanged."""
    if isinstance(expected, list):
        assert isinstance(actual, list), f"{path} should be a list"
        assert len(actual) == len(expected), f"{path} length"
        for index, item in enumerate(expected):
            _assert_subset(actual[index], item, f"{path}[{index}]")
        return
    if isinstance(expected, dict):
        assert isinstance(actual, dict), f"{path} should be an object"
        for key, value in expected.items():
            assert key in actual, f"{path}.{key} is missing"
            _assert_subset(actual[key], value, f"{path}.{key}")
        return
    assert actual == expected, f"{path}: {actual!r} != {expected!r}"


def test_corpus_has_both_outcomes() -> None:
    assert len(CORPUS["valid"]) >= 4
    assert len(CORPUS["invalid"]) >= 15
    names = [entry["name"] for entry in CORPUS["valid"] + CORPUS["invalid"]]
    assert len(names) == len(set(names))


@pytest.mark.parametrize("fixture", CORPUS["valid"], ids=lambda f: f["name"])
def test_valid_fixture_round_trips(fixture: dict[str, Any]) -> None:
    layout = validate_layout(fixture["layout"])
    dumped = layout.model_dump(mode="json", exclude_none=True)
    _assert_subset(dumped, fixture["layout"])
    assert validate_layout(dumped) == layout


@pytest.mark.parametrize("fixture", CORPUS["invalid"], ids=lambda f: f["name"])
def test_invalid_fixture_is_rejected(fixture: dict[str, Any]) -> None:
    with pytest.raises(ValidationError):
        validate_layout(fixture["layout"])


def test_defaults_match_the_typescript_schema() -> None:
    layout = validate_layout({"version": 1, "page": {"size": "A4"}})
    assert layout.page.orientation == "portrait"
    assert layout.page.margins_mm.model_dump() == {
        "top": 12,
        "right": 12,
        "bottom": 12,
        "left": 12,
    }
    assert layout.page.bleed_mm == 0
    assert layout.fonts == []
    assert layout.elements == []


def test_duplicate_element_ids_are_reported() -> None:
    element = {
        "id": "dup",
        "type": "shape",
        "rect": {"x_mm": 0, "y_mm": 0, "w_mm": 10, "h_mm": 10},
        "shape": "rect",
    }
    with pytest.raises(ValidationError, match='duplicate element id "dup"'):
        validate_layout(
            {
                "version": 1,
                "page": {"size": "A4"},
                "elements": [element, {**element, "rect": {**element["rect"], "y_mm": 20}}],
            }
        )


def test_explicit_null_is_rejected_like_a_strict_zod_object() -> None:
    with pytest.raises(ValidationError):
        validate_layout({"version": 1, "page": {"size": "A4"}, "name": None})


def test_canonical_schema_identity_and_closed_objects() -> None:
    assert CANONICAL["$id"] == LAYOUT_SCHEMA_ID
    assert CANONICAL["properties"]["version"]["const"] == LAYOUT_SCHEMA_VERSION
    assert CANONICAL["additionalProperties"] is False
    assert Layout.model_config["extra"] == "forbid"
    for entry in _element_schemas().values():
        assert entry["additionalProperties"] is False
    # Recursive conditions are emitted once and referenced, not inlined.
    assert len(CANONICAL["$defs"]) == 1
    assert "#/$defs/" in json.dumps(CANONICAL)


def test_element_types_agree() -> None:
    schemas = _element_schemas()
    union = get_args(get_args(Element)[0])
    model_types = tuple(get_args(model.model_fields["type"].annotation)[0] for model in union)
    assert set(model_types) == set(ELEMENT_TYPES) == set(schemas)


@pytest.mark.parametrize("element_type", ELEMENT_TYPES)
def test_required_fields_agree_per_element(element_type: str) -> None:
    schema = _element_schemas()[element_type]
    union = get_args(get_args(Element)[0])
    model = next(
        entry for entry in union if get_args(entry.model_fields["type"].annotation)[0] == element_type
    )
    required = {name for name, info in model.model_fields.items() if info.is_required()}
    assert required == set(schema["required"])


def test_root_and_page_required_fields_agree() -> None:
    required = {name for name, info in Layout.model_fields.items() if info.is_required()}
    assert required == set(CANONICAL["required"])

    page_schema = CANONICAL["properties"]["page"]
    page_required = {name for name, info in Page.model_fields.items() if info.is_required()}
    assert page_required == set(page_schema["required"])
    assert set(get_args(Page.model_fields["size"].annotation)) == set(
        page_schema["properties"]["size"]["enum"]
    )


def test_enumerations_agree() -> None:
    schemas = _element_schemas()
    assert set(get_args(Page.model_fields["orientation"].annotation)) == set(
        CANONICAL["properties"]["page"]["properties"]["orientation"]["enum"]
    )
    assert schemas["qr"]["properties"]["error_correction"]["enum"] == ["L", "M", "Q", "H"]
    assert schemas["barcode"]["properties"]["symbology"]["enum"] == [
        "code128",
        "code39",
        "ean13",
        "ean8",
    ]
    assert schemas["image"]["properties"]["fit"]["enum"] == ["contain", "cover", "fill"]


def test_constraints_agree_on_geometry() -> None:
    rect = _element_schemas()["text"]["properties"]["rect"]
    assert rect["properties"]["w_mm"]["exclusiveMinimum"] == 0
    assert rect["properties"]["x_mm"]["minimum"] == 0
    with pytest.raises(ValidationError):
        validate_layout(
            {
                "version": 1,
                "page": {"size": "A4"},
                "elements": [
                    {
                        "id": "box",
                        "type": "shape",
                        "rect": {"x_mm": 0, "y_mm": 0, "w_mm": 0, "h_mm": 10},
                        "shape": "rect",
                    }
                ],
            }
        )
