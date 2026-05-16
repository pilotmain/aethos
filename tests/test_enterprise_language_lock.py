# SPDX-License-Identifier: Apache-2.0

from __future__ import annotations

from app.services.mission_control.enterprise_language_lock import build_enterprise_language_lock


def test_enterprise_language_lock() -> None:
    out = build_enterprise_language_lock()
    assert out["enterprise_language_lock"]["canonical_terms"]["workers"]
