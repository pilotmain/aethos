"""Shared pytest fixtures."""

from __future__ import annotations

import pytest

from app.core.db import SessionLocal, ensure_schema


@pytest.fixture
def db_session():
    ensure_schema()
    session = SessionLocal()
    try:
        yield session
    finally:
        session.close()


@pytest.fixture
def nexa_runtime_clean(db_session):
    """Clear Nexa Next DB tables, bus, and ephemeral privacy/provider buffers; yields the session."""
    from app.services.artifacts.store import clear_store_for_tests
    from app.services.events.bus import clear_events
    from app.services.mission_control.nexa_next_state import STATE

    clear_store_for_tests(db_session)
    clear_events()
    STATE["privacy_events"].clear()
    STATE["provider_events"].clear()
    STATE["last_updated"] = None
    yield db_session
