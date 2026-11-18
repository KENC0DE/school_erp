"""Configurable tax and pension rule sets.

A rule set is versioned: rules are editable while it is a draft, then frozen
when it is activated. Changing rates later means a new set, so a finalised
payslip always points at the exact rules that produced it.
"""

from __future__ import annotations

import uuid
from typing import Any

from app.errors import Conflict, NotFound, ValidationFailed
from core.api.concurrency import ensure_row_version
from core.audit.service import record
from core.auth.principal import Principal
from core.db.soft_delete import get_including_deleted, mark_deleted, restore, soft_delete
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from modules.payroll.common import (
    MODULE,
    engine_rule,
    live_rule,
    live_rule_set,
    rule_brackets,
    rule_set_rules,
    rule_set_state,
    rule_state,
)
from modules.payroll.engine import PayrollError, validate_rule
from modules.payroll.models import (
    PayrollRule,
    PayrollRuleBracket,
    PayrollRuleSet,
    PayrollRun,
)
from modules.payroll.schemas import (
    BracketInput,
    RuleInput,
    RuleOut,
    RuleSetInput,
    RuleSetList,
    RuleSetOut,
    RuleSetUpdate,
    RuleUpdate,
)
from modules.payroll.views import rule_out, rule_set_out

EDITABLE_STATUSES = {"draft"}


def _assert_editable(row: PayrollRuleSet) -> None:
    if row.status not in EDITABLE_STATUSES:
        raise Conflict(
            "A rule set is frozen once activated; create a new version instead",
            message_key="payroll.error.rule_set_frozen",
            details={"status": row.status},
        )


def _assert_dates(effective_from, effective_to) -> None:  # type: ignore[no-untyped-def]
    if effective_to is not None and effective_to < effective_from:
        raise ValidationFailed(
            "The end date cannot be before the start date",
            message_key="payroll.error.rule_set_dates",
        )


async def _assert_code_free(
    session: AsyncSession,
    code: str,
    *,
    current_id: uuid.UUID | None = None,
) -> None:
    stmt = select(PayrollRuleSet.id).where(
        PayrollRuleSet.code == code,
        PayrollRuleSet.deleted_at.is_(None),
    )
    if current_id is not None:
        stmt = stmt.where(PayrollRuleSet.id != current_id)
    if (await session.execute(stmt)).scalar_one_or_none() is not None:
        raise Conflict(
            "A rule set with that code already exists",
            message_key="payroll.error.rule_set_code_taken",
            details={"code": code},
        )


async def _hydrate(
    session: AsyncSession, row: PayrollRuleSet
) -> list[tuple[PayrollRule, list[PayrollRuleBracket]]]:
    rules = await rule_set_rules(session, row.id)
    return [(rule, await rule_brackets(session, rule.id)) for rule in rules]


async def _assert_key_free(
    session: AsyncSession,
    rule_set_id: uuid.UUID,
    key: str,
    *,
    current_id: uuid.UUID | None = None,
) -> None:
    stmt = select(PayrollRule.id).where(
        PayrollRule.rule_set_id == rule_set_id,
        PayrollRule.key == key,
        PayrollRule.deleted_at.is_(None),
    )
    if current_id is not None:
        stmt = stmt.where(PayrollRule.id != current_id)
    if (await session.execute(stmt)).scalar_one_or_none() is not None:
        raise Conflict(
            "A rule with that key already exists in the set",
            message_key="payroll.error.rule_key_taken",
            details={"key": key},
        )


def _assert_rule_valid(rule: PayrollRule, brackets: list[PayrollRuleBracket]) -> None:
    try:
        validate_rule(
            engine_rule(
                rule,
                brackets,
            )
        )
    except PayrollError as exc:
        raise ValidationFailed(str(exc), message_key="payroll.error.rule_invalid") from exc


async def list_rule_sets(
    session: AsyncSession,
    *,
    include_archived: bool = False,
) -> RuleSetList:
    stmt = select(PayrollRuleSet).where(PayrollRuleSet.deleted_at.is_(None))
    if not include_archived:
        stmt = stmt.where(PayrollRuleSet.status != "archived")
    rows = (
        (await session.execute(stmt.order_by(PayrollRuleSet.effective_from.desc(), PayrollRuleSet.code)))
        .scalars()
        .all()
    )
    items = [rule_set_out(row, await _hydrate(session, row)) for row in rows]
    return RuleSetList(items=items, total=len(items))


