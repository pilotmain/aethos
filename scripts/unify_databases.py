#!/usr/bin/env python3
# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2025 AethOS AI

"""
Unify API and Telegram bot SQLite files into the canonical location (~/.aethos/data/aethos.db).

Run once after pulling Phase 60 (from repo root with ``app`` importable), or use ``aethos unify-db``.
"""

from __future__ import annotations

import sys
from pathlib import Path


def main() -> int:
    root = Path(__file__).resolve().parent.parent
    sys.path.insert(0, str(root))

    from aethos_cli.db_migration import unify_databases

    repo = root
    stats = unify_databases(repo_root=repo, extra_env_files=[repo / ".env"])
    cp = stats["canonical_path"]
    n = stats["agents_in_canonical"]
    src = stats["source_path"]
    print(f"Canonical database: {cp}")
    print(f"Agents (sub_agents table): {n}")
    if src:
        print(f"Copied from: {src}")
    print("DATABASE_URL for repo .env / ~/.aethos/.env updated when those files exist.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
