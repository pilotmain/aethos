# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2025 AethOS AI

"""Enterprise setup doctor and validate (Phase 4 Step 10)."""

from __future__ import annotations

from pathlib import Path

from aethos_cli.setup_health import run_setup_health_checks
from aethos_cli.setup_integrations_detect import detect_integrations
from aethos_cli.ui import print_box, print_info


def cmd_setup_doctor(*, repo_root: Path | None = None) -> int:
    repo = repo_root or Path(__file__).resolve().parent.parent
    print_info("AethOS setup doctor")
    health = run_setup_health_checks(repo_root=repo)
    lines = [f"{'✓' if c.get('ok') else '✗'} {c.get('name')}: {c.get('detail')}" for c in health.get("checks") or []]
    print_box("Health", lines)
    integrations = detect_integrations()
    ilines = [f"{'✓' if v else '○'} {k}" for k, v in (integrations.get("installed") or {}).items()]
    print_box("Integrations", ilines)
    return 0 if health.get("all_critical_ok") else 1


def cmd_setup_validate(*, repo_root: Path | None = None) -> int:
    from app.services.setup.setup_status import build_setup_status

    repo = repo_root or Path(__file__).resolve().parent.parent
    status = build_setup_status(repo_root=repo)
    print_box(
        "Setup validation",
        [f"complete={status.get('complete')}", f"passed={status.get('passed')}/{status.get('total')}"],
    )
    for k, v in (status.get("checks") or {}).items():
        print(f"  {'✓' if v else '✗'} {k}")
    return 0 if status.get("complete") else 1