async def get_rule_set(session: AsyncSession, rule_set_id: uuid.UUID) -> RuleSetOut:
    row = await live_rule_set(session, rule_set_id)
    return rule_set_out(row, await _hydrate(session, row))


async def create_rule_set(
    session: AsyncSession,
    principal: Principal,
    data: RuleSetInput,
    *,
    via: str = "api",
) -> RuleSetOut:
    await _assert_code_free(session, data.code)
    _assert_dates(data.effective_from, data.effective_to)
    row = PayrollRuleSet(**data.model_dump(), status="draft")
    session.add(row)
    await session.flush()
    await record(
        session,
        action="payroll.rule_sets.create",
        module=MODULE,
        entity_type="payroll_rule_set",
        entity_id=str(row.id),
        after=rule_set_state(row),
        actor=principal,
        via=via,
    )
    await session.commit()
    return rule_set_out(row, [])


async def update_rule_set(
    session: AsyncSession,
    principal: Principal,
    rule_set_id: uuid.UUID,
    data: RuleSetUpdate,
    *,
    via: str = "api",
) -> RuleSetOut:
    row = await live_rule_set(session, rule_set_id)
    before = rule_set_state(row)
    ensure_row_version(row, data.row_version, current_state=before)
    payload = data.model_dump(exclude_unset=True)
    payload.pop("row_version", None)
    effective_from = payload.get("effective_from", row.effective_from)
    effective_to = payload.get("effective_to", row.effective_to)
    _assert_dates(effective_from, effective_to)

    changes: dict[str, Any] = {}
    for key, value in payload.items():
        if getattr(row, key) != value:
            setattr(row, key, value)
            changes[key] = value
    if changes:
        row.row_version = (row.row_version or 0) + 1
    await session.flush()
    if changes:
        await record(
            session,
            action="payroll.rule_sets.update",
            module=MODULE,
            entity_type="payroll_rule_set",
            entity_id=str(row.id),
            before=before,
            after=rule_set_state(row),
            actor=principal,
            via=via,
        )
    await session.commit()
    return rule_set_out(row, await _hydrate(session, row))


async def activate_rule_set(
    session: AsyncSession,
    principal: Principal,
    rule_set_id: uuid.UUID,
    *,
    via: str = "api",
) -> RuleSetOut:
    row = await live_rule_set(session, rule_set_id)
    if row.status == "active":
        return rule_set_out(row, await _hydrate(session, row))
    if row.status != "draft":
        raise Conflict(
            "Only a draft rule set can be activated",
            message_key="payroll.error.rule_set_not_draft",
        )
    rules = await rule_set_rules(session, row.id)
    if not any(rule.is_active for rule in rules):
        raise ValidationFailed(
            "Add at least one active rule before activating the set",
            message_key="payroll.error.rule_set_empty",
        )
    for rule in rules:
        _assert_rule_valid(rule, await rule_brackets(session, rule.id))

    active_rows = (
        (
            await session.execute(
                select(PayrollRuleSet).where(
                    PayrollRuleSet.status == "active",
                    PayrollRuleSet.deleted_at.is_(None),
                    PayrollRuleSet.id != row.id,
                )
            )
        )
        .scalars()
        .all()
    )
    for previous in active_rows:
        before = rule_set_state(previous)
        previous.status = "archived"
        previous.row_version = (previous.row_version or 0) + 1
        await record(
            session,
            action="payroll.rule_sets.archive",
            module=MODULE,
            entity_type="payroll_rule_set",
            entity_id=str(previous.id),
            before=before,
            after=rule_set_state(previous),
            actor=principal,
            via=via,
        )

    before = rule_set_state(row)
    row.status = "active"
    row.row_version = (row.row_version or 0) + 1
    await session.flush()
    await record(
        session,
        action="payroll.rule_sets.activate",
        module=MODULE,
        entity_type="payroll_rule_set",
        entity_id=str(row.id),
        before=before,
        after=rule_set_state(row),
        actor=principal,
        via=via,
    )
    await session.commit()
    return rule_set_out(row, await _hydrate(session, row))


