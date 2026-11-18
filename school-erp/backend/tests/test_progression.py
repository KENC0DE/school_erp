"""P2-11: bulk promotion, status changes and audit rollback."""

from __future__ import annotations

from tests.conftest import unique_email
from tests.test_students import (
    _activity,
    _level,
    _person,
    _register,
    _section,
    _student_events,
    _year,
)

BASE = "/api/v1/students"
PROMOTIONS = f"{BASE}/promotions"


async def _promotion_setup(client, headers, *, level_code: str = "g5") -> dict:
    source = await _year(client, headers, "2026-2027")
    target = await _year(client, headers, "2027-2028")
    level = await _level(client, headers, level_code)
    next_level = await _level(client, headers, "g6")
    source_section = await _section(client, headers, source, level, "A")
    target_next_section = await _section(client, headers, target, next_level, "A")
    target_alt_section = await _section(client, headers, target, next_level, "B")
    target_same_section = await _section(client, headers, target, level, "A")
    students = []
    for index, name in enumerate(("Abebe", "Marta", "Yonas"), start=1):
        students.append(
            await _register(
                client,
                headers,
                number=f"P-{level_code}-{index:02d}",
                person=_person(
                    given_name_en=name,
                    father_name_en=f"Family{index}",
                    grandfather_name_en="Tessema",
                    given_name_am=None,
                    father_name_am=None,
                    grandfather_name_am=None,
                    date_of_birth=f"2013-0{index}-01",
                ),
                enrollment={
                    "year_id": source["id"],
                    "level_id": level["id"],
                    "section_id": source_section["id"],
                },
            )
        )
    return {
        "source": source,
        "target": target,
        "level": level,
        "next_level": next_level,
        "source_section": source_section,
        "target_next_section": target_next_section,
        "target_alt_section": target_alt_section,
        "target_same_section": target_same_section,
        "students": students,
    }


async def test_promotion_preview_maps_levels_sections_and_exceptions(
    client, superadmin_headers, seeded
) -> None:
    data = await _promotion_setup(client, superadmin_headers)
    body = {
        "source_year_id": data["source"]["id"],
        "target_year_id": data["target"]["id"],
        "source_level_id": data["level"]["id"],
        "source_section_id": data["source_section"]["id"],
    }

    preview = await client.post(f"{PROMOTIONS}/preview", headers=superadmin_headers, json=body)
    assert preview.status_code == 200, preview.text
    result = preview.json()
    assert result["total"] == 3
    assert result["promote"] == 3
    assert result["blocking"] == 0
    first = result["items"][0]
    assert first["action"] == "promote"
    assert first["target_level_id"] == data["next_level"]["id"]
    assert first["target_section_id"] == data["target_next_section"]["id"]
    assert first["current_section_code"] == "A"

    exceptions = [
        {
            "student_id": data["students"][0]["id"],
            "action": "promote",
            "target_section_id": data["target_alt_section"]["id"],
        },
        {"student_id": data["students"][1]["id"], "action": "repeat"},
        {"student_id": data["students"][2]["id"], "action": "skip"},
    ]
    adjusted = await client.post(
        f"{PROMOTIONS}/preview",
        headers=superadmin_headers,
        json={**body, "exceptions": exceptions},
    )
    assert adjusted.status_code == 200, adjusted.text
    adjusted_body = adjusted.json()
    rows = {row["student_id"]: row for row in adjusted_body["items"]}
    explicit = rows[data["students"][0]["id"]]
    assert explicit["action"] == "promote"
    assert explicit["target_section_id"] == data["target_alt_section"]["id"]
    repeat = rows[data["students"][1]["id"]]
    assert repeat["action"] == "repeat"
    assert repeat["target_level_id"] == data["level"]["id"]
    assert repeat["target_section_id"] == data["target_same_section"]["id"]
    assert rows[data["students"][2]["id"]]["action"] == "skip"
    assert adjusted_body["promote"] == 1
    assert adjusted_body["repeat"] == 1
    assert adjusted_body["skip"] == 1


