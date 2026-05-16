# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2025 AethOS AI

"""Mission Control auto-connection seeding (Phase 4 Step 4)."""

from __future__ import annotations

import uuid
from pathlib import Path

from app.core.web_api_token import generate_web_api_token

from aethos_cli.setup_secrets import mask_secret, safe_token_confirm_display
from aethos_cli.ui import print_info, print_success


def default_user_id() -> str:
    return f"web_{uuid.uuid4().hex[:16]}"


def seed_mission_control_connection(
    *,
    repo_root: Path,
    api_base: str,
    user_id: str | None = None,
    bearer_token: str | None = None,
) -> dict[str, str]:
    """
    Persist API URL, bearer token, and user ID for Mission Control.

    Writes repo ``.env`` keys and ``web/.env.local`` when the web app exists.
    """
    uid = (user_id or "").strip() or default_user_id()
    token = (bearer_token or "").strip() or generate_web_api_token()
    ab = api_base.rstrip("/")
    mc_url = "http://localhost:3000"

    updates = {
        "API_BASE_URL": ab,
        "NEXA_API_BASE": ab,
        "TEST_X_USER_ID": uid,
        "X_USER_ID": uid,
        "NEXA_WEB_API_TOKEN": token,
        "AETHOS_MISSION_CONTROL_URL": mc_url,
        "AETHOS_CONNECTION_PROFILE": "default",
    }

    web_env = repo_root / "web" / ".env.local"
    if (repo_root / "web" / "package.json").is_file():
        lines = [
            f"NEXT_PUBLIC_AETHOS_API_BASE={ab}",
            f"NEXT_PUBLIC_API_BASE_URL={ab}",
            f"# User id for dev: {uid}",
            f"# Bearer: {mask_secret(token)}",
        ]
        web_env.parent.mkdir(parents=True, exist_ok=True)
        web_env.write_text("\n".join(lines) + "\n", encoding="utf-8")
        print_success(f"Mission Control env seed → {web_env}")

    try:
        from app.core.setup_creds_file import merge_setup_creds

        merge_setup_creds(api_base=ab, user_id=uid, bearer_token=token)
    except Exception:
        pass

    print_info(safe_token_confirm_display(token))
    return updates
