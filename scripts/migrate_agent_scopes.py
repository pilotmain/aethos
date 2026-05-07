#!/usr/bin/env python3
"""CLI wrapper — optional Phase 61 parent_chat_id normalization (see aethos_cli.migrate_agent_scopes)."""

from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from aethos_cli.migrate_agent_scopes import main

if __name__ == "__main__":
    raise SystemExit(main())
