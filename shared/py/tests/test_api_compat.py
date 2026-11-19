"""P1-26: the /api/v1 breaking-change rules."""

from __future__ import annotations

from typing import Any

from erp_shared.api_compat import compare_schemas, is_v1_path


def document(paths: dict[str, Any] | None = None, schemas: dict[str, Any] | None = None) -> dict:
    return {
        "openapi": "3.1.0",
        "paths": paths or {},
        "components": {"schemas": schemas or {}},
    }


def get(paths: dict[str, Any] | None = None, schemas: dict[str, Any] | None = None) -> dict:
    return document({"/api/v1/notes": {"get": {"responses": {"200": {"description": "ok"}}}}}, schemas)


def kinds(changes) -> list[str]:
    return [change.kind for change in changes]


def test_v1_prefix_matching() -> None:
    assert is_v1_path("/api/v1")
    assert is_v1_path("/api/v1/jobs")
    assert not is_v1_path("/health")
    assert not is_v1_path("/api/v2/jobs")


def test_additive_endpoints_and_parameters_pass() -> None:
    base = get()
    current = get()
    current["paths"]["/api/v1/jobs"] = {"get": {"responses": {"200": {"description": "ok"}}}}
    current["paths"]["/api/v1/notes"]["get"]["parameters"] = [
        {
            "name": "optional",
            "in": "query",
            "required": False,
            "schema": {"type": "string"},
        }
    ]
    assert compare_schemas(current, base) == []


def test_non_v1_paths_are_ignored() -> None:
    base = get()
    current = get()
    base["paths"]["/health"] = {"get": {}}
    current["paths"].pop("/api/v1/notes")
    # Only the removed v1 path is reported.
    assert kinds(compare_schemas(current, base)) == ["endpoint_removed"]


def test_removed_endpoint_is_breaking() -> None:
    changes = compare_schemas(document(), get())
    assert kinds(changes) == ["endpoint_removed"]
    assert "GET /api/v1/notes" in changes[0].location


def test_deprecated_endpoint_needs_two_release_snapshots() -> None:
    base = get()
    base["paths"]["/api/v1/notes"]["get"]["deprecated"] = True
    current = document()

    # Marked deprecated once: still not removable.
    assert kinds(compare_schemas(current, base)) == ["endpoint_removed"]

    previous = get()
    previous["paths"]["/api/v1/notes"]["get"]["deprecated"] = True
    assert compare_schemas(current, base, previous) == []

    # Only the previous snapshot had the deprecation: one release is not enough.
    previous["paths"]["/api/v1/notes"]["get"].pop("deprecated")
    assert kinds(compare_schemas(current, base, previous)) == ["endpoint_removed"]


def test_removed_response_field_is_breaking() -> None:
    base_schemas = {
        "Note": {
            "type": "object",
            "properties": {"id": {"type": "string"}, "body": {"type": "string"}},
            "required": ["id"],
        }
    }
    base = document(
        {
            "/api/v1/notes": {
                "get": {
                    "responses": {
                        "200": {
                            "content": {"application/json": {"schema": {"$ref": "#/components/schemas/Note"}}}
                        }
                    }
                }
            }
        },
        base_schemas,
    )
    current = document(
        {
            "/api/v1/notes": {
                "get": {
                    "responses": {
                        "200": {
                            "content": {"application/json": {"schema": {"$ref": "#/components/schemas/Note"}}}
                        }
                    }
                }
            }
        },
        {
            "Note": {
                "type": "object",
                "properties": {"id": {"type": "string"}},
                "required": ["id"],
            }
        },
    )
    changes = compare_schemas(current, base)
    assert kinds(changes) == ["field_removed"]
    assert changes[0].location.endswith(".body")


def test_deprecated_response_field_can_go_after_two_releases() -> None:
    def build(deprecated: bool) -> dict:
        return document(
            {
                "/api/v1/notes": {
                    "get": {
                        "responses": {
                            "200": {
                                "content": {
                                    "application/json": {"schema": {"$ref": "#/components/schemas/Note"}}
                                }
                            }
                        }
                    }
                }
            },
            {
                "Note": {
                    "type": "object",
                    "properties": {
                        "id": {"type": "string"},
                        "legacy": {"type": "string", "deprecated": deprecated},
                    },
                }
            },
        )

    base = build(True)
    previous = build(True)
    current = document(
        {
            "/api/v1/notes": {
                "get": {
                    "responses": {
                        "200": {
                            "content": {"application/json": {"schema": {"$ref": "#/components/schemas/Note"}}}
                        }
                    }
                }
            }
        },
        {"Note": {"type": "object", "properties": {"id": {"type": "string"}}}},
    )
    assert compare_schemas(current, base, previous) == []


