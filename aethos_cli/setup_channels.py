# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2025 AethOS AI

"""Communication channel setup with secret safety (Phase 4 Step 4)."""

from __future__ import annotations

from typing import Any

from aethos_cli.setup_secrets import safe_token_confirm_display
from aethos_cli.ui import get_input, print_info, print_warn


CHANNELS = (
    ("Telegram", "telegram", "TELEGRAM_BOT_TOKEN", "BotFather → /newbot"),
    ("Discord", "discord", "DISCORD_BOT_TOKEN", "Discord Developer Portal"),
    ("Slack", "slack", "SLACK_BOT_TOKEN", "Slack app → OAuth & Permissions"),
    ("Web UI only", "web", None, "Mission Control only — no chat bridge"),
    ("Skip for now", "skip", None, "Configure channels later"),
)


def configure_channel_choice(choice: str, updates: dict[str, str]) -> dict[str, Any]:
    """Configure one channel; never re-display full token."""
    for label, slug, env_key, hint in CHANNELS:
        if slug != choice:
            continue
        if env_key is None:
            return {"channel": slug, "configured": slug != "skip"}
        print_info(f"{label}: {hint}")
        token = get_input(f"{env_key}", hide=True)
        if not token.strip():
            print_warn(f"Skipped {label}.")
            return {"channel": slug, "configured": False}
        if len(token) < 20:
            print_warn("Token looks short — not saved.")
            return {"channel": slug, "configured": False}
        updates[env_key] = token.strip()
        print_info(safe_token_confirm_display(token))
        if slug == "telegram":
            updates["NEXA_TELEGRAM_EMBED_WITH_API"] = "true"
        return {"channel": slug, "configured": True}
    return {"channel": "unknown", "configured": False}
