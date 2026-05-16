# SPDX-License-Identifier: Apache-2.0

from __future__ import annotations

from app.services.setup.setup_operator_profile_api import build_setup_operator_profile


def test_onboarding_relationship() -> None:
    out = build_setup_operator_profile()
    assert out["setup_operator_profile"]["optional_fields_skippable"] is True
