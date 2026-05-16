# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2025 AethOS AI

from __future__ import annotations

import pytest

from app.core.config import get_settings
from app.privacy.deploy_privacy import augment_deployment_result_privacy


@pytest.fixture
def _fresh():
    get_settings.cache_clear()
    yield
    get_settings.cache_clear()


def test_deploy_result_gets_privacy_block(monkeypatch: pytest.MonkeyPatch, _fresh) -> None:
    monkeypatch.setenv("AETHOS_PRIVACY_MODE", "observe")
    res = {
        "success": True,
        "provider": "vercel",
        "command": "vercel deploy",
        "stdout": "done user@example.com",
        "stderr": "",
        "url": "https://example.com",
    }
    augment_deployment_result_privacy(res)
    assert "privacy" in res
    assert res["privacy"]["scanned"] is True
    assert "email" in res["privacy"].get("pii_categories", [])
