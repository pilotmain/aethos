# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2025 AethOS AI

from __future__ import annotations

import json
from types import SimpleNamespace

from app.core.db import ensure_schema
from app.models.conversation_context import ConversationContext
from app.services.conversation_context_service import get_last_decision_from_context
from sqlalchemy import delete
from app.services.decision_summary import (
    R_CODE_CHANGE,
    R_CURRENT_PUBLIC,
    R_NO_LLM,
    R_PUBLIC_URL,
    build_decision_for_telegram_turn,
    build_decision_summary,
    decision_for_dev_job,
    format_decision_for_telegram_why,
    infer_decision_for_web_main,
    merge_no_llm_path,
    _sanitize_reason,
)


def test_dev_job_decision_approval() -> None:
    job = SimpleNamespace(
        risk_level="normal",
        approval_required=True,
        status="needs_approval",
    )
    d = decision_for_dev_job(job=job, project_tool="aider")
    assert d["action"] == "dev_job"
    assert d["agent"] == "developer"
    assert d["tool"] == "aider"
    assert "code" in d["reason"].lower() or "file" in d["reason"].lower()
    assert d["approval_required"] is True


def test_public_url_reason() -> None:
    d = infer_decision_for_web_main(
        user_text="read https://example.com ",
        routed_agent_key="nexa",
        intent="general",
        response_kind="public_web",
    )
    assert d["action"] == "public_url_summary"
    assert R_PUBLIC_URL in d["reason"] or "public" in d["reason"].lower()


def test_web_search_reason() -> None:
    d = infer_decision_for_web_main(
        user_text="search the web for latest news",
        routed_agent_key="research",
        intent="general",
        response_kind="web_search",
    )
    assert d["action"] == "web_search_summary"
    assert d["tool"] == "web_search"
    assert R_CURRENT_PUBLIC in d["reason"] or "public" in d["reason"].lower()


def test_marketing_web_analysis_decision() -> None:
    d = infer_decision_for_web_main(
        user_text="@marketing analyze https://a.com",
        routed_agent_key="marketing",
        intent="general",
        response_kind="marketing_web_analysis",
    )
    assert d.get("action") == "marketing_web_analysis"
    assert d.get("tool") == "marketing_web_tools"
    assert (d.get("agent") or "").lower() == "marketing"


def test_tool_only_no_llm() -> None:
    base = build_decision_summary(
        agent_key="nexa",
        action="chat_response",
        tool="llm",
        reason="",
    )
    out = merge_no_llm_path(base, had_llm=False, tool_hint="local_state")
    assert out["action"] == "tool_only"
    assert R_NO_LLM in out["reason"] or "LLM" in out["reason"]


def test_approval_copy_dev() -> None:
    d = build_decision_summary(
        agent_key="developer",
        action="dev_job",
        tool="aider",
        reason=R_CODE_CHANGE,
        risk="normal",
        approval_required=True,
    )
    t = format_decision_for_telegram_why(d)
    assert "Required" in t
    assert "chain" not in t.lower()


def test_no_cot_in_sanitized() -> None:
    s = _sanitize_reason("We used chain of thought to decide this")
    assert "chain of thought" not in s.lower()
    assert "Nexa" in s or "general" in s.lower()  # template fallback


def test_why_text_empty() -> None:
    t = format_decision_for_telegram_why(None)
    assert "don" in t.lower() or "no recent" in t.lower()


def test_telegram_turn_with_job() -> None:
    job = SimpleNamespace(
        risk_level="low",
        approval_required=False,
        status="queued",
    )
    d = build_decision_for_telegram_turn(
        user_text="@dev fix",
        intent="dev_command",
        agent_key="developer",
        extras={"job": job},
    )
    assert d["action"] == "dev_job"
    assert d["agent"] == "developer"


def test_last_decision_in_context() -> None:
    from app.core.db import SessionLocal

    ensure_schema()
    db = SessionLocal()
    try:
        c = ConversationContext(
            user_id="u_test_dec_1",
            recent_messages_json="[]",
            last_decision_json=json.dumps(
                {
                    "agent": "research",
                    "action": "x",
                    "tool": "y",
                    "reason": "z",
                    "risk": "low",
                    "approval_required": False,
                }
            ),
        )
        db.add(c)
        db.commit()
        d2 = get_last_decision_from_context(c)
        assert d2 and d2.get("agent") == "research"
    finally:
        db.execute(
            delete(ConversationContext).where(ConversationContext.user_id == "u_test_dec_1")
        )
        db.commit()
        db.close()
