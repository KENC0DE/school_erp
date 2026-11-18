"""P4-04: assessment tables store exact marks and honour live unique indexes."""

from __future__ import annotations

import uuid
from datetime import UTC, datetime
from decimal import Decimal

import pytest
from core.db.base import JSONType
from modules.assessment.models import (
    MARK_SCALE,
    AssessmentStructure,
    GradeBand,
    GradeScale,
    ResultSnapshot,
    Score,
)
from sqlalchemy import select, text
from sqlalchemy.exc import IntegrityError, StatementError

YEAR = uuid.uuid4()
TERM = uuid.uuid4()
SECTION = uuid.uuid4()
SUBJECT = uuid.uuid4()
STRUCTURE = uuid.uuid4()
COMPONENT = uuid.uuid4()
ASSESSMENT = uuid.uuid4()
STUDENT = uuid.uuid4()


def _structure(**overrides) -> AssessmentStructure:
    values = {
        "id": STRUCTURE,
        "year_id": YEAR,
        "scope_type": "school",
        "scope_key": "school",
        "name": "Lower primary",
        "term_system": "semester",
        "year_mode": "average",
        "precision": 2,
        "rounding": "half_up",
        "intended_total": Decimal("100"),
    }
    values.update(overrides)
    return AssessmentStructure(**values)


def _score(**overrides) -> Score:
    values = {
        "assessment_id": ASSESSMENT,
        "student_id": STUDENT,
        "raw_score": Decimal("8.5"),
        "out_of": Decimal("10"),
        "status": "present",
        "converted": Decimal("8.500000"),
    }
    values.update(overrides)
    return Score(**values)


async def test_mark_columns_round_trip_as_exact_decimals(app) -> None:
    async with app.state.db.session() as session:
        session.add(
            GradeBand(
                scale_id=uuid.uuid4(),
                min_value=Decimal("74.990000"),
                max_value=Decimal("85.123456"),
                label="C+",
                gpa_points=Decimal("2.75"),
            )
        )
        await session.commit()

        band = (await session.execute(select(GradeBand))).scalar_one()
        assert band.min_value == Decimal("74.990000")
        assert band.max_value == Decimal("85.123456")
        assert band.gpa_points == Decimal("2.75")
        assert isinstance(band.min_value, Decimal)

        # Storage is an integer count of micro-units, not a SQL float.
        stored = (
            await session.execute(text("SELECT min_value, typeof(min_value) FROM assessment_grade_bands"))
        ).one()
        assert stored[0] == int(Decimal("74.990000") * MARK_SCALE) == 74_990_000
        assert stored[1] == "integer"


async def test_mark_input_is_rejected_when_it_is_not_a_number(app) -> None:
    async with app.state.db.session() as session:
        session.add(
            GradeBand(
                scale_id=uuid.uuid4(),
                min_value=74.99,  # float: rejected before it can reach SQL
                max_value=Decimal("85"),
                label="B",
            )
        )
        with pytest.raises(StatementError, match="must be Decimal, int or str"):
            await session.flush()


async def test_live_score_index_rejects_a_duplicate_then_allows_replacement(app) -> None:
    async with app.state.db.session() as session:
        session.add(_score())
        await session.commit()

    async with app.state.db.session() as session:
        session.add(_score())
        with pytest.raises(IntegrityError):
            await session.commit()

    # Soft-deleting the live row frees the key without losing its history.
    async with app.state.db.session() as session:
        original = (await session.execute(select(Score))).scalar_one()
        original.deleted_at = datetime.now(UTC)
        await session.commit()

    async with app.state.db.session() as session:
        session.add(_score(raw_score=Decimal("9.25")))
        await session.commit()

        live = (await session.execute(select(Score).where(Score.deleted_at.is_(None)))).scalars().all()
        assert len(live) == 1
        assert live[0].raw_score == Decimal("9.250000")


async def test_live_structure_index_rejects_duplicate_year_scope(app) -> None:
    async with app.state.db.session() as session:
        session.add(_structure())
        await session.commit()

    async with app.state.db.session() as session:
        session.add(_structure(id=uuid.uuid4(), name="Duplicate"))
        with pytest.raises(IntegrityError):
            await session.commit()


async def test_only_one_live_default_grade_scale(app) -> None:
    async with app.state.db.session() as session:
        session.add(GradeScale(name="National", version=1, is_default=True))
        await session.commit()

    async with app.state.db.session() as session:
        session.add(GradeScale(name="Regional", version=1, is_default=True))
        with pytest.raises(IntegrityError):
            await session.commit()


async def test_assessment_defaults_and_json_payload(app) -> None:
    async with app.state.db.session() as session:
        session.add(_structure())
        session.add(
            ResultSnapshot(
                year_id=YEAR,
                term_id=TERM,
                section_id=SECTION,
                kind="term",
                payload={"marks": [{"student": str(STUDENT), "total": "87.50"}]},
            )
        )
        await session.commit()

        snapshot = (await session.execute(select(ResultSnapshot))).scalar_one()
        assert snapshot.payload["marks"][0]["total"] == "87.50"
        await session.refresh(snapshot)
        assert snapshot.published_at is not None

    # ``JSONType`` keeps the same behaviour on SQLite and PostgreSQL.
    assert ResultSnapshot.__table__.c.payload.type is JSONType
