# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2025 AethOS AI

from __future__ import annotations

from app.providers.repair.repair_verification import build_verification_result


def test_verification_result_blocked_flag() -> None:
    suite = {"ok": False, "results": [{"command": "npm run build", "returncode": 1, "cli": {}}], "failed_command": "npm run build"}
    vr = build_verification_result(suite, blocked_redeploy=True)
    assert vr["verified"] is False
    assert vr["blocked_redeploy"] is True
