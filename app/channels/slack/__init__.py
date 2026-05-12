# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2025 AethOS AI

"""Slack channel — Events API (existing FastAPI routes) + Socket Mode Bolt bot (Phase 12.1)."""

from app.channels.slack.adapter import SlackSocketNexaChannel
from app.channels.slack.bot import run_slack_socket_bot, run_slack_socket_bot_forever

__all__ = ["SlackSocketNexaChannel", "run_slack_socket_bot", "run_slack_socket_bot_forever"]
