"""Vault oversight: chain integrity and suspicious-pattern alerts (P1-12)."""

from __future__ import annotations

from collections import defaultdict
from datetime import UTC, datetime, timedelta

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from controller_api.models import Alert, VaultChainHead, VaultEntry

GRADE_ACTION_FRAGMENTS = ("marks", "grade", "score")


def _entry_ts(entry: dict) -> datetime | None:
    value = entry.get("ts")
    if not value:
        return None
    try:
        parsed = datetime.fromisoformat(str(value).replace("Z", "+00:00"))
    except ValueError:
        return None
    return parsed if parsed.tzinfo else parsed.replace(tzinfo=UTC)


def _is_off_hours(ts: datetime, start: int, end: int) -> bool:
    hour = ts.hour
    if start == end:
        return False
    if start > end:
        return hour >= start or hour < end
    return start <= hour < end


async def scan_school(session: AsyncSession, school_id: str, settings) -> list[Alert]:
    """Return new alerts for one school; does not commit."""
    rows = list(
        (
            await session.execute(
                select(VaultEntry).where(VaultEntry.school_id == school_id).order_by(VaultEntry.seq)
            )
        )
        .scalars()
        .all()
    )
    found: list[Alert] = []

    expected = 1
    for row in rows:
        if row.seq != expected:
            found.append(
                Alert(
                    school_id=school_id,
                    kind="AUDIT_GAP",
                    message=f"Expected seq {expected}, found {row.seq}",
                )
            )
        if not row.chain_ok:
            found.append(
                Alert(
                    school_id=school_id,
                    kind="AUDIT_CHAIN_BREAK",
                    message=f"Chain check failed at seq {row.seq}",
                )
            )
        expected = row.seq + 1

    head = await session.get(VaultChainHead, school_id)
    if head is not None and rows and head.last_seq > rows[-1].seq:
        found.append(
            Alert(
                school_id=school_id,
                kind="AUDIT_GAP",
                message=f"Chain head is seq {head.last_seq} but the newest stored entry is {rows[-1].seq}",
            )
        )

    mass_threshold = int(getattr(settings, "vault_mass_delete_threshold", 10))
    window = timedelta(minutes=int(getattr(settings, "vault_mass_delete_window_minutes", 10)))
    deletes: dict[str, list[datetime]] = defaultdict(list)
    for row in rows:
        action = str(row.entry.get("action") or "")
        if not action.endswith(".delete"):
            continue
        ts = _entry_ts(row.entry)
        if ts is None:
            continue
        deletes[str(row.entry.get("actor_id") or "unknown")].append(ts)
    for actor, stamps in deletes.items():
        stamps.sort()
        for index in range(len(stamps)):
            window_end = stamps[index] + window
            count = sum(1 for stamp in stamps[index:] if stamp <= window_end)
            if count >= mass_threshold:
                found.append(
                    Alert(
                        school_id=school_id,
                        kind="MASS_DELETE",
                        message=(f"{count} deletions by {actor} within {window.seconds // 60} minutes"),
                    )
                )
                break

    start = int(getattr(settings, "vault_off_hours_start", 22))
    end = int(getattr(settings, "vault_off_hours_end", 6))
    off_hours_grade_changes = 0
    for row in rows:
        action = str(row.entry.get("action") or "").lower()
        if not any(fragment in action for fragment in GRADE_ACTION_FRAGMENTS):
            continue
        ts = _entry_ts(row.entry)
        if ts is not None and _is_off_hours(ts, start, end):
            off_hours_grade_changes += 1
    threshold = int(getattr(settings, "vault_off_hours_threshold", 5))
    if off_hours_grade_changes >= threshold:
        found.append(
            Alert(
                school_id=school_id,
                kind="OFF_HOURS_GRADE_CHANGE",
                message=(f"{off_hours_grade_changes} grade changes between {start:02d}:00 and {end:02d}:00"),
            )
        )

    for alert in found:
        session.add(alert)
    await session.flush()
    return found
