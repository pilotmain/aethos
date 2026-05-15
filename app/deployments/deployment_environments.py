# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2025 AethOS AI

"""Resolve deployment ↔ environment linkage (uses :mod:`app.environments`)."""

from __future__ import annotations

from typing import Any

from app.environments import environment_registry


def resolve_environment_id(st: dict[str, Any], *, explicit: str | None, user_id: str) -> str:
    if explicit and str(explicit).strip():
        eid = str(explicit).strip()
        environment_registry.ensure_environment(st, eid, user_id=user_id)
        return eid
    return environment_registry.default_environment_id_for_user(st, user_id)
