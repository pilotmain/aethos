# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2025 AethOS AI

"""Resolve governance organization id from headers and settings."""

from __future__ import annotations

from app.core.config import get_settings


def resolve_organization_id(x_org_id: str | None) -> str | None:
    """
    Effective org id for the current request.

    Priority: ``X-Org-Id`` header → :envvar:`NEXA_DEFAULT_ORGANIZATION_ID`.

    When governance is disabled, returns ``None`` (callers should skip org enforcement).
    """
    if not get_settings().nexa_governance_enabled:
        return None
    if x_org_id and str(x_org_id).strip():
        return str(x_org_id).strip()[:64]
    d = (get_settings().nexa_default_organization_id or "").strip()
    return d[:64] if d else None
