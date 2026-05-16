# SPDX-License-Identifier: Apache-2.0

from __future__ import annotations

from app.services.mission_control.runtime_payload_profiles import apply_payload_profile


def test_office_profile_smaller() -> None:
    truth = {"office": {"agents": []}, "intelligent_routing": {}, "enterprise_overview": {}}
    office = apply_payload_profile(truth, "office")
    assert office.get("payload_profile") == "office"
    assert "intelligent_routing" not in office