def test_new_required_request_field_is_breaking() -> None:
    def build(properties: dict, required: list[str]) -> dict:
        return document(
            {
                "/api/v1/notes": {
                    "post": {
                        "requestBody": {
                            "required": True,
                            "content": {
                                "application/json": {"schema": {"$ref": "#/components/schemas/NoteCreate"}}
                            },
                        },
                        "responses": {"200": {"description": "ok"}},
                    }
                }
            },
            {
                "NoteCreate": {
                    "type": "object",
                    "properties": properties,
                    "required": required,
                }
            },
        )

    base = build({"body": {"type": "string"}}, ["body"])
    added = build({"body": {"type": "string"}, "email": {"type": "string"}}, ["body", "email"])
    changes = compare_schemas(added, base)
    assert "required_field_added" in kinds(changes)
    assert any(change.location.endswith(".email") for change in changes)

    # Adding an optional field is fine.
    optional = build(
        {"body": {"type": "string"}, "email": {"type": "string"}},
        ["body"],
    )
    assert compare_schemas(optional, base) == []

    # Making an existing optional field required is breaking too.
    now_required = build(
        {"body": {"type": "string"}, "email": {"type": "string"}},
        ["body", "email"],
    )
    assert "field_now_required" in kinds(compare_schemas(now_required, optional))


def test_type_change_and_enum_narrowing_are_breaking() -> None:
    def build(prop: dict) -> dict:
        return document(
            {
                "/api/v1/notes": {
                    "get": {
                        "responses": {
                            "200": {
                                "content": {
                                    "application/json": {"schema": {"$ref": "#/components/schemas/Note"}}
                                }
                            }
                        }
                    }
                }
            },
            {"Note": {"type": "object", "properties": {"value": prop}}},
        )

    assert "type_changed" in kinds(compare_schemas(build({"type": "integer"}), build({"type": "string"})))
    assert "enum_value_removed" in kinds(
        compare_schemas(
            build({"type": "string", "enum": ["a"]}),
            build({"type": "string", "enum": ["a", "b"]}),
        )
    )
    # Adding an enum value is additive.
    assert (
        compare_schemas(
            build({"type": "string", "enum": ["a", "b"]}),
            build({"type": "string", "enum": ["a"]}),
        )
        == []
    )


def test_union_variant_removal_is_breaking() -> None:
    def build(variants: list[dict]) -> dict:
        return document(
            {
                "/api/v1/notes": {
                    "get": {
                        "responses": {
                            "200": {
                                "content": {
                                    "application/json": {
                                        "schema": {
                                            "anyOf": variants,
                                        }
                                    }
                                }
                            }
                        }
                    }
                }
            }
        )

    base = build([{"type": "string"}, {"type": "integer"}])
    current = build([{"type": "string"}, {"type": "boolean"}])
    assert "union_variant_removed" in kinds(compare_schemas(current, base))


def test_parameter_rules() -> None:
    def build(params: list[dict], status: str = "200") -> dict:
        return document(
            {
                "/api/v1/notes": {
                    "get": {
                        "parameters": params,
                        "responses": {status: {"description": "ok"}},
                    }
                }
            }
        )

    optional = [{"name": "q", "in": "query", "required": False, "schema": {"type": "string"}}]
    required = [{"name": "q", "in": "query", "required": True, "schema": {"type": "string"}}]
    assert "parameter_removed" in kinds(compare_schemas(build([]), build(optional)))
    assert "parameter_now_required" in kinds(compare_schemas(build(required), build(optional)))
    assert "required_parameter_added" in kinds(compare_schemas(build(required), build([])))
    assert "type_changed" in kinds(
        compare_schemas(
            build([{"name": "q", "in": "query", "schema": {"type": "integer"}}]),
            build(optional),
        )
    )
    assert "response_removed" in kinds(compare_schemas(build(optional, "201"), build(optional)))


def test_request_body_rules() -> None:
    def build(body: dict | None) -> dict:
        operation: dict[str, Any] = {"responses": {"200": {"description": "ok"}}}
        if body is not None:
            operation["requestBody"] = body
        return document({"/api/v1/notes": {"post": operation}})

    body = {
        "required": True,
        "content": {"application/json": {"schema": {"type": "object"}}},
    }
    assert "request_body_removed" in kinds(compare_schemas(build(None), build(body)))
    assert "required_request_body_added" in kinds(compare_schemas(build(body), build(None)))
    optional_body = {
        "required": False,
        "content": {"application/json": {"schema": {"type": "object"}}},
    }
    assert "request_body_now_required" in kinds(compare_schemas(build(body), build(optional_body)))


def test_narrowed_request_constraints_are_breaking() -> None:
    def build(minimum: int) -> dict:
        return document(
            {
                "/api/v1/notes": {
                    "get": {
                        "parameters": [
                            {
                                "name": "limit",
                                "in": "query",
                                "required": False,
                                "schema": {"type": "integer", "minimum": minimum},
                            }
                        ],
                        "responses": {"200": {"description": "ok"}},
                    }
                }
            }
        )

    changes = compare_schemas(build(5), build(1))
    assert "constraint_narrowed" in kinds(changes)
    # Loosening a request constraint accepts more values.
    assert compare_schemas(build(0), build(1)) == []
