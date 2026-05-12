#!/usr/bin/env python3
# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2025 AethOS AI

"""Debug orchestration NL spawn detection (no DB writes unless spawn succeeds)."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

_REPO = Path(__file__).resolve().parents[1]
if str(_REPO) not in sys.path:
    sys.path.insert(0, str(_REPO))


def main() -> int:
    p = argparse.ArgumentParser(description="Print prefers_registry + parsed specs + optional spawn text.")
    p.add_argument("message", nargs="?", default="Create a marketing agent for product launch")
    p.add_argument("--user-id", default="tg_8666826080", help="App user id for spawn attempt")
    p.add_argument("--no-spawn", action="store_true", help="Skip try_spawn (parse only)")
    args = p.parse_args()

    from app.core.config import get_settings
    from app.services.sub_agent_natural_creation import (
        parse_natural_sub_agent_specs,
        prefers_registry_sub_agent,
        try_spawn_natural_sub_agents,
    )

    msg = (args.message or "").strip()
    print("message:", msg)
    print("prefers_registry_sub_agent:", prefers_registry_sub_agent(msg))
    print("parse_natural_sub_agent_specs:", parse_natural_sub_agent_specs(msg))

    if args.no_spawn:
        return 0

    s = get_settings()
    if not bool(getattr(s, "nexa_agent_orchestration_enabled", False)):
        print("NEXA_AGENT_ORCHESTRATION_ENABLED is false — spawn would return off message.")
    from app.core.db import SessionLocal

    db = SessionLocal()
    try:
        out = try_spawn_natural_sub_agents(
            db,
            args.user_id,
            msg,
            parent_chat_id=f"debug:{args.user_id}",
        )
        print("try_spawn_natural_sub_agents:", (out or "")[:2000])
    finally:
        db.close()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
