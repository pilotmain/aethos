# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2025 AethOS AI

"""Shared pytest fixtures."""

from __future__ import annotations

import os
import sys
from pathlib import Path

# Phase 27 — CI/local tests must not require Postgres; matches scripts that set this sidcar flag.
os.environ["NEXA_NEXT_LOCAL_SIDECAR"] = "1"
# Phase 33 — allow .env NEXA_AGENT_TOOLS_ENABLED when NEXA_PRODUCTION_MODE is also true (see Settings._phase33_production_lock).
os.environ["NEXA_PYTEST"] = "1"

_REPO_ROOT = Path(__file__).resolve().parents[1]
_NEXA_EXT_PRO_ROOT = _REPO_ROOT / "nexa-ext-pro"
if _NEXA_EXT_PRO_ROOT.is_dir():
    p = str(_NEXA_EXT_PRO_ROOT)
    if p not in sys.path:
        sys.path.insert(0, p)

import uuid

import pytest
from fastapi.testclient import TestClient

from app.core.db import SessionLocal, ensure_schema
from app.core.security import get_valid_web_user_id
from app.main import app


@pytest.fixture
def db_session():
    ensure_schema()
    session = SessionLocal()
    try:
        yield session
    finally:
        session.close()


@pytest.fixture
def api_client():
    """Authenticated Mission Control API client (``X-User-Id`` + optional bearer)."""
    uid = f"mc_user_{uuid.uuid4().hex[:10]}"
    app.dependency_overrides[get_valid_web_user_id] = lambda: uid
    try:
        yield TestClient(app), uid
    finally:
        app.dependency_overrides.clear()


@pytest.fixture(autouse=True)
def _reset_provider_rate_limits():
    from app.services.providers.rate_limit import reset_rate_limits_for_tests

    reset_rate_limits_for_tests()
    yield


@pytest.fixture
def nexa_runtime_clean(db_session):
    """Clear Nexa Next DB tables, bus, and ephemeral privacy/provider buffers; yields the session."""
    from app.services.artifacts.store import clear_store_for_tests
    from app.services.events.bus import clear_events
    from app.services.mission_control.nexa_next_state import STATE

    clear_store_for_tests(db_session)
    clear_events()
    STATE.setdefault("privacy_events", []).clear()
    STATE.setdefault("provider_events", []).clear()
    STATE.setdefault("integrity_alerts", []).clear()
    STATE.setdefault("integrity_alert_ignored_ids", {}).clear()
    STATE.setdefault("privacy_override_log", []).clear()
    STATE["last_updated"] = None
    yield db_session
