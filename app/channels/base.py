# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2025 AethOS AI

"""Abstract channel interface for Nexa multi-channel support (Phase 12)."""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Any


@dataclass
class ChannelMessage:
    """Normalized inbound message for gateway routing."""

    text: str
    user_id: str
    channel: str = "slack"
    channel_user_id: str | None = None
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass
class ChannelResponse:
    """Normalized outbound reply metadata."""

    text: str
    metadata: dict[str, Any] = field(default_factory=dict)


class NexaChannel(ABC):
    """Abstract interface for messaging transports (Slack, Discord, WhatsApp, …)."""

    name: str = "abstract"

    @property
    @abstractmethod
    def enabled(self) -> bool:  # noqa: D401 - imperative mood OK for abstract stub
        """Return True when this channel should be started."""

    @abstractmethod
    async def start(self) -> None:
        """Start listeners / webhook servers (may block until cancelled)."""

    @abstractmethod
    async def send_message(self, channel_id: str, text: str) -> None:
        """Send plain text to a channel or DM."""

    @abstractmethod
    async def handle_message(self, message: ChannelMessage) -> ChannelResponse:
        """Process a normalized message through Nexa (typically :func:`~app.services.channels.router.route_inbound`)."""


__all__ = ["ChannelMessage", "ChannelResponse", "NexaChannel"]
