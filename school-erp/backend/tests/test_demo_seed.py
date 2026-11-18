"""P2-SEED: demo academic structure, staff placeholders and the student roster."""

from __future__ import annotations

import importlib.util
import uuid
from pathlib import Path

from core.audit.models import AuditLog
from core.auth.principal import Principal
from core.events.models import DomainEvent
from core.people.models import Person
from modules.academics.models import (
    AcademicYear,
    LevelSubject,
    Section,
    Subject,
    Term,
)
from modules.students.models import StudentEnrollment, StudentGuardian, StudentProfile
from sqlalchemy import func, select

REPO_ROOT = Path(__file__).resolve().parents[3]


def _load_seed_module():
    spec = importlib.util.spec_from_file_location("demo_seed", REPO_ROOT / "scripts" / "seed.py")
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


seed = _load_seed_module()


def _principal() -> Principal:
    return Principal(
        actor_id=str(uuid.uuid4()),
        actor_type="user",
        via="api",
        display_name="Demo Seed",
        email="superadmin@demo.school",
        roles=["super_admin"],
        permissions={"*"},
        scopes={"*": {"all"}},
    )


async def _run_seed(app) -> dict:
    principal = _principal()
    async with app.state.db.session() as session:
        return await seed.seed_demo_data(session, principal)


async def _counts(app) -> dict[str, int]:
    async with app.state.db.session() as session:
        values = {}
        for key, model in (
            ("students", StudentProfile),
            ("enrollments", StudentEnrollment),
            ("guardians", StudentGuardian),
            ("persons", Person),
            ("sections", Section),
            ("audit", AuditLog),
            ("events", DomainEvent),
        ):
            values[key] = int((await session.execute(select(func.count()).select_from(model))).scalar_one())
        return values


async def test_demo_seed_builds_year_sections_students_and_guardians(app) -> None:
    summary = await _run_seed(app)

    assert summary["year_code"] == seed.DEMO_YEAR_CODE
    assert summary["year_status"] == "open"
    assert summary["students"] == 60
    assert summary["sections"] == len(seed.DEMO_SECTION_PLAN) == 19
    assert summary["subjects"] >= 17
    assert summary["level_subjects"] > 0

    async with app.state.db.session() as session:
        year = (
            await session.execute(select(AcademicYear).where(AcademicYear.code == seed.DEMO_YEAR_CODE))
        ).scalar_one()
        assert year.term_system == "semester"
        assert year.status == "open"

        terms = (
            (await session.execute(select(Term).where(Term.year_id == year.id).order_by(Term.number)))
            .scalars()
            .all()
        )
        assert [term.number for term in terms] == [1, 2]
        assert [term.status for term in terms] == ["open", "pending"]

        sections = (await session.execute(select(Section).where(Section.year_id == year.id))).scalars().all()
        assert len(sections) == 19
        assert len({(section.level_id, section.code) for section in sections}) == 19

        students = (
            (
                await session.execute(
                    select(StudentProfile).where(
                        StudentProfile.student_number.like("STU-2026-%"),
                        StudentProfile.deleted_at.is_(None),
                    )
                )
            )
            .scalars()
            .all()
        )
        assert len(students) == 60
        assert {student.status for student in students} == {"active"}

        for student in students:
            person = await session.get(Person, student.person_id)
            assert person is not None
            assert all(
                getattr(person, field)
                for field in (
                    "given_name_en",
                    "father_name_en",
                    "grandfather_name_en",
                    "given_name_am",
                    "father_name_am",
                    "grandfather_name_am",
                )
            )

        enrollments = (
            (await session.execute(select(StudentEnrollment).where(StudentEnrollment.year_id == year.id)))
            .scalars()
            .all()
        )
        assert len(enrollments) == 60
        assert {enrollment.status for enrollment in enrollments} == {"active"}
        assert {enrollment.section_id for enrollment in enrollments} == {section.id for section in sections}

        guardian_links = (await session.execute(select(StudentGuardian))).scalars().all()
        assert len(guardian_links) == 120
        assert all(link.deleted_at is None for link in guardian_links)

        parent_one = (
            await session.execute(select(Person).where(Person.email == "parent1@demo.school"))
        ).scalar_one()
        parent_links = (
            (await session.execute(select(StudentGuardian).where(StudentGuardian.person_id == parent_one.id)))
            .scalars()
            .all()
        )
        assert len(parent_links) == 2
        assert {link.relationship for link in parent_links} == {"father"}
        assert all(link.is_primary for link in parent_links)

        staff_emails = [row[0] for row in seed.DEMO_STAFF]
        staff = (await session.execute(select(Person).where(Person.email.in_(staff_emails)))).scalars().all()
        assert len(staff) == len(seed.DEMO_STAFF)

        subjects = int((await session.execute(select(func.count()).select_from(Subject))).scalar_one())
        assert subjects >= 17
        level_subjects = int(
            (await session.execute(select(func.count()).select_from(LevelSubject))).scalar_one()
        )
        assert level_subjects > 0

        event_types = (await session.execute(select(DomainEvent.event_type))).scalars().all()
        assert event_types.count("student.admitted") == 60
        assert event_types.count("student.enrolled") == 60


async def test_demo_seed_rerun_is_a_noop(app) -> None:
    first = await _run_seed(app)
    before = await _counts(app)

    second = await _run_seed(app)
    after = await _counts(app)

    assert first["students_created"] == 60
    assert second["students_created"] == 0
    assert second["sections_created"] == 0
    assert second["people_created"] == 0
    assert second["staff_created"] == 0
    assert before == after
