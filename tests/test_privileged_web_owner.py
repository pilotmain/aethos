"""Mission Control owner gate: Telegram owner vs governance / org membership."""

from __future__ import annotations

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker

from app.core.branding import display_product_name
from app.core.config import get_settings
from app.core.db import Base
from app.models.governance import Organization, OrganizationMembership
from app.models.user import User
from app.services.governance.service import ROLE_OWNER
from app.services.user_capabilities import is_privileged_owner_for_web_mutations


@pytest.fixture(autouse=True)
def _clear_settings_cache_for_owner_tests() -> None:
    get_settings.cache_clear()
    display_product_name.cache_clear()
    yield
    get_settings.cache_clear()
    display_product_name.cache_clear()


@pytest.fixture
def mem_db() -> Session:
    engine = create_engine("sqlite:///:memory:", future=True)
    Base.metadata.create_all(bind=engine)
    S = sessionmaker(bind=engine, class_=Session, future=True)
    db = S()
    try:
        yield db
    finally:
        db.close()
        engine.dispose()


def test_privileged_by_governance_role(mem_db: Session) -> None:
    mem_db.add(
        User(
            id="web_only_1",
            name="W",
            timezone="UTC",
            is_new=False,
            governance_role="owner",
        )
    )
    mem_db.commit()
    assert is_privileged_owner_for_web_mutations(mem_db, "web_only_1") is True


def test_privileged_by_org_membership(mem_db: Session) -> None:
    mem_db.add(
        User(
            id="tg_999000001",
            name="T",
            timezone="UTC",
            is_new=False,
            governance_role=None,
        )
    )
    mem_db.add(
        Organization(
            id="org_test",
            name="Org",
            owner_user_id="other",
            enabled=True,
        )
    )
    mem_db.add(
        OrganizationMembership(
            organization_id="org_test",
            user_id="tg_999000001",
            role=ROLE_OWNER,
            enabled=True,
        )
    )
    mem_db.commit()
    assert is_privileged_owner_for_web_mutations(mem_db, "tg_999000001") is True


def test_guest_without_governance(mem_db: Session) -> None:
    mem_db.add(
        User(
            id="tg_888000002",
            name="T",
            timezone="UTC",
            is_new=False,
            governance_role=None,
        )
    )
    mem_db.commit()
    assert is_privileged_owner_for_web_mutations(mem_db, "tg_888000002") is False


def test_privileged_by_aethos_owner_ids_env(mem_db: Session, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("AETHOS_OWNER_IDS", "web_listed_only_1, tg_900")
    assert is_privileged_owner_for_web_mutations(mem_db, "web_listed_only_1") is True
    assert is_privileged_owner_for_web_mutations(mem_db, "tg_900") is True
    assert is_privileged_owner_for_web_mutations(mem_db, "tg_not_listed") is False
