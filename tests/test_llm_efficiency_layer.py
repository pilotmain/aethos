# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2025 AethOS AI

from __future__ import annotations

from sqlalchemy import delete

from app.core.db import SessionLocal, ensure_schema
from app.models.llm_usage_event import LlmUsageEvent
from app.models.response_turn_event import ResponseTurnEvent
from app.services.llm_usage_recorder import (
    build_llm_usage_summary,
    build_usage_summary_for_request,
    count_llm_events_for_request,
    format_usage_subline,
    get_session_usage_summary,
    record_llm_usage,
    record_response_turn,
)


U_PREFIX = "u_llm_eff_test_"


def _clean_user(db, uid: str) -> None:
    db.execute(delete(ResponseTurnEvent).where(ResponseTurnEvent.user_id == uid))
    db.execute(delete(LlmUsageEvent).where(LlmUsageEvent.user_id == uid))
    db.commit()


def test_no_llm_no_request_id() -> None:
    ensure_schema()
    db = SessionLocal()
    try:
        s = build_usage_summary_for_request(db, "")
        assert s["used_llm"] is False
        assert s["total_tokens"] == 0
        assert s.get("provider") is None
    finally:
        db.close()


def test_no_llm_request_but_no_events() -> None:
    ensure_schema()
    db = SessionLocal()
    try:
        s = build_usage_summary_for_request(db, "req-no-llm-1")
        assert s["used_llm"] is False
        sub = format_usage_subline(s)
        assert "No LLM call" in sub
    finally:
        db.close()


def test_llm_call_aggregates_tokens() -> None:
    ensure_schema()
    uid = f"{U_PREFIX}t1"
    db = SessionLocal()
    try:
        _clean_user(db, uid)
        record_llm_usage(
            db,
            user_id=uid,
            source="test",
            request_id="req-llm-1",
            provider="openai",
            model="gpt-4o-mini",
            action_type="chat_response",
            input_tokens=100,
            output_tokens=20,
            used_user_key=False,
        )
        s = build_usage_summary_for_request(db, "req-llm-1")
        assert s["used_llm"] is True
        assert s["input_tokens"] == 100
        assert s["output_tokens"] == 20
        assert s["total_tokens"] == 120
        assert s["used_user_key"] is False
        sub = format_usage_subline(s)
        assert "k" in sub or "120" in sub or "≈" in sub
        assert "system key" in sub
        assert "gpt-4o-mini" in sub
    finally:
        _clean_user(db, uid)
        db.close()


def test_byok_in_summary_and_subline() -> None:
    ensure_schema()
    uid = f"{U_PREFIX}byok"
    db = SessionLocal()
    try:
        _clean_user(db, uid)
        record_llm_usage(
            db,
            user_id=uid,
            source="test",
            request_id="req-byok",
            provider="anthropic",
            model="claude-3-5-sonnet-20241022",
            action_type="chat_response",
            input_tokens=500,
            output_tokens=500,
            used_user_key=True,
        )
        s = build_usage_summary_for_request(db, "req-byok")
        assert s["used_llm"] is True
        assert s["used_user_key"] is True
        sub = format_usage_subline(s)
        assert "user key" in sub
        assert "BYOK" not in sub  # short form per product copy
        assert "claude-3-5-sonnet" in sub
    finally:
        _clean_user(db, uid)
        db.close()


def test_count_llm_events_for_request() -> None:
    ensure_schema()
    uid = f"{U_PREFIX}cnt"
    db = SessionLocal()
    try:
        _clean_user(db, uid)
        for i in range(2):
            record_llm_usage(
                db,
                user_id=uid,
                source="test",
                request_id="req-multi",
                provider="openai",
                model="gpt-4o-mini",
                action_type="chat_response",
                input_tokens=10,
                output_tokens=10,
                used_user_key=False,
            )
        n = count_llm_events_for_request(db, "req-multi")
        assert n == 2
    finally:
        _clean_user(db, uid)
        db.close()


