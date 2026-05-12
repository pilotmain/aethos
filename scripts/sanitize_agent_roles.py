#!/usr/bin/env python3
# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2025 AethOS AI

"""
Repair user_agents rows that inherited legal/read-only templates (local dev housekeeping).

Usage (repo root, venv active):
  python scripts/sanitize_agent_roles.py
  python scripts/sanitize_agent_roles.py --dry-run
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

# Repo root on PYTHONPATH when run as script
_ROOT = Path(__file__).resolve().parent.parent
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

LEGAL_MARKERS = [
    "legal advice",
    "legal research",
    "contract review",
    "regulated domain",
    "regulated-domain",
    "read-only",
    "cannot use tools",
    "qualified professional",
    "prompt injection",
    "social engineering",
]

TARGET_NORMALIZED_KEYS = frozenset(
    {
        "boss",
        "executor",
        "researcher_pro",
        "analyst_pro",
        "chief_operator",
        "orchestrator",
    }
)


def needs_sanitize(system_prompt: str) -> bool:
    low = (system_prompt or "").lower()
    return any(m in low for m in LEGAL_MARKERS)


def run(*, dry_run: bool, force: bool) -> int:
    from app.core.config import get_settings
    from app.core.db import SessionLocal, ensure_schema
    from app.services.audit_service import audit
    from app.services.custom_agent_parser import is_operator_runtime_handle
    from app.services.custom_agents import BASE_OPERATOR_TEMPLATE, normalize_agent_key

    get_settings.cache_clear()
    if not force and (get_settings().nexa_workspace_mode or "").strip().lower() != "developer":
        print(
            "Skip: set NEXA_WORKSPACE_MODE=developer on this host, or pass --force (not recommended).",
            file=sys.stderr,
        )
        return 2

    ensure_schema()
    db = SessionLocal()
    try:
        from sqlalchemy import select

        from app.models.user_agent import UserAgent

        rows = db.scalars(select(UserAgent)).all()
        n_ok = 0
        for row in rows:
            nk = normalize_agent_key(row.agent_key)
            if nk not in TARGET_NORMALIZED_KEYS and not is_operator_runtime_handle(row.agent_key):
                continue
            if not needs_sanitize(row.system_prompt or ""):
                continue
            if dry_run:
                print(f"[dry-run] would sanitize user={row.owner_user_id!r} key={row.agent_key!r}")
                n_ok += 1
                continue
            row.system_prompt = BASE_OPERATOR_TEMPLATE.strip()[:50_000]
            db.add(row)
            db.commit()
            audit(
                db,
                event_type="custom_agent.sanitized_template",
                actor="nexa",
                user_id=row.owner_user_id,
                message=f"sanitized template for @{row.agent_key}",
                metadata={"agent_key": row.agent_key, "source": "sanitize_agent_roles"},
            )
            n_ok += 1
        print(f"Done. Updated (or dry-run matched): {n_ok}")
        return 0
    finally:
        db.close()


def main() -> None:
    p = argparse.ArgumentParser(description="Sanitize legal/read-only inherited agent prompts.")
    p.add_argument("--dry-run", action="store_true", help="Print targets only; do not commit.")
    p.add_argument(
        "--force",
        action="store_true",
        help="Run even when NEXA_WORKSPACE_MODE is not developer (unsafe outside local dev).",
    )
    args = p.parse_args()
    raise SystemExit(run(dry_run=args.dry_run, force=args.force))


if __name__ == "__main__":
    main()