async def test_bulk_promotion_applies_exceptions_and_is_audited(
    app, client, superadmin_headers, seeded
) -> None:
    data = await _promotion_setup(client, superadmin_headers)
    body = {
        "source_year_id": data["source"]["id"],
        "target_year_id": data["target"]["id"],
        "source_level_id": data["level"]["id"],
        "reason": "End of year 2026/27",
        "exceptions": [
            {"student_id": data["students"][1]["id"], "action": "repeat"},
            {"student_id": data["students"][2]["id"], "action": "skip"},
        ],
    }
    applied = await client.post(f"{PROMOTIONS}/apply", headers=superadmin_headers, json=body)
    assert applied.status_code == 200, applied.text
    result = applied.json()
    assert result["promoted"] == 1
    assert result["repeated"] == 1
    assert result["skipped"] == 1
    assert result["enrolled"] == 2

    promoted = await client.get(f"{BASE}/{data['students'][0]['id']}", headers=superadmin_headers)
    assert promoted.status_code == 200
    promoted_body = promoted.json()
    assert promoted_body["status"] == "promoted"
    assert len(promoted_body["enrollments"]) == 2
    target_enrollment = next(
        item for item in promoted_body["enrollments"] if item["year_id"] == data["target"]["id"]
    )
    assert target_enrollment["level_id"] == data["next_level"]["id"]
    assert target_enrollment["section_id"] == data["target_next_section"]["id"]

    repeating = await client.get(f"{BASE}/{data['students'][1]['id']}", headers=superadmin_headers)
    assert repeating.json()["status"] == "repeating"

    skipped = await client.get(f"{BASE}/{data['students'][2]['id']}", headers=superadmin_headers)
    assert skipped.json()["status"] == "active"
    assert len(skipped.json()["enrollments"]) == 1

    actions = {item["action"] for item in await _activity(client, superadmin_headers)}
    assert {"students.progress.promote", "students.progress.repeat", "students.progress.apply"} <= actions

    events = await _student_events(app)
    promoted_events = events["student.promoted"]
    assert len(promoted_events) == 2
    assert {event["action"] for event in promoted_events} == {"promote", "repeat"}
    assert all(event["source_year_id"] == data["source"]["id"] for event in promoted_events)
    assert all(event["target_year_id"] == data["target"]["id"] for event in promoted_events)
    assert {event["student_id"] for event in promoted_events} == {
        data["students"][0]["id"],
        data["students"][1]["id"],
    }
    target_enrollments = [
        event for event in events["student.enrolled"] if event["year_id"] == data["target"]["id"]
    ]
    assert len(target_enrollments) == 2

    # A second run now sees the target enrollments and skips them instead of
    # creating duplicates.
    again = await client.post(
        f"{PROMOTIONS}/preview",
        headers=superadmin_headers,
        json={
            "source_year_id": data["source"]["id"],
            "target_year_id": data["target"]["id"],
        },
    )
    assert again.status_code == 200, again.text
    again_rows = {row["student_id"]: row for row in again.json()["items"]}
    assert again_rows[data["students"][0]["id"]]["action"] == "skip"
    assert "students.progress.warning.already_enrolled" in again_rows[data["students"][0]["id"]]["warnings"]


async def test_promotion_blocks_an_invalid_target_and_graduates_the_last_level(
    client, superadmin_headers, seeded
) -> None:
    source = await _year(client, superadmin_headers, "2026-2027")
    target = await _year(client, superadmin_headers, "2027-2028")
    g5 = await _level(client, superadmin_headers, "g5")
    g12 = await _level(client, superadmin_headers, "g12")
    g5_section = await _section(client, superadmin_headers, source, g5, "A")
    g12_section = await _section(client, superadmin_headers, source, g12, "A")
    await _section(client, superadmin_headers, target, g12, "A")

    younger = await _register(
        client,
        superadmin_headers,
        number="P-LOW-01",
        enrollment={"year_id": source["id"], "level_id": g5["id"], "section_id": g5_section["id"]},
    )
    senior = await _register(
        client,
        superadmin_headers,
        number="P-TOP-01",
        enrollment={
            "year_id": source["id"],
            "level_id": g12["id"],
            "section_id": g12_section["id"],
        },
    )

    blocked = await client.post(
        f"{PROMOTIONS}/preview",
        headers=superadmin_headers,
        json={
            "source_year_id": source["id"],
            "target_year_id": target["id"],
            "source_level_id": g5["id"],
            "exceptions": [{"student_id": younger["id"], "action": "graduate"}],
        },
    )
    assert blocked.status_code == 200, blocked.text
    row = blocked.json()["items"][0]
    assert row["action"] == "graduate"
    assert row["blocking"] is True
    assert "students.progress.warning.graduate_not_final" in row["warnings"]
    refused = await client.post(
        f"{PROMOTIONS}/apply",
        headers=superadmin_headers,
        json={
            "source_year_id": source["id"],
            "target_year_id": target["id"],
            "source_level_id": g5["id"],
            "exceptions": [{"student_id": younger["id"], "action": "graduate"}],
        },
    )
    assert refused.status_code == 422
    assert refused.json()["error"]["message_key"] == "students.progress.error.blocking"

    final = await client.post(
        f"{PROMOTIONS}/preview",
        headers=superadmin_headers,
        json={
            "source_year_id": source["id"],
            "target_year_id": target["id"],
            "source_level_id": g12["id"],
        },
    )
    assert final.status_code == 200, final.text
    assert final.json()["items"][0]["action"] == "graduate"
    assert final.json()["items"][0]["blocking"] is False

    graduated = await client.post(
        f"{PROMOTIONS}/apply",
        headers=superadmin_headers,
        json={
            "source_year_id": source["id"],
            "target_year_id": target["id"],
            "source_level_id": g12["id"],
            "effective_date": "2027-07-01",
            "reason": "Completed Grade 12",
        },
    )
    assert graduated.status_code == 200, graduated.text
    assert graduated.json()["graduated"] == 1
    detail = await client.get(f"{BASE}/{senior['id']}", headers=superadmin_headers)
    assert detail.json()["status"] == "graduated"
    assert detail.json()["exit_date"] == "2027-07-01"
    assert detail.json()["exit_reason"] == "Completed Grade 12"


