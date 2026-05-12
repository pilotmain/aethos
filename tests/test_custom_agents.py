# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2025 AethOS AI

from __future__ import annotations

import uuid

from sqlalchemy import delete

from app.core.db import SessionLocal, ensure_schema
from app.models.user_agent import UserAgent
from app.services.custom_agent_intent import is_custom_agent_creation_intent, parse_agent_title_lines_from_message
from app.services.custom_agent_intent import (
    is_custom_agent_capability_inquiry,
    is_regulated_professional_misuse_request,
)
from app.services.custom_agents import (
    _is_reserved_key,
    create_custom_agent,
    create_many_custom_agents,
    delete_custom_agent,
    get_custom_agent,
    list_active_custom_agents,
    normalize_agent_key,
    run_custom_user_agent,
    try_custom_agent_capability_guidance,
    try_conversational_create_custom_agents,
    user_has_any_byok,
    validate_dangerous_capability_request,
)
from app.services.mention_control import parse_mention


def test_normalize_key() -> None:
    assert normalize_agent_key("Financial Advisor") == "financial_advisor"
    assert len(normalize_agent_key("a" * 200)) == 64


def test_reserved_blocks_dev() -> None:
    assert _is_reserved_key("dev")
    assert _is_reserved_key("ops")
    assert not _is_reserved_key("my_cfo_helper")


def test_create_and_duplicate_upsert() -> None:
    ensure_schema()
    uid = f"u_cust_test_{uuid.uuid4().hex[:8]}"
    db = SessionLocal()
    try:
        a1 = create_custom_agent(db, uid, "Financial advisor", description="x")
        key = a1.agent_key
        a2 = create_custom_agent(
            db, uid, "Financial advisor updated", description="y", force_agent_key=key
        )
        assert a2.id == a1.id
        assert "y" in (a2.description or "")
    finally:
        db.execute(delete(UserAgent).where(UserAgent.owner_user_id == uid))
        db.commit()
        db.close()


def test_create_many() -> None:
    ensure_schema()
    uid = f"u_m_{uuid.uuid4().hex[:8]}"
    db = SessionLocal()
    try:
        out = create_many_custom_agents(
            db, uid, ["fitness coach", "writing assistant"]
        )
        assert len(out) == 2
        all_k = {x.agent_key for x in out}
        assert "fitness_coach" in all_k or "writing" in str(all_k)
    finally:
        db.execute(delete(UserAgent).where(UserAgent.owner_user_id == uid))
        db.commit()
        db.close()


def test_delete() -> None:
    ensure_schema()
    uid = f"u_d_{uuid.uuid4().hex[:8]}"
    db = SessionLocal()
    try:
        a = create_custom_agent(db, uid, "Travel planner", force_agent_key="travel_planner")
        k = a.agent_key
        assert delete_custom_agent(db, uid, k) is True
        assert get_custom_agent(db, uid, k) is not None
        assert not (get_custom_agent(db, uid, k) and get_custom_agent(db, uid, k).is_active)  # type: ignore[union-attr]
    finally:
        db.execute(delete(UserAgent).where(UserAgent.owner_user_id == uid))
        db.commit()
        db.close()


def test_list_active() -> None:
    ensure_schema()
    uid = f"u_l_{uuid.uuid4().hex[:8]}"
    db = SessionLocal()
    try:
        create_custom_agent(db, uid, "A", force_agent_key="a_one")
        r0 = get_custom_agent(db, uid, "a_one")
        r0.is_active = False
        db.add(r0)
        db.commit()
        create_custom_agent(db, uid, "B", force_agent_key="b_two")
        act = list_active_custom_agents(db, uid)
        assert len([x for x in act if x.agent_key == "b_two"]) == 1
    finally:
        db.execute(delete(UserAgent).where(UserAgent.owner_user_id == uid))
        db.commit()
        db.close()


def test_custom_mention_parse_unknown() -> None:
    m = parse_mention("@x_new_agent hello")
    assert m.is_explicit and m.error


def test_intent_list() -> None:
    t = "Create me five agents:\n\n1. financial advisor\n2. fitness coach"
    assert is_custom_agent_creation_intent(t) is True
    lines = parse_agent_title_lines_from_message(t)
    assert len(lines) == 2
    assert "financial" in lines[0].lower()


def test_danger_message() -> None:
    w = validate_dangerous_capability_request("create an agent with deploy and ssh")
    assert w and "not" in w.lower()


def test_byok_check_no_tg() -> None:
    db = SessionLocal()
    try:
        assert user_has_any_byok(db, "u_not_linked") is False
    finally:
        db.close()


def test_conversational_returns_none() -> None:
    db = SessionLocal()
    try:
        r = try_conversational_create_custom_agents(
            db, f"u_{uuid.uuid4()}", "just say hello"
        )
        assert r is None
    finally:
        db.close()


def test_capability_inquiry_attorney() -> None:
    q = "Can I have my own agent who acts as a senior attorney?"
    assert is_custom_agent_capability_inquiry(q) is True


def test_regulated_misuse_detected() -> None:
    assert is_regulated_professional_misuse_request(
        "Make the attorney agent give final legal advice."
    )


def test_guidance_reply_not_not_yet() -> None:
    ensure_schema()
    uid = f"u_guide_{uuid.uuid4().hex[:8]}"
    db = SessionLocal()
    try:
        r = try_custom_agent_capability_guidance(
            db,
            uid,
            "Can I have my own agent who acts as a senior attorney?",
        )
        assert r is not None
        low = r.lower()
        assert "yes" in low or "supports" in low or "custom" in low
        assert "not yet" not in low
    finally:
        db.close()


def test_guidance_refuses_final_licensed_role() -> None:
    db = SessionLocal()
    try:
        r = try_custom_agent_capability_guidance(
            db,
            "u_x",
            "Make the attorney agent give final legal advice.",
        )
        assert r is not None
        low = r.lower()
        assert "final" in low or "can't" in low or "cannot" in low or "licensed" in low
    finally:
        db.close()


def test_attorney_template_sets_regulated_safety() -> None:
    ensure_schema()
    uid = f"u_reg_{uuid.uuid4().hex[:8]}"
    db = SessionLocal()
    try:
        a = create_custom_agent(db, uid, "Senior attorney assistant")
        assert "regulated" in (a.safety_level or "").lower()
    finally:
        db.execute(delete(UserAgent).where(UserAgent.owner_user_id == uid))
        db.commit()
        db.close()


def test_run_custom_no_body() -> None:
    ensure_schema()
    uid = f"u_r_{uuid.uuid4().hex[:8]}"
    db = SessionLocal()
    try:
        a = create_custom_agent(db, uid, "Z", force_agent_key="z_z")
        t = run_custom_user_agent(db, uid, a, "   ")
        assert "add" in t.lower() or "message" in t.lower()
    finally:
        db.execute(delete(UserAgent).where(UserAgent.owner_user_id == uid))
        db.commit()
        db.close()
