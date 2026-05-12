# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2025 AethOS AI

"""Telegram commands for universal cloud provider discovery (Phase 52c / 52d)."""

from __future__ import annotations

import re
from pathlib import Path

from telegram import Update
from telegram.ext import ContextTypes

from app.services.cloud.loader import get_builtin_provider_names


def _provider_file_stem(raw: str) -> str:
    s = (raw or "").strip().lower()
    s = re.sub(r"[^a-z0-9_-]+", "_", s).strip("_")
    return s or "provider"


async def cloud_providers_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """List registered providers from :mod:`app.services.cloud.registry` (reloads from disk)."""
    from app.services.cloud.registry import get_provider_registry

    if not update.message:
        return
    reg = get_provider_registry(force_reload=True)
    rows = [f"• {p.display_name} (`{p.name}`)" for p in reg.list_all()]
    body = "\n".join(rows[:120])
    n = len(rows)
    await update.message.reply_text(
        f"Registered cloud providers ({n}). Say e.g. deploy to Kubernetes / Terraform / Render "
        f"from an ops agent (CLI + tokens on the worker).\n\n{body}"[:12000]
    )


async def cloud_add_provider_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Add a custom provider by writing ~/.aethos/cloud_providers.d/<name>.yaml and reloading."""
    if not update.message:
        return

    args = list(context.args or [])
    if len(args) < 3:
        await update.message.reply_text(
            "Usage: `/add_provider <name> <cli_binary> <TOKEN_ENV>`\n"
            "Example: `/add_provider scaleway scw SCW_SECRET_KEY`\n\n"
            "After adding, use e.g. deploy to that provider from an ops agent. "
            "You cannot replace shipped provider ids (see `/cloud_providers`)."
        )
        return

    raw_name, cli_exe, token_env = args[0], args[1], args[2]
    stem = _provider_file_stem(raw_name)
    builtins = get_builtin_provider_names()
    if stem in builtins:
        await update.message.reply_text(
            f"Cannot add `{stem}` — that id is reserved by built-in providers. "
            f"Choose another name or override via `~/.aethos/cloud_providers.yaml`."
        )
        return

    display = raw_name.strip().replace("_", " ").title() if raw_name else stem.title()
    user_dir = Path.home() / ".aethos" / "cloud_providers.d"
    user_dir.mkdir(parents=True, exist_ok=True)
    config_file = user_dir / f"{stem}.yaml"

    lines = [
        "# User-defined cloud provider (AethOS Phase 52d)",
        f"name: {stem}",
        f"display_name: {display}",
        f"cli_package: {cli_exe}",
        f"install_command: Install `{cli_exe}` and ensure it is on PATH.",
        f"token_env_var: {token_env}",
        f"detect_patterns: [{stem}]",
        "capabilities: [deploy, logs, status]",
        "commands:",
        f"  deploy: [{cli_exe}, deploy]",
        f"  logs: [{cli_exe}, logs]",
        f"  status: [{cli_exe}, status]",
        "",
    ]
    config_file.write_text("\n".join(lines), encoding="utf-8")

    from app.services.cloud.registry import get_provider_registry

    get_provider_registry(force_reload=True)

    await update.message.reply_text(
        f"Added cloud provider `{stem}`.\n"
        f"CLI: `{cli_exe}`\n"
        f"Token env: `{token_env}`\n"
        f"Config: `{config_file}`"
    )


async def cloud_remove_provider_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Remove a user drop-in provider file under ~/.aethos/cloud_providers.d/."""
    if not update.message:
        return

    args = list(context.args or [])
    if len(args) < 1:
        await update.message.reply_text("Usage: `/remove_provider <name>`")
        return

    stem = _provider_file_stem(args[0])
    builtins = get_builtin_provider_names()
    if stem in builtins:
        await update.message.reply_text(f"Cannot remove built-in provider `{stem}`.")
        return

    drop = Path.home() / ".aethos" / "cloud_providers.d"
    for candidate in (drop / f"{stem}.yaml", drop / f"{stem}.yml"):
        if candidate.is_file():
            candidate.unlink()
            from app.services.cloud.registry import get_provider_registry

            get_provider_registry(force_reload=True)
            await update.message.reply_text(f"Removed provider drop-in `{stem}` ({candidate.name}).")
            return

    await update.message.reply_text(
        f"No drop-in file for `{stem}` under `{drop}`.\n"
        f"Overrides in `~/.aethos/cloud_providers.yaml` must be edited manually."
    )


__all__ = [
    "cloud_add_provider_cmd",
    "cloud_providers_cmd",
    "cloud_remove_provider_cmd",
]
