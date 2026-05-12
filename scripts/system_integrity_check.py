#!/usr/bin/env python3
# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2025 AethOS AI

"""
Phase 17 — aggregate architecture + privacy integrity checks for CI.

Fails fast with CRITICAL SYSTEM INTEGRITY FAILURE on violation.
"""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path


def main() -> int:
    root = Path(__file__).resolve().parents[1]
    if str(root) not in sys.path:
        sys.path.insert(0, str(root))
    errs: list[str] = []

    r = subprocess.run(
        [sys.executable, str(root / "scripts" / "verify_no_direct_providers.py")],
        cwd=str(root),
        capture_output=True,
        text=True,
    )
    if r.returncode != 0:
        errs.append(r.stderr.strip() or r.stdout.strip() or "verify_no_direct_providers failed")

    gw = (root / "app/services/providers/gateway.py").read_text(encoding="utf-8")
    if "FrozenPayloadDict" not in gw:
        errs.append("gateway.py missing FrozenPayloadDict (immutable outbound payload)")
    if "gateway_post_provider_scan" not in gw:
        errs.append("gateway.py missing post-provider scan audit hook")
    if "gateway_pre_firewall" not in gw:
        errs.append("gateway.py missing pre-firewall audit hook")

    imm_path = root / "app/services/privacy_firewall/immutable.py"
    if not imm_path.is_file():
        errs.append("privacy_firewall/immutable.py missing")

    try:
        from app.services.privacy_firewall.immutable import FrozenPayloadDict
    except ImportError as exc:
        errs.append(f"cannot import FrozenPayloadDict: {exc}")
    else:
        frozen = FrozenPayloadDict({"k": 1})
        try:
            frozen["x"] = 2  # type: ignore[index]
            errs.append("FrozenPayloadDict incorrectly allowed mutation")
        except RuntimeError:
            pass

    if errs:
        print(
            "CRITICAL SYSTEM INTEGRITY FAILURE\n\n" + "\n".join(errs),
            file=sys.stderr,
        )
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
