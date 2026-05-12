# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2025 AethOS AI

"""Phase 22 — user skills JSON API."""

from __future__ import annotations

from fastapi.testclient import TestClient

from app.main import app
from app.core.security import get_valid_web_user_id


def test_skills_post_and_list(monkeypatch) -> None:
    uid = f"web_skill_{__import__('uuid').uuid4().hex[:10]}"
    app.dependency_overrides[get_valid_web_user_id] = lambda: uid
    monkeypatch.delenv("NEXA_WEB_API_TOKEN", raising=False)

    c = TestClient(app)
    try:
        p = c.post(
            "/api/v1/skills",
            headers={"X-User-Id": uid},
            json={
                "name": "gmail_send",
                "inputs": ["to", "subject", "body"],
                "provider": "api",
                "pii_policy": "redact",
            },
        )
        assert p.status_code == 200
        assert p.json().get("ok") is True

        g = c.get("/api/v1/skills", headers={"X-User-Id": uid})
        assert g.status_code == 200
        skills = g.json().get("skills") or []
        assert any((s.get("name") == "gmail_send") for s in skills)
    finally:
        app.dependency_overrides.clear()
