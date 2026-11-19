#!/usr/bin/env python3
"""Phase 4 checkpoint performance probe: score entry and recalculation.

This is a measurement script, not a test. It builds a throwaway SQLite instance,
seeds the demo school, then times the two operations the checkpoint names:

* entering marks for the full 60-student demo section through the real service;
* recalculating a school structure that holds 3,000 students' scores.

Run it on an idle machine:

    uv run --project school-erp/backend python scripts/bench_assessment.py

The numbers it prints belong in ``docs/DECISIONS.md``.
"""

from __future__ import annotations

import asyncio
import importlib.util
import json
import sys
import tempfile
import time
import uuid
from datetime import date
from decimal import Decimal
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
for _path in (REPO_ROOT / "shared" / "py", REPO_ROOT / "school-erp" / "backend"):
    sys.path.insert(0, str(_path))

BENCH_STUDENTS = 3_000


def _load_seed():
    spec = importlib.util.spec_from_file_location("bench_seed", REPO_ROOT / "scripts" / "seed.py")
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


async def _run() -> dict:
    """Benchmark script: quiet the per-statement SQL echo."""
    import logging

    logging.disable(logging.INFO)

    from app.main import create_app
    from app.settings import Settings
    from core.auth.principal import Principal
    from core.bootstrap import bootstrap
    from core.people.models import Person
    from modules.academics.models import AcademicYear, GradeLevel, Section, Subject, Term
    from modules.assessment import common as assessment_common
    from modules.assessment import service as assessment_service
    from modules.assessment.models import Assessment, AssessmentStructure, Score
    from modules.assessment.schemas import AssessmentCreate, ScoreBulkInput, ScoreInput
    from modules.students.models import StudentEnrollment, StudentProfile
    from sqlalchemy import insert, select

    seed = _load_seed()

    with tempfile.TemporaryDirectory(prefix="bench-assessment-") as tmp:
        settings = Settings(
            app_env="test",
            dev_mode=True,
            database_url=f"sqlite+aiosqlite:///{tmp}/bench.db",
            auto_create_schema=False,
            secret_key="bench-secret-key-0123456789abcdef012",
            refresh_secret="bench-refresh-key-0123456789abcdef",
            storage_dir=f"{tmp}/storage",
            public_base_url="http://benchserver",
        )
        app = create_app(settings)
        await app.state.db.create_all()
        await bootstrap(app)

        principal = Principal(
            actor_id=str(uuid.uuid4()),
            actor_type="system",
            via="automation",
            display_name="Assessment benchmark",
            roles=["super_admin"],
            permissions={"*"},
            scopes={"*": {"all"}},
        )

        async with app.state.db.session() as session:
            await seed.seed_demo_data(session, principal)

        async with app.state.db.session() as session:
            year = (
                (await session.execute(select(AcademicYear).order_by(AcademicYear.start_date)))
                .scalars()
                .first()
            )
            section = (
                (
                    await session.execute(
                        select(Section)
                        .join(GradeLevel, GradeLevel.id == Section.level_id)
                        .where(
                            Section.code == seed.DEMO_ASSESSMENT_SECTION,
                            GradeLevel.code == seed.DEMO_ASSESSMENT_LEVEL,
                            Section.year_id == year.id,
                            Section.deleted_at.is_(None),
                        )
                    )
                )
                .scalars()
                .first()
            )
            subject = (
                (
                    await session.execute(
                        select(Subject).where(
                            Subject.code == seed.DEMO_ASSESSMENT_SUBJECT,
                            Subject.deleted_at.is_(None),
                        )
                    )
                )
                .scalars()
                .first()
            )
            structure = (
                (
                    await session.execute(
                        select(AssessmentStructure).where(AssessmentStructure.deleted_at.is_(None))
                    )
                )
                .scalars()
                .first()
            )
            assert year is not None and section is not None and subject is not None
            assert structure is not None
            term = (
                (
                    await session.execute(
                        select(Term)
                        .where(Term.year_id == year.id, Term.deleted_at.is_(None))
                        .order_by(Term.number)
                    )
                )
                .scalars()
                .first()
            )
            assert term is not None
            roster = await assessment_common.enrolled_roster(session, year.id, section.id)

            # The demo roster spreads 60 students across 19 sections. Top this
            # section up to a full class so the entry figure matches the
            # checkpoint's 60-student section.
            fill = 60 - len(roster)
            if fill > 0:
                fill_people = [
                    {
                        "id": uuid.uuid4(),
                        "given_name_en": f"Class {index}",
                        "father_name_en": "Student",
                        "grandfather_name_en": "Demo",
                        "search_name": f"class student {index}",
                    }
                    for index in range(fill)
                ]
                fill_profiles = [
                    {
                        "id": uuid.uuid4(),
                        "person_id": person["id"],
                        "student_number": f"STU-FILL-{index:03d}",
                        "status": "active",
                    }
                    for index, person in enumerate(fill_people)
                ]
                await session.execute(insert(Person), fill_people)
                await session.execute(insert(StudentProfile), fill_profiles)
                await session.execute(
                    insert(StudentEnrollment),
                    [
                        {
                            "id": uuid.uuid4(),
                            "student_id": profile["id"],
                            "year_id": year.id,
                            "level_id": section.level_id,
                            "section_id": section.id,
                            "status": "active",
                        }
                        for profile in fill_profiles
                    ],
                )
                await session.flush()
                roster = await assessment_common.enrolled_roster(session, year.id, section.id)

            # The demo subject's submission is already published and locked, so
            # entering marks there would (correctly) be refused. A fresh subject
            # in the same section gives the write path an open draft to fill.
            bench_subject = Subject(code="bench-subject", name="Benchmark subject")
            session.add(bench_subject)
            await session.flush()

            # 1) A full 60-student section through the real write path.
            created = await assessment_service.create_assessment(
                session,
                principal,
                AssessmentCreate(
                    year_id=year.id,
                    term_id=term.id,
                    section_id=section.id,
                    subject_id=bench_subject.id,
                    component_key="quizzes",
                    title="Benchmark quiz",
                    assessment_date=date(2026, 10, 1),
                    out_of=Decimal(15),
                ),
                via="automation",
            )
            items = [
                ScoreInput(student_id=profile.id, raw_score=Decimal(str(8 + (index % 7))))
                for index, (profile, _person, _enrollment) in enumerate(roster)
            ]
            started = time.perf_counter()
            entered = await assessment_service.upsert_scores(
                session,
                principal,
                uuid.UUID(created.id),
                ScoreBulkInput(items=items),
                via="automation",
            )
            entry_seconds = time.perf_counter() - started

            # 2) A 3,000-student term: insert the students and their scores
            # directly (the write path above is what is being measured), then
            # run the recalculation job body over the whole structure.
            assessments = (
                (
                    await session.execute(
                        select(Assessment).where(
                            Assessment.year_id == year.id,
                            Assessment.section_id == section.id,
                            Assessment.subject_id == subject.id,
                            Assessment.deleted_at.is_(None),
                        )
                    )
                )
                .scalars()
                .all()
            )
            people = [
                {
                    "id": uuid.uuid4(),
                    "given_name_en": f"Bench {index}",
                    "father_name_en": "Student",
                    "grandfather_name_en": "Demo",
                    "search_name": f"bench student {index}",
                }
                for index in range(BENCH_STUDENTS)
            ]
            profiles = [
                {
                    "id": uuid.uuid4(),
                    "person_id": person["id"],
                    "student_number": f"STU-BENCH-{index:05d}",
                    "status": "active",
                }
                for index, person in enumerate(people)
            ]
            await session.execute(insert(Person), people)
            await session.execute(insert(StudentProfile), profiles)
            await session.execute(
                insert(StudentEnrollment),
                [
                    {
                        "id": uuid.uuid4(),
                        "student_id": profile["id"],
                        "year_id": year.id,
                        "level_id": section.level_id,
                        "section_id": section.id,
                        "status": "active",
                    }
                    for profile in profiles
                ],
            )
            score_rows = []
            for profile_index, profile in enumerate(profiles):
                for assessment_index, assessment in enumerate(assessments):
                    raw = min(
                        Decimal(assessment.out_of),
                        Decimal(str(5 + (profile_index + assessment_index) % 10)),
                    )
                    score_rows.append(
                        {
                            "id": uuid.uuid4(),
                            "assessment_id": assessment.id,
                            "student_id": profile["id"],
                            "raw_score": raw,
                            "out_of": assessment.out_of,
                            "status": "present",
                        }
                    )
            await session.execute(insert(Score), score_rows)
            await session.commit()

            started = time.perf_counter()
            recalculated = await assessment_service.recalculate_structure(session, structure.id)
            recalc_seconds = time.perf_counter() - started

        await app.state.db.dispose()

        return {
            "section_students": len(roster),
            "entry_students": len(items),
            "entry_created": entered.created,
            "entry_seconds": round(entry_seconds, 3),
            "recalc_students": BENCH_STUDENTS,
            "recalc_assessments": len(assessments),
            "recalc_scores": recalculated.scores,
            "recalc_changed": recalculated.changed,
            "recalc_seconds": round(recalc_seconds, 3),
        }


def main() -> int:
    result = asyncio.run(_run())
    print(json.dumps(result, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
