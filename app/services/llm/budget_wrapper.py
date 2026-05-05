"""
Optional ``LLMProvider`` wrapper that enforces Phase 28 per-member budgets.
"""

from __future__ import annotations

from collections.abc import AsyncIterator

from app.services.budget.hooks import (
    check_budget_before_llm,
    llm_preflight_estimate,
    record_budget_after_llm,
)
from app.services.llm.base import LLMProvider, Message, ModelInfo, Tool


class BudgetAwareLLMProvider(LLMProvider):
    """Delegates to an inner provider; blocks and records token usage for one member."""

    def __init__(
        self,
        inner: LLMProvider,
        member_id: str,
        member_name: str | None = None,
    ) -> None:
        self._inner = inner
        self._member_id = member_id
        self._member_name = member_name
        self.logical_name = getattr(inner, "logical_name", "") or ""

    def complete_chat(
        self,
        messages: list[Message],
        *,
        temperature: float = 0.7,
        max_tokens: int | None = None,
        response_format_json: bool = False,
        tools: list[Tool] | None = None,
    ) -> str:
        est = llm_preflight_estimate(messages, max_tokens)
        ok, err = check_budget_before_llm(self._member_id, est)
        if not ok and err:
            return err
        out = self._inner.complete_chat(
            messages,
            temperature=temperature,
            max_tokens=max_tokens,
            response_format_json=response_format_json,
            tools=tools,
        )
        record_budget_after_llm(
            self._member_id,
            messages,
            out,
            member_name=self._member_name,
        )
        return out

    async def complete_chat_streaming(
        self,
        messages: list[Message],
        *,
        temperature: float = 0.7,
        max_tokens: int | None = None,
        response_format_json: bool = False,
        tools: list[Tool] | None = None,
    ) -> AsyncIterator[str]:
        est = llm_preflight_estimate(messages, max_tokens)
        ok, err = check_budget_before_llm(self._member_id, est)
        if not ok and err:
            yield err
            return

        chunks: list[str] = []
        async for part in self._inner.complete_chat_streaming(
            messages,
            temperature=temperature,
            max_tokens=max_tokens,
            response_format_json=response_format_json,
            tools=tools,
        ):
            chunks.append(part)
            yield part
        record_budget_after_llm(
            self._member_id,
            messages,
            "".join(chunks),
            member_name=self._member_name,
            description="LLM streaming call",
        )

    def get_model_info(self) -> ModelInfo:
        return self._inner.get_model_info()


__all__ = ["BudgetAwareLLMProvider"]
