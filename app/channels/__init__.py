"""Multi-channel abstraction (Phase 12+) — transport adapters live under ``channels/<vendor>/``."""

from app.channels.base import ChannelMessage, ChannelResponse, NexaChannel

__all__ = ["ChannelMessage", "ChannelResponse", "NexaChannel"]
