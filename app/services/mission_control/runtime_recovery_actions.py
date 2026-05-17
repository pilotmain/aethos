# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2025 AethOS AI

"""Safe runtime recovery actions (Phase 4 Step 19)."""

from __future__ import annotations

from typing import Any

from app.services.mission_control.runtime_ownership_lock import (
    record_process_lifecycle_event,
    release_runtime_ownership_if_owner,
    takeover_runtime_ownership,
)


def confirm_takeover(*, yes: bool = False) -> tuple[bool, str]:
    if yes:
        return True, ""
    return False, "Takeover requires confirmation. Re-run with --yes."


def execute_runtime_takeover(*, port: int, yes: bool = False) -> dict[str, Any]:
    ok_confirm, msg = confirm_takeover(yes=yes)
    if not ok_confirm:
        return {"ok": False, "message": msg, "changed": False}
    ok = takeover_runtime_ownership(role="cli", port=port)
    record_process_lifecycle_event("takeover", detail="confirmed cli takeover", service="runtime")
    return {
        "ok": ok,
        "changed": ok,
        "message": "Runtime ownership transferred to this CLI session." if ok else "Takeover failed — another live owner may remain.",
    }


def execute_runtime_release() -> dict[str, Any]:
    from app.services.telegram_polling_lock import release_telegram_polling_lock_if_owner

    release_runtime_ownership_if_owner()
    release_telegram_polling_lock_if_owner()
    record_process_lifecycle_event("release", detail="cli release", service="runtime")
    return {"ok": True, "changed": True, "message": "Released runtime and Telegram locks owned by this process."}
