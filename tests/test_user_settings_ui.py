# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2025 AethOS AI

"""Phase 21 — API contract expected by Mission Control settings UI."""

from __future__ import annotations


def test_user_settings_response_shape(api_client) -> None:
    client, uid = api_client
    r = client.get("/api/v1/user/settings", headers={"X-User-Id": uid})
    assert r.status_code == 200
    j = r.json()
    assert "privacy_mode" in j
    assert "ui_preferences" in j
    assert isinstance(j["ui_preferences"], dict)
    assert "identity" in j
