"""Document Studio settings (ARCH §9.8).

The only policy the school currently owns is whether certificates need a second
pair of eyes before anything is printed. Other document types are unaffected:
a report card or a receipt is operational paperwork, while a certificate is a
claim the school makes about a person.
"""

from __future__ import annotations

from pydantic import BaseModel, Field


class DocumentSettings(BaseModel):
    require_certificate_approval: bool = Field(
        False,
        json_schema_extra={"label_key": "settings.documents.require_certificate_approval"},
        description=(
            "A certificate batch waits for somebody with documents.approve "
            "before any document is numbered or printed"
        ),
    )


__all__ = ["DocumentSettings"]
