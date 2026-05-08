"""
Phase 72 — :func:`primary_complete_messages` ``task_type`` integration tests.

Verifies that:

* When ``task_type`` is omitted, behavior is unchanged (no cost-aware routing
  call, no Anthropic override applied).
* When ``task_type`` is provided **and** cost-aware routing is enabled, the
  router is consulted and an Anthropic override is applied via the existing
  ``clone_with_model`` mechanism.
* An explicit ``anthropic_model_override`` argument always wins over the
  cost-aware decision.
* Routing failures inside the cost-aware helper never propagate (best-effort
  telemetry only).
"""

from __future__ import annotations

import json

import pytest

from app.services.llm.base import LLMProvider, Message, ModelInfo
from app.services.llm.completion import primary_complete_messages
from app.services.llm.providers.anthropic_backend import AnthropicBackend


class _StubAnthropic(AnthropicBackend):  # subclass so isinstance(prov, AnthropicBackend) is True
    """Deterministic Anthropic stand-in. Subclasses :class:`AnthropicBackend` so the
    ``isinstance(prov, AnthropicBackend)`` gate inside ``primary_complete_messages``
    triggers ``clone_with_model`` exactly the way the real backend does."""

    def __init__(self, model: str = "claude-sonnet-4-5") -> None:  # noqa: D401 — fixture init
        # Skip AnthropicBackend.__init__ (which talks to the real SDK) — we only
        # need a duck-typed object that returns text and supports clone_with_model.
        self.model = model
        self.captured: list[Message] = []

    def get_model_info(self) -> ModelInfo:  # type: ignore[override]
        return ModelInfo(
            id=self.model,
            name=self.model,
            provider="anthropic",
            context_length=200_000,
            supports_tools=True,
            supports_streaming=True,
            supports_vision=False,
        )

    def complete_chat(  # type: ignore[override]
        self,
        messages,
        *,
        temperature=0.7,
        max_tokens=1024,
        response_format_json=False,
        tools=None,
    ) -> str:
        self.captured = list(messages)
        return f"[stub:{self.model}]"

    async def complete_chat_streaming(self, *args, **kwargs):  # type: ignore[override]
        yield f"[stub:{self.model}]"

    def clone_with_model(self, model: str) -> "_StubAnthropic":  # type: ignore[override]
        return _StubAnthropic(model=model)


@pytest.fixture()
def stub_anthropic(monkeypatch) -> _StubAnthropic:
    """Replace the registered Anthropic provider with a deterministic stub."""

    stub = _StubAnthropic()

    monkeypatch.setattr(
        "app.services.llm.completion.register_llm_providers_from_settings",
        lambda: None,
    )

    class _Reg:
        def get_provider(self, name: str | None = None):
            if (name or "").lower() == "anthropic":
                return stub
            return None

    monkeypatch.setattr(
        "app.services.llm.completion.get_llm_registry",
        lambda: _Reg(),
    )

    monkeypatch.setattr(
        "app.services.llm.completion.assert_provider_egress_allowed",
        lambda *a, **k: None,
    )

    monkeypatch.setattr(
        "app.services.llm.completion._build_chain",
        lambda: ["anthropic"],
    )

    return stub


# Mark used to satisfy linters about the LLMProvider import.
_ = LLMProvider


class _SettingsBase:
    nexa_llm_temperature = 0.7
    nexa_llm_max_tokens = 1024
    nexa_cost_aware_enabled = True
    nexa_cost_aware_max_per_task_usd = 0.05
    nexa_cost_aware_default_provider = "anthropic"
    nexa_cost_aware_default_model = "claude-sonnet-4-5"
    nexa_cost_aware_cheap_provider = "anthropic"
    nexa_cost_aware_cheap_model = "claude-haiku-4-5"
    nexa_cost_aware_default_model_per_domain = ""
    nexa_cost_aware_fallback_provider = "ollama"


@pytest.fixture()
def cost_settings(monkeypatch) -> _SettingsBase:
    s = _SettingsBase()
    monkeypatch.setattr("app.services.llm.completion.get_settings", lambda: s)
    monkeypatch.setattr(
        "app.services.llm.cost_aware_router.get_settings",
        lambda: s,
    )
    monkeypatch.setattr("app.services.budget.helpers.budget_enabled", lambda: False)
    return s


def test_no_task_type_no_routing(stub_anthropic: _StubAnthropic, cost_settings: _SettingsBase) -> None:
    """Backward compatibility: no ``task_type`` -> default model, no override."""

    out = primary_complete_messages([Message(role="user", content="hi")])
    assert out == "[stub:claude-sonnet-4-5]"


def test_task_type_picks_cheap_tier_for_intent(
    stub_anthropic: _StubAnthropic, cost_settings: _SettingsBase
) -> None:
    """Intent classification is hinted to the cheap tier (Haiku)."""

    out = primary_complete_messages(
        [Message(role="user", content="hi")],
        task_type="intent_classification",
    )
    assert out == f"[stub:{cost_settings.nexa_cost_aware_cheap_model}]"


def test_task_type_picks_default_tier_for_planning(
    stub_anthropic: _StubAnthropic, cost_settings: _SettingsBase
) -> None:
    out = primary_complete_messages(
        [Message(role="user", content="plan something")],
        task_type="planning",
    )
    assert out == f"[stub:{cost_settings.nexa_cost_aware_default_model}]"


def test_domain_override_wins_over_tier_hint(
    stub_anthropic: _StubAnthropic, cost_settings: _SettingsBase
) -> None:
    cost_settings.nexa_cost_aware_default_model_per_domain = json.dumps(
        {"qa": "claude-sonnet-4-5"}  # explicit operator choice
    )
    out = primary_complete_messages(
        [Message(role="user", content="check this code")],
        task_type="qa",
    )
    assert out == "[stub:claude-sonnet-4-5]"


def test_explicit_anthropic_override_beats_cost_aware_decision(
    stub_anthropic: _StubAnthropic, cost_settings: _SettingsBase
) -> None:
    """Caller-provided override always wins so existing call sites are stable."""

    out = primary_complete_messages(
        [Message(role="user", content="hi")],
        task_type="intent_classification",  # would otherwise pick cheap tier
        anthropic_model_override="claude-3-5-sonnet-20241022",
    )
    assert out == "[stub:claude-3-5-sonnet-20241022]"


def test_cost_aware_disabled_means_no_override(
    stub_anthropic: _StubAnthropic, cost_settings: _SettingsBase
) -> None:
    cost_settings.nexa_cost_aware_enabled = False
    out = primary_complete_messages(
        [Message(role="user", content="hi")],
        task_type="intent_classification",
    )
    assert out == "[stub:claude-sonnet-4-5]"


def test_router_failure_does_not_break_call(
    monkeypatch, stub_anthropic: _StubAnthropic, cost_settings: _SettingsBase
) -> None:
    """A bug inside route_for_task must never break the surrounding LLM call."""

    def _boom(*_a, **_k):
        raise RuntimeError("router exploded")

    monkeypatch.setattr(
        "app.services.llm.cost_aware_router.route_for_task", _boom
    )
    out = primary_complete_messages(
        [Message(role="user", content="hi")],
        task_type="planning",
    )
    assert out == "[stub:claude-sonnet-4-5]"
