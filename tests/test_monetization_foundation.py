"""Monetization foundation — feature flags, license route shape, usage tracker."""

from __future__ import annotations

from pathlib import Path
from unittest.mock import patch

from fastapi.testclient import TestClient


def test_feature_flag_unknown_key_is_open() -> None:
    from app.core.feature_flags import is_enterprise_feature_enabled

    assert is_enterprise_feature_enabled("not_an_enterprise_gate") is True


def test_usage_tracker_roundtrip(tmp_path: Path) -> None:
    from app.services.billing.usage_tracker import UsageTracker

    db = tmp_path / "u.sqlite"
    ut = UsageTracker(db_path=db)
    ut.record_usage("u1", tokens=100, requests=2)
    ut.record_usage("u1", tokens=50, requests=1)
    m = ut.get_monthly_usage("u1")
    assert m["tokens"] >= 150
    assert m["requests"] >= 3


def test_license_status_route() -> None:
    from app.main import app

    c = TestClient(app)
    r = c.get("/api/v1/license/status")
    assert r.status_code == 200
    data = r.json()
    assert data.get("tier") in ("community", "enterprise")
    assert "licensed_feature_ids" in data