async def test_status_changes_validate_transitions_and_are_revertible(
    client, superadmin_headers, limited_headers, seeded
) -> None:
    data = await _promotion_setup(client, superadmin_headers)
    student = data["students"][0]

    missing_reason = await client.post(
        f"{BASE}/{student['id']}/status",
        headers=superadmin_headers,
        json={"action": "withdraw"},
    )
    assert missing_reason.status_code == 422
    assert missing_reason.json()["error"]["message_key"] == "students.progress.error.reason_required"

    denied = await client.post(
        f"{BASE}/{student['id']}/status",
        headers=limited_headers,
        json={"action": "withdraw", "exit_reason": "Family moved"},
    )
    assert denied.status_code == 403

    withdrawn = await client.post(
        f"{BASE}/{student['id']}/status",
        headers=superadmin_headers,
        json={"action": "withdraw", "exit_date": "2027-01-15", "exit_reason": "Family moved"},
    )
    assert withdrawn.status_code == 200, withdrawn.text
    assert withdrawn.json()["student"]["status"] == "withdrawn"
    assert withdrawn.json()["student"]["exit_reason"] == "Family moved"

    invalid = await client.post(
        f"{BASE}/{student['id']}/status",
        headers=superadmin_headers,
        json={"action": "alumni", "exit_reason": "skip a step"},
    )
    assert invalid.status_code == 409
    assert invalid.json()["error"]["message_key"] == "students.progress.error.transition"

    reinstated = await client.post(
        f"{BASE}/{student['id']}/status",
        headers=superadmin_headers,
        json={"action": "reinstate"},
    )
    assert reinstated.status_code == 200, reinstated.text
    assert reinstated.json()["student"]["status"] == "active"
    assert reinstated.json()["student"]["exit_date"] is None

    entries = await _activity(
        client,
        superadmin_headers,
        entity_type="student_progression",
        entity_id=student["id"],
    )
    withdraw_entry = next(item for item in entries if item["action"] == "students.progress.withdraw")
    assert withdraw_entry["revertible"] is True

    reverted = await client.post(
        f"/api/v1/audit/activity/{withdraw_entry['seq']}/revert",
        headers=superadmin_headers,
        json={"reason": "Withdrawal entered by mistake"},
    )
    assert reverted.status_code == 200, reverted.text
    restored = await client.get(f"{BASE}/{student['id']}", headers=superadmin_headers)
    assert restored.json()["status"] == "active"
    assert restored.json()["exit_date"] is None

    entries = await _activity(
        client,
        superadmin_headers,
        entity_type="student_progression",
        entity_id=student["id"],
    )
    revert_entry = next(item for item in entries if item["seq"] == reverted.json()["audit_seq"])
    assert revert_entry["action"] == "student_progression.revert"
    assert revert_entry["reverts_id"] == str(withdraw_entry["seq"])


