# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2025 AethOS AI

"""Machine-local JSON used by the setup wizard and Mission Control for first-run auth (dev only)."""

from __future__ import annotations

import json
import os
import tempfile
from pathlib import Path

FILENAME = "aethos_creds.json"


def setup_creds_json_path() -> Path:
    """Path to the setup credentials file (override with ``AETHOS_SETUP_CREDS_FILE``)."""
    override = (os.environ.get("AETHOS_SETUP_CREDS_FILE") or "").strip()
    if override:
        return Path(override)
    return Path(tempfile.gettempdir()) / FILENAME


def read_setup_creds_dict() -> dict[str, str]:
    p = setup_creds_json_path()
    if not p.is_file():
        return {}
    try:
        raw = json.loads(p.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {}
    if not isinstance(raw, dict):
        return {}
    out: dict[str, str] = {}
    for k in ("api_base", "user_id", "bearer_token"):
        v = raw.get(k)
        if isinstance(v, str) and v.strip():
            out[k] = v.strip()
    return out


def merge_setup_creds(
    *,
    api_base: str | None = None,
    user_id: str | None = None,
    bearer_token: str | None = None,
) -> None:
    """Merge non-empty fields into the setup creds file (partial updates allowed)."""
    cur = read_setup_creds_dict()
    if api_base and str(api_base).strip():
        cur["api_base"] = str(api_base).strip().rstrip("/")
    if user_id and str(user_id).strip():
        cur["user_id"] = str(user_id).strip()
    if bearer_token is not None and str(bearer_token).strip():
        cur["bearer_token"] = str(bearer_token).strip()
    if not cur:
        return
    p = setup_creds_json_path()
    p.write_text(json.dumps(cur, indent=2) + "\n", encoding="utf-8")


def write_setup_creds(*, api_base: str, user_id: str, bearer_token: str) -> None:
    """Write non-empty credentials for the Mission Control bootstrap flow."""
    ab = (api_base or "").strip().rstrip("/")
    uid = (user_id or "").strip()
    tok = (bearer_token or "").strip()
    if not ab or not uid or not tok:
        return
    merge_setup_creds(api_base=ab, user_id=uid, bearer_token=tok)
