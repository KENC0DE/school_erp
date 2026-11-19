"""P5-02: the document fields registry and its endpoint.

Modules declare fields on their manifests; the endpoint returns only the fields
of modules that pass all three gates. The corpus also guards the declarations
themselves: field keys are unique across the registry and every advertised
format is one the renderer understands.
"""

from __future__ import annotations

import pytest
from core.documents.fields import FIELD_KINDS, DocumentField
from core.documents.registry import FORMAT_OPTIONS, collect_fields
from core.modules.manifest import ModuleManifest

BASE = "/api/v1/documents/fields"
MODULES = "/api/v1/system/modules"


async def _enable(client, headers, key: str = "assessment", enabled: bool = True) -> None:
    response = await client.put(f"{MODULES}/{key}", headers=headers, json={"enabled": enabled})
    assert response.status_code == 200, response.text


def _by_key(body: dict) -> dict[str, dict]:
    return {item["key"]: item for item in body["items"]}


async def test_fields_come_from_enabled_modules(client, superadmin_headers) -> None:
    await _enable(client, superadmin_headers, "assessment")
    response = await client.get(BASE, headers=superadmin_headers)
    assert response.status_code == 200, response.text

    body = response.json()
    assert body["format_options"] == {
        "calendar": ["ec", "gc", "both"],
        "script": ["am", "en"],
        "money": ["etb"],
    }
    fields = _by_key(body)
    assert fields, "the assessment module should offer report-card fields"
    term_total = fields["student.marks.term.total"]
    assert term_total["module"] == "assessment"
    assert term_total["kind"] == "decimal"
    assert term_total["label_key"] == "assessment.field.marks_term_total"
    assert term_total["sample"] == "35.69"
    assert term_total["formats"] == []
    assert fields["student.marks.subjects"]["kind"] == "table"
    assert fields["student.marks.term.pass"]["kind"] == "boolean"
    assert all(item["module"] for item in body["items"])


async def test_disabling_a_module_removes_its_fields(client, superadmin_headers) -> None:
    await _enable(client, superadmin_headers, "assessment")
    before = _by_key((await client.get(BASE, headers=superadmin_headers)).json())
    assert "student.marks.term.total" in before

    await _enable(client, superadmin_headers, "assessment", False)
    after = _by_key((await client.get(BASE, headers=superadmin_headers)).json())
    assert not any(item["module"] == "assessment" for item in after.values())

    await _enable(client, superadmin_headers, "assessment")
    restored = _by_key((await client.get(BASE, headers=superadmin_headers)).json())
    assert "student.marks.term.total" in restored


async def test_listing_fields_needs_the_design_permission(client, limited_headers) -> None:
    denied = await client.get(BASE, headers=limited_headers)
    assert denied.status_code == 403
    assert denied.json()["error"]["code"] == "PERMISSION_DENIED"

    anonymous = await client.get(BASE)
    assert anonymous.status_code == 401


async def test_the_documents_module_gates_its_own_route(client, superadmin_headers) -> None:
    await _enable(client, superadmin_headers, "documents", False)
    blocked = await client.get(BASE, headers=superadmin_headers)
    assert blocked.status_code == 403
    assert blocked.json()["error"]["code"] == "MODULE_DISABLED"

    await _enable(client, superadmin_headers, "documents")
    assert (await client.get(BASE, headers=superadmin_headers)).status_code == 200


def test_manifest_field_keys_are_unique(app) -> None:
    owners: dict[str, str] = {}
    for manifest in app.state.registry.all():
        for document_field in manifest.document_fields:
            assert document_field.key not in owners, (
                f"'{document_field.key}' is declared by both "
                f"'{owners[document_field.key]}' and '{manifest.key}'"
            )
            owners[document_field.key] = manifest.key


def test_declared_fields_are_renderable(app) -> None:
    for manifest in app.state.registry.all():
        for document_field in manifest.document_fields:
            assert document_field.kind in FIELD_KINDS
            assert set(document_field.formats) <= set(FORMAT_OPTIONS)
            assert document_field.label_key
            assert document_field.sample is not None or document_field.kind == "table"


def _manifest(key: str, *fields: DocumentField) -> ModuleManifest:
    return ModuleManifest(key=key, name=key.title(), document_fields=list(fields))


def test_collect_fields_filters_on_availability_and_keeps_declaration_order() -> None:
    alpha = _manifest(
        "alpha",
        DocumentField("alpha.one", "alpha.field.one", sample="one"),
        DocumentField("alpha.two", "alpha.field.two", sample="two"),
    )
    beta = _manifest("beta", DocumentField("beta.one", "beta.field.one", sample="three"))
    registered = collect_fields(
        [alpha, beta],
        {"alpha": {"available": True}, "beta": {"available": False}},
    )
    assert [(item.module, item.field.key) for item in registered] == [
        ("alpha", "alpha.one"),
        ("alpha", "alpha.two"),
    ]
    assert registered[0].to_dict() == {
        "key": "alpha.one",
        "label_key": "alpha.field.one",
        "kind": "text",
        "formats": [],
        "sample": "one",
        "module": "alpha",
    }


def test_collect_fields_rejects_duplicate_keys_across_enabled_modules() -> None:
    alpha = _manifest("alpha", DocumentField("shared.value", "alpha.field.value"))
    beta = _manifest("beta", DocumentField("shared.value", "beta.field.value"))
    with pytest.raises(ValueError, match="declared by both 'alpha' and 'beta'"):
        collect_fields([alpha, beta], {"alpha": {"available": True}, "beta": {"available": True}})


def test_collect_fields_rejects_unknown_formats_and_kinds() -> None:
    bad_format = _manifest(
        "alpha",
        DocumentField("alpha.date", "alpha.field.date", "date", formats=("calendar", "julian")),
    )
    with pytest.raises(ValueError, match="unknown format"):
        collect_fields([bad_format], {"alpha": {"available": True}})

    bad_kind = _manifest("beta", DocumentField("beta.value", "beta.field.value", "money"))
    with pytest.raises(ValueError, match="unknown kind"):
        collect_fields([bad_kind], {"beta": {"available": True}})