async def archive_rule_set(
    session: AsyncSession,
    principal: Principal,
    rule_set_id: uuid.UUID,
    *,
    reason: str | None = None,
    via: str = "api",
) -> RuleSetOut:
    row = await live_rule_set(session, rule_set_id)
    if row.status != "active":
        raise Conflict(
            "Only an active rule set can be archived",
            message_key="payroll.error.rule_set_not_active",
        )
    before = rule_set_state(row)
    row.status = "archived"
    row.row_version = (row.row_version or 0) + 1
    await session.flush()
    await record(
        session,
        action="payroll.rule_sets.archive",
        module=MODULE,
        entity_type="payroll_rule_set",
        entity_id=str(row.id),
        before=before,
        after=rule_set_state(row),
        actor=principal,
        reason=reason,
        via=via,
    )
    await session.commit()
    return rule_set_out(row, await _hydrate(session, row))


async def delete_rule_set(
    session: AsyncSession,
    principal: Principal,
    rule_set_id: uuid.UUID,
    *,
    reason: str | None = None,
    via: str = "api",
) -> dict[str, Any]:
    row = await live_rule_set(session, rule_set_id)
    if row.status == "active":
        raise Conflict(
            "Archive the rule set before deleting it",
            message_key="payroll.error.rule_set_active_delete",
        )
    used = (
        (
            await session.execute(
                select(PayrollRun.id)
                .where(
                    PayrollRun.rule_set_id == row.id,
                    PayrollRun.deleted_at.is_(None),
                )
                .limit(1)
            )
        )
        .scalars()
        .first()
    )
    if used is not None:
        raise Conflict(
            "This rule set produced a payroll run and cannot be deleted",
            message_key="payroll.error.rule_set_in_use",
        )
    changed = await soft_delete(
        session,
        row,
        action="payroll.rule_sets.delete",
        module=MODULE,
        actor=principal,
        reason=reason,
        via=via,
        entity_type="payroll_rule_set",
    )
    await session.flush()
    await session.commit()
    return {"id": str(row.id), "deleted": bool(changed), "row_version": row.row_version}


async def restore_rule_set(
    session: AsyncSession,
    principal: Principal,
    rule_set_id: uuid.UUID,
    *,
    reason: str | None = None,
    via: str = "api",
) -> RuleSetOut:
    row = await get_including_deleted(session, PayrollRuleSet, rule_set_id)
    if row is None:
        raise NotFound(
            "The payroll rule set does not exist",
            message_key="payroll.error.rule_set_not_found",
        )
    await _assert_code_free(session, row.code, current_id=row.id)
    await restore(
        session,
        row,
        action="payroll.rule_sets.restore",
        module=MODULE,
        actor=principal,
        reason=reason,
        via=via,
        entity_type="payroll_rule_set",
    )
    await session.flush()
    await session.commit()
    return rule_set_out(row, await _hydrate(session, row))


# --------------------------------------------------------------------- rules


async def _replace_brackets(
    session: AsyncSession,
    principal: Principal,
    rule: PayrollRule,
    brackets: list[BracketInput],
) -> list[PayrollRuleBracket]:
    existing = await rule_brackets(session, rule.id)
    for row in existing:
        mark_deleted(row, actor=principal)
    rows: list[PayrollRuleBracket] = []
    for index, bracket in enumerate(brackets):
        row = PayrollRuleBracket(
            rule_id=rule.id,
            lower_santim=bracket.lower_santim,
            upper_santim=bracket.upper_santim,
            rate_basis_points=bracket.rate_basis_points,
            sort_order=index,
        )
        session.add(row)
        rows.append(row)
    await session.flush()
    return rows


async def create_rule(
    session: AsyncSession,
    principal: Principal,
    rule_set_id: uuid.UUID,
    data: RuleInput,
    *,
    via: str = "api",
) -> RuleOut:
    rule_set = await live_rule_set(session, rule_set_id)
    _assert_editable(rule_set)
    await _assert_key_free(session, rule_set_id, data.key)
    payload = data.model_dump()
    brackets = [BracketInput(**item) for item in payload.pop("brackets")]
    rule = PayrollRule(rule_set_id=rule_set_id, **payload)
    session.add(rule)
    await session.flush()
    rows = await _replace_brackets(session, principal, rule, brackets)
    _assert_rule_valid(rule, rows)
    await record(
        session,
        action="payroll.rules.create",
        module=MODULE,
        entity_type="payroll_rule",
        entity_id=str(rule.id),
        after=rule_state(rule, rows),
        actor=principal,
        via=via,
    )
    await session.commit()
    return rule_out(rule, rows)


