# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2025 AethOS AI

"""Abstract channel — outbound stubs; inbound always delegates to the Nexa gateway."""

from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Any

from sqlalchemy.orm import Session


class Channel(ABC):
    """Minimal channel contract (extend per Slack/Telegram/Web)."""

    name: str = "abstract"

    @abstractmethod
    def send(self, message: str, *, metadata: dict[str, Any] | None = None) -> dict[str, Any]:
        """Deliver outbound text to the channel implementation."""

    @abstractmethod
    def receive(self, payload: dict[str, Any], *, db: Session | None = None) -> dict[str, Any]:
        """Accept inbound payload and route through ``NexaGateway.handle_message``."""
