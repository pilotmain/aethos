"""Slack channel adapter (canonical import path for Phase 41 channel expansion)."""

from __future__ import annotations

from app.services.channels.router import route_inbound
from app.services.channels.slack_channel import SlackChannel

__all__ = ["SlackChannel", "route_inbound"]
