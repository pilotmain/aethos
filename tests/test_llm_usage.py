from __future__ import annotations

from sqlalchemy import delete, func, select

from app.core.db import SessionLocal, ensure_schema
from app.models.llm_usage_event import LlmUsageEvent
from app.services.llm_costs import estimate_llm_cost, get_known_model_pricing, normalize_model_name
from app.services.llm_usage_context import (
    LlmUsageState,
    bind_llm_usage_context,
    get_llm_usage_context,
    reset_llm_usage_state,
)
from app.services.llm_usage_recorder import (
    build_llm_usage_summary,
    get_recent_llm_usage,
    get_usage_by_action,
    get_usage_by_day,
    record_llm_usage,
)


def test_cost_estimate_known_model() -> None:
    c = estimate_llm_cost("openai", "gpt-4o", 1_000_000, 1_000_000)
    assert c is not None
    assert 15.0 < c < 30.0


def test_cost_unknown_model_returns_none() -> None:
    assert estimate_llm_cost("openai", "not-a-real-model-xyz-9999", 100, 200) is None
    assert estimate_llm_cost("acme", "x", 1, 1) is None


def test_pricing_table_has_anthropic_and_openai() -> None:
    t = get_known_model_pricing()
    assert "anthropic" in t
    assert "openai" in t


def test_normalize_model() -> None:
    assert normalize_model_name("openai", "models/gpt-4o-mini-2024") in (
        normalize_model_name("openai", "gpt-4o-mini"),
        "gpt-4o-mini-2024",
    )


def test_record_usage_creates_row() -> None:
    ensure_schema()
    db = SessionLocal()
    try:
        n0 = int(
            db.scalar(select(func.count()).select_from(LlmUsageEvent).where(LlmUsageEvent.user_id == "u_test_1"))
            or 0
        )
        with bind_llm_usage_context(user_id="u_test_1", source="test"):
            record_llm_usage(
                db,
                user_id="u_test_1",
                source="test",
                agent_key="nexa",
                action_type="chat_response",
                provider="openai",
                model="gpt-4o-mini",
                input_tokens=10,
                output_tokens=5,
                used_user_key=True,
            )
        n1 = int(
            db.scalar(select(func.count()).select_from(LlmUsageEvent).where(LlmUsageEvent.user_id == "u_test_1"))
            or 0
        )
        assert n1 == n0 + 1
    finally:
        db.execute(delete(LlmUsageEvent).where(LlmUsageEvent.user_id == "u_test_1"))
        db.commit()
        db.close()


def test_system_vs_user_key_in_summary() -> None:
    ensure_schema()
    db = SessionLocal()
    try:
        record_llm_usage(
            db,
            user_id="u_sku",
            source="test",
            provider="openai",
            model="gpt-4o-mini",
            input_tokens=1_000_000,
            output_tokens=0,
            used_user_key=False,
        )
        record_llm_usage(
            db,
            user_id="u_sku",
            source="test",
            provider="openai",
            model="gpt-4o-mini",
            input_tokens=500_000,
            output_tokens=0,
            used_user_key=True,
        )
        s = build_llm_usage_summary("all", db, "u_sku", is_owner=False)
        sc = float(s["system_key_cost_usd"] or 0)
        uc = float(s["user_key_cost_usd"] or 0)
        est = float(s["estimated_cost_usd"] or 0)
        assert abs(sc + uc - est) < 1e-4
    finally:
        db.execute(delete(LlmUsageEvent).where(LlmUsageEvent.user_id == "u_sku"))
        db.commit()
        db.close()


def test_build_summary_today_totals() -> None:
    ensure_schema()
    db = SessionLocal()
    try:
        s = build_llm_usage_summary("today", db, "nonexistent", is_owner=False)
        assert "total_calls" in s
        assert "by_provider" in s
    finally:
        db.close()


def test_get_recent_scoped_to_user() -> None:
    ensure_schema()
    db = SessionLocal()
    try:
        record_llm_usage(
            db,
            user_id="own_only",
            source="test",
            provider="openai",
            model="gpt-4o-mini",
            input_tokens=1,
            output_tokens=0,
            used_user_key=True,
        )
        record_llm_usage(
            db,
            user_id="other_user",
            source="test",
            provider="openai",
            model="gpt-4o-mini",
            input_tokens=99,
            output_tokens=0,
            used_user_key=True,
        )
        rec = get_recent_llm_usage(db, 20, "own_only", is_owner=False)
        assert len(rec) >= 1
        assert not any((r.get("total_tokens") or 0) == 99 for r in rec)
    finally:
        db.execute(delete(LlmUsageEvent).where(LlmUsageEvent.user_id == "own_only"))
        db.execute(delete(LlmUsageEvent).where(LlmUsageEvent.user_id == "other_user"))
        db.commit()
        db.close()


def test_owner_sees_all_rows() -> None:
    ensure_schema()
    db = SessionLocal()
    try:
        record_llm_usage(
            db,
            user_id="a",
            source="test",
            provider="openai",
            model="gpt-4o-mini",
            input_tokens=1,
            output_tokens=0,
            used_user_key=True,
        )
        record_llm_usage(
            db,
            user_id="b",
            source="test",
            provider="anthropic",
            model="claude-haiku-4-5-20251001",
            input_tokens=1,
            output_tokens=0,
            used_user_key=True,
        )
        r = get_recent_llm_usage(db, 20, "a", is_owner=True)
        assert len(r) >= 2
    finally:
        db.execute(delete(LlmUsageEvent).where(LlmUsageEvent.user_id == "a"))
        db.execute(delete(LlmUsageEvent).where(LlmUsageEvent.user_id == "b"))
        db.commit()
        db.close()


def test_action_breakdown() -> None:
    ensure_schema()
    db = SessionLocal()
    try:
        record_llm_usage(
            db,
            user_id="act",
            source="test",
            action_type="intent_classification",
            provider="openai",
            model="gpt-4o-mini",
            input_tokens=10,
            output_tokens=0,
            used_user_key=False,
        )
        a = get_usage_by_action("all", db, "act", is_owner=True)
        assert isinstance(a, list) and a
    finally:
        db.execute(delete(LlmUsageEvent).where(LlmUsageEvent.user_id == "act"))
        db.commit()
        db.close()


def test_daily_rollup() -> None:
    ensure_schema()
    db = SessionLocal()
    try:
        d = get_usage_by_day(7, db, None, is_owner=True)
        assert isinstance(d, list)
    finally:
        db.close()


def test_get_llm_usage_context_default() -> None:
    reset_llm_usage_state()
    st = get_llm_usage_context()
    assert isinstance(st, LlmUsageState)


def test_openai_recording_tolerates_missing_usage() -> None:
    from types import SimpleNamespace

    from app.services.llm_usage_recorder import record_openai_message_usage

    resp = SimpleNamespace(usage=None, choices=(SimpleNamespace(message=SimpleNamespace(content="{}")),))
    # db=None, no context — should not throw
    record_openai_message_usage(
        resp,
        model="gpt-4o-mini",
        used_user_key=False,
    )
