"""Telegram commands for universal cloud provider discovery (Phase 52c)."""

from __future__ import annotations

from telegram import Update
from telegram.ext import ContextTypes


async def cloud_providers_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """List registered providers from :mod:`app.services.cloud.registry`."""
    from app.services.cloud.registry import get_provider_registry

    if not update.message:
        return
    reg = get_provider_registry()
    rows = [f"• {p.display_name} (`{p.name}`)" for p in reg.list_all()]
    body = "\n".join(rows[:120])
    n = len(rows)
    await update.message.reply_text(
        f"Registered cloud providers ({n}). Say e.g. deploy to Kubernetes / Terraform / Render "
        f"from an ops agent (CLI + tokens on the worker).\n\n{body}"[:12000]
    )


async def cloud_add_provider_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Placeholder — runtime registration from chat is not implemented yet."""
    if not update.message:
        return
    await update.message.reply_text(
        "Adding providers from Telegram is not enabled yet. "
        "Extend `CloudProviderRegistry.register()` in code, or open a feature request."
    )


__all__ = ["cloud_add_provider_cmd", "cloud_providers_cmd"]
