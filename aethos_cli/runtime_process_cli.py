# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2025 AethOS AI

"""Runtime process supervision CLI (Phase 4 Step 18)."""

from __future__ import annotations

import json
import os


def cmd_runtime_ownership() -> int:
    from app.services.mission_control.runtime_ownership_lock import build_runtime_ownership_status

    print(json.dumps(build_runtime_ownership_status(), indent=2, default=str)[:24000])
    return 0


def cmd_runtime_services() -> int:
    from app.services.mission_control.runtime_service_registry import build_runtime_service_registry

    print(json.dumps(build_runtime_service_registry(), indent=2, default=str)[:24000])
    return 0


def cmd_runtime_takeover() -> int:
    from app.services.mission_control.runtime_ownership_lock import (
        build_runtime_ownership_status,
        record_process_lifecycle_event,
        takeover_runtime_ownership,
    )

    port = int(os.environ.get("AETHOS_SERVE_PORT") or os.environ.get("NEXA_SERVE_PORT") or "8010")
    ok = takeover_runtime_ownership(role="cli", port=port)
    record_process_lifecycle_event("takeover", detail="cli takeover", service="runtime")
    print(json.dumps({"takeover_ok": ok, **build_runtime_ownership_status()}, indent=2, default=str)[:24000])
    return 0 if ok else 1


def cmd_runtime_release() -> int:
    from app.services.mission_control.runtime_ownership_lock import (
        build_runtime_ownership_status,
        record_process_lifecycle_event,
        release_runtime_ownership_if_owner,
    )
    from app.services.telegram_polling_lock import release_telegram_polling_lock_if_owner

    release_runtime_ownership_if_owner()
    release_telegram_polling_lock_if_owner()
    record_process_lifecycle_event("release", detail="cli release", service="runtime")
    print(json.dumps(build_runtime_ownership_status(), indent=2, default=str)[:24000])
    return 0