async def test_reverting_a_promotion_removes_the_created_enrollment(
    client, superadmin_headers, seeded
) -> None:
    data = await _promotion_setup(client, superadmin_headers)
    student = data["students"][0]
    applied = await client.post(
        f"{PROMOTIONS}/apply",
        headers=superadmin_headers,
        json={
            "source_year_id": data["source"]["id"],
            "target_year_id": data["target"]["id"],
            "source_level_id": data["level"]["id"],
            "student_ids": [student["id"]],
            "reason": "Promote one student",
        },
    )
    assert applied.status_code == 200, applied.text

    entries = await _activity(
        client,
        superadmin_headers,
        entity_type="student_progression",
        entity_id=student["id"],
        action="students.progress.promote",
    )
    entry = entries[0]
    assert entry["revertible"] is True
    assert entry["after"]["enrollment_id"]

    reverted = await client.post(
        f"/api/v1/audit/activity/{entry['seq']}/revert",
        headers=superadmin_headers,
        json={"reason": "Wrong section"},
    )
    assert reverted.status_code == 200, reverted.text
    detail = await client.get(f"{BASE}/{student['id']}", headers=superadmin_headers)
    assert detail.json()["status"] == "active"
    assert len(detail.json()["enrollments"]) == 1
    assert detail.json()["enrollments"][0]["year_id"] == data["source"]["id"]


async def test_promotion_requires_a_manage_permission(
    client, superadmin_headers, limited_headers, seeded
) -> None:
    data = await _promotion_setup(client, superadmin_headers)
    body = {
        "source_year_id": data["source"]["id"],
        "target_year_id": data["target"]["id"],
    }
    denied = await client.post(f"{PROMOTIONS}/preview", headers=limited_headers, json=body)
    assert denied.status_code == 403
    allowed = await client.post(f"{PROMOTIONS}/preview", headers=superadmin_headers, json=body)
    assert allowed.status_code == 200
    assert allowed.json()["total"] == len(data["students"])


async def test_single_graduation_alumni_and_transfer_out(client, superadmin_headers, seeded) -> None:
    source = await _year(client, superadmin_headers, "2026-2027")
    g5 = await _level(client, superadmin_headers, "g5")
    g12 = await _level(client, superadmin_headers, "g12")
    g5_section = await _section(client, superadmin_headers, source, g5, "A")
    g12_section = await _section(client, superadmin_headers, source, g12, "A")
    younger = await _register(
        client,
        superadmin_headers,
        number="P-SINGLE-05",
        enrollment={"year_id": source["id"], "level_id": g5["id"], "section_id": g5_section["id"]},
    )
    senior = await _register(
        client,
        superadmin_headers,
        number="P-SINGLE-12",
        enrollment={
            "year_id": source["id"],
            "level_id": g12["id"],
            "section_id": g12_section["id"],
        },
    )

    not_final = await client.post(
        f"{BASE}/{younger['id']}/status",
        headers=superadmin_headers,
        json={"action": "graduate", "exit_reason": "Early exit"},
    )
    assert not_final.status_code == 422
    assert not_final.json()["error"]["message_key"] == "students.progress.error.not_final_level"

    transferred = await client.post(
        f"{BASE}/{younger['id']}/status",
        headers=superadmin_headers,
        json={
            "action": "transfer_out",
            "exit_date": "2027-02-01",
            "exit_reason": "Family relocated to Addis Ababa",
        },
    )
    assert transferred.status_code == 200, transferred.text
    assert transferred.json()["student"]["status"] == "transferred_out"
    assert transferred.json()["student"]["exit_reason"] == "Family relocated to Addis Ababa"

    graduated = await client.post(
        f"{BASE}/{senior['id']}/status",
        headers=superadmin_headers,
        json={"action": "graduate", "exit_date": "2027-07-01", "exit_reason": "Completed Grade 12"},
    )
    assert graduated.status_code == 200, graduated.text
    assert graduated.json()["student"]["status"] == "graduated"

    alumni = await client.post(
        f"{BASE}/{senior['id']}/status",
        headers=superadmin_headers,
        json={"action": "alumni"},
    )
    assert alumni.status_code == 200, alumni.text
    assert alumni.json()["student"]["status"] == "alumni"

    still_not_reversible = await client.post(
        f"{BASE}/{senior['id']}/status",
        headers=superadmin_headers,
        json={"action": "reinstate"},
    )
    assert still_not_reversible.status_code == 409
    assert still_not_reversible.json()["error"]["message_key"] == "students.progress.error.transition"


def test_unique_email_fixture_is_available() -> None:
    assert unique_email("progress").startswith("progress.")
