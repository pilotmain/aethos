# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2025 AethOS AI

"""Multi-channel abstraction (Phase 12+) — transport adapters live under ``channels/<vendor>/``."""

from app.channels.base import ChannelMessage, ChannelResponse, NexaChannel

__all__ = ["ChannelMessage", "ChannelResponse", "NexaChannel"]
