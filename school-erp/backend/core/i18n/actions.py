"""Action-registry hook for "Suggest with AI" (P1-19).

The editor never talks to a model directly: it invokes the registered action,
so permissions, previews and the AI tool list all share one definition. Until
the AI module lands in Phase 9 there is no suggester, and the endpoint reports
a clear not-configured state instead of inventing a translation.
"""

from __future__ import annotations

from collections.abc import Awaitable, Callable

from app.errors import ValidationFailed
from core.actions.registry import ActionContext, action
from core.i18n.editor import suggest_entry
from pydantic import BaseModel, Field

TranslationSuggester = Callable[[str, str, str, str], Awaitable[str]]

_suggester: TranslationSuggester | None = None


class SuggestInput(BaseModel):
    namespace: str = Field(min_length=1, max_length=60)
    key: str = Field(min_length=1, max_length=200)
    locale: str = Field(min_length=2, max_length=8)


def register_translation_suggester(suggester: TranslationSuggester | None) -> None:
    """Wire the provider. Phase 9 registers the real implementation."""
    global _suggester
    _suggester = suggester


def translation_suggester() -> TranslationSuggester | None:
    return _suggester


@action(
    key="i18n.suggest_translation",
    module="core",
    permission="i18n.manage",
    risk="write",
    describe=(
        "Draft a translation for one key. The draft is stored with "
        "status=needs_review and never overwrites a human school override."
    ),
    input=SuggestInput,
)
async def suggest_translation(ctx: ActionContext, payload: dict) -> dict:
    data = SuggestInput.model_validate(payload)
    suggester = translation_suggester()
    if suggester is None:
        raise ValidationFailed(
            "AI is not configured yet",
            message_key="error.ai.not_configured",
        )
    return await suggest_entry(
        ctx.session,
        ctx.principal,
        data.namespace,
        data.key,
        data.locale,
        suggester=suggester,
        via=ctx.via,
    )


__all__ = [
    "SuggestInput",
    "TranslationSuggester",
    "register_translation_suggester",
    "translation_suggester",
]
