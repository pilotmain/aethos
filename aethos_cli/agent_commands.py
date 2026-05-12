# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2025 AethOS AI

"""CLI helpers for orchestration agent maintenance (Phase 61)."""

from __future__ import annotations


def run_migrate_scopes(*, apply: bool = False) -> int:
    """Rewrite bare ``tg_*`` registry scopes to ``web:tg_*:default`` (optional; SQLite only)."""
    from aethos_cli.migrate_agent_scopes import migrate_agent_scopes

    return migrate_agent_scopes(apply=apply)


__all__ = ["run_migrate_scopes"]
