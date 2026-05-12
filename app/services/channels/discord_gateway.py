# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2025 AethOS AI

"""Backward-compatible import — prefer :mod:`app.services.channels.discord`."""

from app.services.channels.discord import DiscordChannel
from app.services.channels.router import route_inbound

__all__ = ["DiscordChannel", "route_inbound"]
