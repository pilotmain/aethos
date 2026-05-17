# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2025 AethOS AI

"""Runtime process supervision CLI (Phase 4 Step 18–19)."""

from __future__ import annotations

import json
import os
import sys


def _print_human(lines: list[str]) -> None:
    print("== AethOS runtime supervision ==", file=sys.stderr)
    for ln in lines:
        print(ln)


def cmd_runtime_ownership() -> int:
    from app.services.mission_control.runtime_ownership_lock import (
        build_runtime_ownership_status,
        format_runtime_ownership_summary,
    )

    summary = format_runtime_ownership_summary()
    _print_human(summary.splitlines())
    if os.environ.get("AETHOS_RUNTIME_JSON"):
        print(json.dumps(build_runtime_ownership_status(), indent=2, default=str)[:24000])
    return 0


def cmd_runtime_services() -> int:
    from app.services.mission_control.runtime_service_registry import build_runtime_service_registry
    from app.services.mission_control.telegram_ownership_ux import build_telegram_ownership_status

    reg = build_runtime_service_registry()["runtime_services"]
    tg = build_telegram_ownership_status()["telegram_ownership"]
    lines = [
        f"API processes: {reg.get('api_instance_count')} (reload parents filtered: {reg.get('reloader_parents_filtered', 0)})",
        f"Telegram bots: {reg.get('telegram_instance_count')}",
        f"Mission Control web: {reg.get('web_instance_count')}",
        f"Telegram mode: {tg.get('mode')}",
        tg.get("message") or "",
    ]
    if reg.get("recommended_action"):
        lines.append(f"Next: {reg['recommended_action']}")
    _print_human([ln for ln in lines if ln])
    if os.environ.get("AETHOS_RUNTIME_JSON"):
        print(json.dumps(build_runtime_service_registry(), indent=2, default=str)[:24000])
    return 0


def cmd_runtime_takeover(*, yes: bool = False) -> int:
    from app.services.mission_control.runtime_recovery_actions import execute_runtime_takeover
    from app.services.mission_control.runtime_ownership_lock import format_runtime_ownership_summary

    port = int(os.environ.get("AETHOS_SERVE_PORT") or os.environ.get("NEXA_SERVE_PORT") or "8010")
    result = execute_runtime_takeover(port=port, yes=yes)
    _print_human([result.get("message") or "takeover complete", "", format_runtime_ownership_summary()])
    return 0 if result.get("ok") else 1


def cmd_runtime_release() -> int:
    from app.services.mission_control.runtime_recovery_actions import execute_runtime_release
    from app.services.mission_control.runtime_ownership_lock import format_runtime_ownership_summary

    result = execute_runtime_release()
    _print_human([result.get("message") or "released", "", format_runtime_ownership_summary()])
    return 0
