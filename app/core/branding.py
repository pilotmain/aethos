"""Central user-facing product name and strings (AethOS vs legacy \"Nexa\" copy).

Uses :class:`~app.core.config.Settings` so operators can override via env without code edits.
"""

from __future__ import annotations

import re
from functools import lru_cache

__all__ = [
    "display_product_name",
    "full_product_title",
    "substitute_legacy_product_name",
    "access_restricted_body",
    "dev_execution_restricted_body",
    "ops_execution_restricted_body",
    "guest_projects_hint",
    "blocked_account_body",
]


@lru_cache
def display_product_name() -> str:
    """Short UI name (e.g. ``AethOS``)."""
    from app.core.config import get_settings

    s = get_settings()
    return (s.aethos_brand_name or s.app_name or "AethOS").strip() or "AethOS"


def full_product_title() -> str:
    """One-line title + tagline when needed."""
    from app.core.config import get_settings

    s = get_settings()
    name = display_product_name()
    tag = (s.aethos_brand_tagline or "").strip()
    return f"{name} — {tag}".strip(" —") if tag else name


_NEXA_WORD = re.compile(r"\bNexa\b")


def substitute_legacy_product_name(text: str) -> str:
    """
    Replace standalone word ``Nexa`` with the configured product name.

    Does **not** rewrite ``NEXA_*`` env var prefixes or ``nexa`` inside identifiers.
    """
    if not text:
        return text
    return _NEXA_WORD.sub(display_product_name(), text)


def access_restricted_body() -> str:
    n = display_product_name()
    return (
        "This command is restricted.\n\n"
        f"You can still chat with {n} in plain language — ask what you’re trying to do or describe "
        "the outcome you want.\n"
        "If you need Dev, Ops, or project admin, ask the bot owner to grant access."
    )


def dev_execution_restricted_body() -> str:
    n = display_product_name()
    return f"Development execution is restricted on this {n} instance."


def ops_execution_restricted_body() -> str:
    n = display_product_name()
    return f"Ops execution is restricted on this {n} instance."


def guest_projects_hint() -> str:
    n = display_product_name()
    return (
        "Projects on this instance are not shown publicly. Ask the bot owner for access to Dev or "
        "project details."
    )


def blocked_account_body() -> str:
    n = display_product_name()
    return f"This {n} instance is not available for your account."
