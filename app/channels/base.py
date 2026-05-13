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
class InboundMessage:
    """
    Provider-native inbound envelope (OpenClaw-style adapter output).

    ``user_id`` is the **platform** identifier (Slack member id, WhatsApp digits, Discord snowflake).
    Hand off to Nexa only after resolving to an app user id (e.g. via Channel Gateway adapters).
    """

    channel: str
    user_id: str
    chat_id: str
    text: str
    raw_payload: dict[str, Any] = field(default_factory=dict)

    def to_channel_message(self, *, app_user_id: str, extra_metadata: dict[str, Any] | None = None) -> ChannelMessage:
        """Build a :class:`ChannelMessage` for :func:`~app.services.channels.router.route_inbound`."""
        meta: dict[str, Any] = {"chat_id": self.chat_id, **(self.raw_payload or {})}
        if extra_metadata:
            meta.update(extra_metadata)
        return ChannelMessage(
            text=self.text,
            user_id=app_user_id,
            channel=self.channel,
            channel_user_id=self.user_id,
            metadata=meta,
        )


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


__all__ = ["ChannelMessage", "ChannelResponse", "InboundMessage", "NexaChannel"]
