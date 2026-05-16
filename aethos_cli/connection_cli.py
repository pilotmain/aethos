# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2025 AethOS AI

"""Mission Control connection commands (Phase 4 Step 4)."""

from __future__ import annotations

import os
from pathlib import Path

from aethos_cli.env_util import upsert_env_file
from aethos_cli.setup_mission_control import seed_mission_control_connection
from aethos_cli.setup_secrets import mask_secret


def _repo_root() -> Path:
    return Path(__file__).resolve().parent.parent


def _api_base() -> str:
    return (
        os.environ.get("NEXA_API_BASE")
        or os.environ.get("API_BASE_URL")
        or "http://127.0.0.1:8010"
    ).rstrip("/")


def cmd_connection_show() -> int:
    try:
        from app.core.setup_creds_file import read_setup_creds_merged_dict

        creds = read_setup_creds_merged_dict()
    except Exception:
        creds = {}
    print("Mission Control connection profile:")
    print(f"  API base:    {creds.get('api_base') or _api_base()}")
    print(f"  User ID:     {creds.get('user_id') or os.environ.get('TEST_X_USER_ID', '(not set)')}")
    print(f"  Bearer:      {mask_secret(creds.get('bearer_token') or os.environ.get('NEXA_WEB_API_TOKEN'))}")
    print(f"  MC URL:      {os.environ.get('AETHOS_MISSION_CONTROL_URL', 'http://localhost:3000')}")
    return 0


def cmd_connect() -> int:
    """Regenerate connection credentials and seed Mission Control."""
    repo = _repo_root()
    env_path = repo / ".env"
    updates = seed_mission_control_connection(repo_root=repo, api_base=_api_base())
    if env_path.is_file():
        upsert_env_file(env_path, updates)
    print("Connection refreshed. Open http://localhost:3000")
    return 0


def cmd_connection_repair() -> int:
    """Repair Mission Control connection mismatch."""
    repo = _repo_root()
    env_path = repo / ".env"
    if not env_path.is_file():
        home_env = Path.home() / ".aethos" / ".env"
        env_path = home_env if home_env.is_file() else env_path
    updates = seed_mission_control_connection(repo_root=repo, api_base=_api_base())
    if env_path.is_file():
        upsert_env_file(env_path, updates)
    try:
        from app.core.setup_creds_file import merge_setup_creds

        merge_setup_creds(
            api_base=updates.get("API_BASE_URL"),
            user_id=updates.get("TEST_X_USER_ID"),
            bearer_token=updates.get("NEXA_WEB_API_TOKEN"),
        )
    except Exception:
        pass
    print("Connection repaired — restart API if auth still fails: aethos restart api")
    return 0
