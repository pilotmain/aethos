# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2025 AethOS AI

"""Conversational continuity across interactive setup steps."""

from __future__ import annotations

from typing import Any

from aethos_cli.ui import print_info


class SetupConversationContext:
    """Remembers operator choices and produces calm continuity lines."""

    def __init__(self) -> None:
        self._choices: dict[str, Any] = {}

    def record(self, key: str, value: Any) -> None:
        self._choices[key] = value

    def get(self, key: str, default: Any = None) -> Any:
        return self._choices.get(key, default)

    def explain_routing(self, *, mode: str, preference: str) -> str:
        from aethos_cli.setup_routing import canonical_routing_label

        label = canonical_routing_label(mode)
        if mode == "hybrid":
            return (
                f"You selected {label} routing earlier. "
                "I'll prioritize local models first and use cloud providers when higher capability is needed."
            )
        if mode == "local_only":
            return (
                f"You selected {label} routing earlier. "
                "AethOS will keep reasoning on your machine unless you change routing later."
            )
        if mode == "cloud_only":
            return (
                f"You selected {label} routing earlier. "
                "Configured cloud providers will handle reasoning when keys are present."
            )
        if preference == "local_first":
            return (
                "Since you chose privacy-first routing, AethOS will avoid cloud fallback unless explicitly approved."
            )
        return f"Routing is set to {label}. I'll keep decisions aligned with that strategy."

    def explain_provider(self, provider: str, *, configured: bool) -> str:
        name = provider.replace("_", " ").title()
        if configured:
            return (
                f"You already configured {name} previously. "
                "You can keep it, replace it, or disable it temporarily in providers."
            )
        return f"{name} is not configured yet — you can add it now or defer to Mission Control."

    def continuity_line(self, topic: str) -> str | None:
        if topic == "routing" and self._choices.get("routing_mode"):
            return self.explain_routing(
                mode=str(self._choices["routing_mode"]),
                preference=str(self._choices.get("routing_preference") or "balanced"),
            )
        return None

    def print_continuity(self, topic: str) -> None:
        line = self.continuity_line(topic)
        if line:
            print_info(line)


_CTX = SetupConversationContext()


def get_setup_conversation() -> SetupConversationContext:
    return _CTX


def reset_setup_conversation() -> None:
    global _CTX
    _CTX = SetupConversationContext()


__all__ = ["SetupConversationContext", "get_setup_conversation", "reset_setup_conversation"]