def test_get_session_usage_summary_aggregation() -> None:
    ensure_schema()
    uid = f"{U_PREFIX}sess"
    db = SessionLocal()
    try:
        _clean_user(db, uid)
        record_llm_usage(
            db,
            user_id=uid,
            source="test",
            session_id="eff_sess_1",
            request_id="r1",
            provider="openai",
            model="gpt-4o-mini",
            input_tokens=1000,
            output_tokens=0,
            used_user_key=False,
        )
        record_llm_usage(
            db,
            user_id=uid,
            source="test",
            session_id="eff_sess_1",
            request_id="r2",
            provider="openai",
            model="gpt-4o-mini",
            input_tokens=500,
            output_tokens=500,
            used_user_key=False,
        )
        o = get_session_usage_summary(db, "eff_sess_1", uid, is_owner=False)
        assert o["call_count"] == 2
        assert o["total_tokens"] == 2000
        assert o["session_id"] == "eff_sess_1"
    finally:
        _clean_user(db, uid)
        db.close()


def test_efficiency_ratio_in_summary() -> None:
    ensure_schema()
    uid = f"{U_PREFIX}eff"
    db = SessionLocal()
    try:
        _clean_user(db, uid)
        record_response_turn(
            db, user_id=uid, session_id="default", request_id="a1", had_llm=False
        )
        record_response_turn(
            db, user_id=uid, session_id="default", request_id="a2", had_llm=False
        )
        record_response_turn(
            db, user_id=uid, session_id="default", request_id="a3", had_llm=True
        )
        summ = build_llm_usage_summary("all", db, uid, is_owner=False)
        eff = summ.get("efficiency") or {}
        assert eff.get("total_actions") == 3
        assert eff.get("llm_calls") == 1
        assert eff.get("non_llm_actions") == 2
        ratio = eff.get("efficiency_ratio")
        assert ratio is not None
        assert abs(float(ratio) - (2.0 / 3.0)) < 0.01
    finally:
        _clean_user(db, uid)
        db.close()


def test_top_cost_drivers_percentages() -> None:
    ensure_schema()
    uid = f"{U_PREFIX}top"
    db = SessionLocal()
    try:
        _clean_user(db, uid)
        for _ in range(3):
            record_llm_usage(
                db,
                user_id=uid,
                source="test",
                request_id="x",
                provider="openai",
                model="gpt-4o-mini",
                action_type="chat_response",
                input_tokens=500_000,
                output_tokens=0,
                used_user_key=False,
            )
        for _ in range(2):
            record_llm_usage(
                db,
                user_id=uid,
                source="test",
                request_id="y",
                provider="openai",
                model="gpt-4o-mini",
                action_type="web_search_summary",
                input_tokens=200_000,
                output_tokens=0,
                used_user_key=False,
            )
        summ = build_llm_usage_summary("all", db, uid, is_owner=False)
        top = summ.get("top_cost_drivers") or []
        assert top
        assert top[0].get("action") == "chat_response"
        assert int(top[0].get("percent") or 0) >= 50
        wss = next((r for r in top if r.get("action") == "web_search_summary"), None)
        assert wss is not None
        assert 10 <= int(wss.get("percent") or 0) <= 90
        for row in summ.get("by_action") or []:
            if row.get("action") in ("chat_response", "web_search_summary"):
                assert row.get("percent") is not None
    finally:
        _clean_user(db, uid)
        db.close()


def test_format_subline_null_cost_safety() -> None:
    """If estimated_cost is missing, formatting must not throw."""
    s: dict = {
        "used_llm": True,
        "input_tokens": 0,
        "output_tokens": 0,
        "total_tokens": 10,
        "estimated_cost_usd": None,
        "provider": "openai",
        "model": "x",
        "used_user_key": False,
    }
    line = format_usage_subline(s)
    assert isinstance(line, str) and "≈" in line
    assert "x" in line