async def update_rule(
    session: AsyncSession,
    principal: Principal,
    rule_set_id: uuid.UUID,
    rule_id: uuid.UUID,
    data: RuleUpdate,
    *,
    via: str = "api",
) -> RuleOut:
    rule_set = await live_rule_set(session, rule_set_id)
    _assert_editable(rule_set)
    rule = await live_rule(session, rule_set_id, rule_id)
    before_brackets = await rule_brackets(session, rule.id)
    before = rule_state(rule, before_brackets)
    ensure_row_version(rule, data.row_version, current_state=before)
    payload = data.model_dump(exclude_unset=True)
    payload.pop("row_version", None)
    brackets = payload.pop("brackets", None)

    changes: dict[str, Any] = {}
    for key, value in payload.items():
        if getattr(rule, key) != value:
            setattr(rule, key, value)
            changes[key] = value
    rows = before_brackets
    if brackets is not None:
        rows = await _replace_brackets(
            session,
            principal,
            rule,
            [BracketInput(**item) for item in brackets],
        )
        changes["brackets"] = True
    _assert_rule_valid(rule, rows)
    if changes:
        rule.row_version = (rule.row_version or 0) + 1
    await session.flush()
    if changes:
        await record(
            session,
            action="payroll.rules.update",
            module=MODULE,
            entity_type="payroll_rule",
            entity_id=str(rule.id),
            before=before,
            after=rule_state(rule, rows),
            actor=principal,
            via=via,
        )
    await session.commit()
    return rule_out(rule, rows)


async def delete_rule(
    session: AsyncSession,
    principal: Principal,
    rule_set_id: uuid.UUID,
    rule_id: uuid.UUID,
    *,
    reason: str | None = None,
    via: str = "api",
) -> dict[str, Any]:
    rule_set = await live_rule_set(session, rule_set_id)
    _assert_editable(rule_set)
    rule = await live_rule(session, rule_set_id, rule_id)
    brackets = await rule_brackets(session, rule.id)
    for bracket in brackets:
        mark_deleted(bracket, actor=principal)
    changed = await soft_delete(
        session,
        rule,
        action="payroll.rules.delete",
        module=MODULE,
        actor=principal,
        reason=reason,
        via=via,
        entity_type="payroll_rule",
    )
    await session.flush()
    await session.commit()
    return {"id": str(rule.id), "deleted": bool(changed), "row_version": rule.row_version}


async def restore_rule(
    session: AsyncSession,
    principal: Principal,
    rule_set_id: uuid.UUID,
    rule_id: uuid.UUID,
    *,
    reason: str | None = None,
    via: str = "api",
) -> RuleOut:
    rule_set = await live_rule_set(session, rule_set_id)
    _assert_editable(rule_set)
    rule = await get_including_deleted(session, PayrollRule, rule_id)
    if rule is None or rule.rule_set_id != rule_set_id:
        raise NotFound(
            "The payroll rule does not exist",
            message_key="payroll.error.rule_not_found",
        )
    await _assert_key_free(session, rule_set_id, rule.key, current_id=rule.id)
    await restore(
        session,
        rule,
        action="payroll.rules.restore",
        module=MODULE,
        actor=principal,
        reason=reason,
        via=via,
        entity_type="payroll_rule",
    )
    for bracket in (
        (
            await session.execute(
                select(PayrollRuleBracket).where(
                    PayrollRuleBracket.rule_id == rule.id,
                )
            )
        )
        .scalars()
        .all()
    ):
        if bracket.deleted_at is not None:
            await restore(
                session,
                bracket,
                action="payroll.rule_brackets.restore",
                module=MODULE,
                actor=principal,
                via=via,
                entity_type="payroll_rule_bracket",
            )
    await session.flush()
    await session.commit()
    return rule_out(rule, await rule_brackets(session, rule.id))


__all__ = [
    "activate_rule_set",
    "archive_rule_set",
    "create_rule",
    "create_rule_set",
    "delete_rule",
    "delete_rule_set",
    "get_rule_set",
    "list_rule_sets",
    "restore_rule",
    "restore_rule_set",
    "update_rule",
    "update_rule_set",
]
