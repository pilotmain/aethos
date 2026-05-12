# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2025 AethOS AI

"""
Persist LLM usage metadata only. Recording failures must not affect callers.
"""

from __future__ import annotations

import logging
from collections.abc import Sequence
from datetime import UTC, date, datetime, timedelta
from typing import Any

from sqlalchemy import and_, func, select
from sqlalchemy.orm import Session

from app.models.llm_usage_event import LlmUsageEvent
from app.models.response_turn_event import ResponseTurnEvent
from app.services.llm_action_types import normalize_action_type
from app.services.llm_costs import estimate_llm_cost
from app.services.llm_usage_context import get_llm_usage_context, resolve_db_for_usage

logger = logging.getLogger(__name__)


def _tok_from_anthropic_message(msg: Any) -> tuple[int, int]:
    usage = getattr(msg, "usage", None)
    if not usage:
        return 0, 0
    it = int(getattr(usage, "input_tokens", None) or 0)
    ot = int(getattr(usage, "output_tokens", None) or 0)
    return it, ot


def _tok_from_openai_response(resp: Any) -> tuple[int, int, int | None]:
    u = getattr(resp, "usage", None)
    if not u:
        return 0, 0, None
    it = int(getattr(u, "prompt_tokens", None) or getattr(u, "input_tokens", None) or 0)
    ot = int(getattr(u, "completion_tokens", None) or getattr(u, "output_tokens", None) or 0)
    tot = getattr(u, "total_tokens", None)
    tti = int(tot) if tot is not None else it + ot
    return it, ot, tti


def record_openai_message_usage(
    response: Any,
    *,
    model: str | None,
    used_user_key: bool,
    db: Session | None = None,
    success: bool = True,
    error_type: str | None = None,
) -> None:
    it, ot, _t = _tok_from_openai_response(response)
    record_llm_usage(
        db,
        provider="openai",
        model=model,
        input_tokens=it,
        output_tokens=ot,
        used_user_key=used_user_key,
        success=success,
        error_type=error_type,
    )


def record_anthropic_message_usage(
    msg: Any,
    *,
    model: str | None,
    used_user_key: bool,
    db: Session | None = None,
    success: bool = True,
    error_type: str | None = None,
) -> None:
    it, ot = _tok_from_anthropic_message(msg)
    record_llm_usage(
        db,
        provider="anthropic",
        model=model,
        input_tokens=it,
        output_tokens=ot,
        used_user_key=used_user_key,
        success=success,
        error_type=error_type,
    )


def _as_naive_utc(dt: datetime) -> datetime:
    if dt.tzinfo is not None:
        return dt.astimezone(UTC).replace(tzinfo=None)
    return dt


def _today_range() -> tuple[datetime, datetime]:
    nowu = datetime.now(UTC)
    if nowu.tzinfo is None:  # pragma: no cover
        nowu = nowu.replace(tzinfo=UTC)
    s = nowu.replace(hour=0, minute=0, second=0, microsecond=0)
    e = s + timedelta(days=1)
    return _as_naive_utc(s), _as_naive_utc(e)


def _date_filter(period: str) -> tuple[datetime, datetime, str]:
    p = (period or "today").lower().strip()
    as_n = _as_naive_utc(datetime.now(UTC))
    if p in ("7d", "7"):
        return (as_n - timedelta(days=7), as_n + timedelta(seconds=1), "7d")
    if p in ("30d", "30"):
        return (as_n - timedelta(days=30), as_n + timedelta(seconds=1), "30d")
    if p == "all":
        return (datetime(1970, 1, 1, 0, 0, 0), as_n + timedelta(seconds=1), "all")
    s, e = _today_range()
    return s, e, "today"


def _user_scope(uid: str | None, is_owner: bool) -> str | None:
    if is_owner or not (uid or "").strip():
        return None
    return (uid or "").strip()


def _user_where_clause(
    app_user_id: str | None, is_owner: bool
) -> list[Any]:
    s = _user_scope(app_user_id, is_owner)
    if s is None:
        return []
    return [LlmUsageEvent.user_id == s]


def _merge_from_context(
    user_id: str | None,
    telegram_user_id: str | None,
    source: str,
    agent_key: str | None,
    action_type: str | None,
    session_id: str | None,
    request_id: str | None,
) -> tuple[str | None, str | None, str, str | None, str | None, str | None, str | None]:
    ctx = get_llm_usage_context()
    u = user_id if user_id is not None else ctx.user_id
    tg = telegram_user_id if telegram_user_id is not None else ctx.telegram_user_id
    src = (source or "").strip() or (ctx.source or "unknown")
    a = agent_key if agent_key is not None else ctx.agent_key
    at = action_type if action_type is not None else ctx.action_type
    se = session_id if session_id is not None else ctx.session_id
    rq = request_id if request_id is not None else ctx.request_id
    return (u, tg, src, a, at, se, rq)


def record_llm_usage(
    db: Session | None,
    *,
    user_id: str | None = None,
    telegram_user_id: str | None = None,
    source: str = "unknown",
    agent_key: str | None = None,
    action_type: str | None = None,
    session_id: str | None = None,
    request_id: str | None = None,
    provider: str = "",
    model: str | None = None,
    input_tokens: int = 0,
    output_tokens: int = 0,
    used_user_key: bool = False,
    success: bool = True,
    error_type: str | None = None,
    metadata_json: dict | None = None,
) -> None:
    dbs = db or resolve_db_for_usage()
    if dbs is None:
        logger.debug("llm usage skipped: no database session in context")
        return
    (u, tg, src, ag, act, se, rq) = _merge_from_context(
        user_id, telegram_user_id, source, agent_key, action_type, session_id, request_id
    )
    act = normalize_action_type(act)
    it = max(0, int(input_tokens or 0))
    ot = max(0, int(output_tokens or 0))
    tot = it + ot
    p = (provider or "").lower().strip() or "unknown"
    est = estimate_llm_cost(p, model, it, ot)
    try:
        row = LlmUsageEvent(
            user_id=u,
            telegram_user_id=tg,
            session_id=se,
            request_id=rq,
            source=src,
            agent_key=ag,
            action_type=act,
            provider=p,
            model=(str(model)[:120] if model is not None else None),
            input_tokens=it,
            output_tokens=ot,
            total_tokens=tot,
            estimated_cost_usd=est,
            used_user_key=bool(used_user_key),
            success=bool(success),
            error_type=error_type,
            metadata_json=dict(metadata_json) if metadata_json is not None else {},
        )
        dbs.add(row)
        dbs.commit()
        try:
            from app.services.observability import get_observability

            obs = get_observability()
            obs.record_metric("llm.calls", 1.0, "count")
            obs.record_metric("llm.tokens", float(tot), "tokens")
            if p and p != "unknown":
                obs.record_metric(f"llm.provider.{p}.calls", 1.0, "count")
        except Exception:
            pass
    except Exception as e:  # noqa: BLE001
        try:
            dbs.rollback()
        except Exception:  # noqa: BLE001
            pass
        logger.warning("llm usage record failed (suppressed): %s", type(e).__name__, exc_info=False)


def _events_in_range(
    db: Session, start: datetime, end: datetime, app_user_id: str | None, is_owner: bool
) -> list[LlmUsageEvent]:
    parts: list[Any] = [
        LlmUsageEvent.created_at >= start,
        LlmUsageEvent.created_at < end,
    ] + _user_where_clause(app_user_id, is_owner)
    c = and_(*parts)
    return list(db.scalars(select(LlmUsageEvent).where(c).order_by(LlmUsageEvent.id)).all())  # type: ignore[call-overload]


def _sum_block(rows: Sequence[LlmUsageEvent]) -> dict[str, int | float]:
    calls = len(rows)
    it = sum(int(r.input_tokens) for r in rows)
    ot = sum(int(r.output_tokens) for r in rows)
    tot = sum(int(r.total_tokens) for r in rows)
    c_all = c_sys = c_byok = 0.0
    for r in rows:
        v = float(r.estimated_cost_usd) if r.estimated_cost_usd is not None else 0.0
        c_all += v
        if r.used_user_key:
            c_byok += v
        else:
            c_sys += v
    return {
        "total_calls": calls,
        "total_input_tokens": it,
        "total_output_tokens": ot,
        "total_tokens": tot,
        "estimated_cost_usd": round(c_all, 6),
        "system_key_cost_usd": round(c_sys, 6),
        "user_key_cost_usd": round(c_byok, 6),
    }


def _by_dim(
    rows: Sequence[LlmUsageEvent], key_attr: str, out_key: str
) -> list[dict[str, Any]]:
    m: dict[str, list[LlmUsageEvent]] = {}
    for r in rows:
        v = getattr(r, key_attr)
        if v is None or (isinstance(v, str) and not v.strip()):
            k = "none"
        else:
            k = str(v)
        m.setdefault(k, []).append(r)
    out: list[dict[str, Any]] = []
    for k, g in sorted(m.items(), key=lambda x: -_sum_block(x[1])["total_calls"]):  # type: ignore[index,operator]
        b = _sum_block(g)
        b[out_key] = k
        out.append(b)  # type: ignore[arg-type]
    return out  # type: ignore[return-value]


def build_usage_summary_for_request(db: Session, request_id: str | None) -> dict[str, Any]:
    """Aggregates LlmUsageEvent rows for a single request_id. No secrets; safe to return to client."""
    if not (request_id or "").strip():
        return {
            "used_llm": False,
            "input_tokens": 0,
            "output_tokens": 0,
            "total_tokens": 0,
            "estimated_cost_usd": None,
            "provider": None,
            "model": None,
            "used_user_key": False,
        }
    rid = (request_id or "").strip()
    rows = list(
        db.scalars(select(LlmUsageEvent).where(LlmUsageEvent.request_id == rid).order_by(LlmUsageEvent.id)).all()  # type: ignore[call-overload]
    )
    if not rows:
        return {
            "used_llm": False,
            "input_tokens": 0,
            "output_tokens": 0,
            "total_tokens": 0,
            "estimated_cost_usd": None,
            "provider": None,
            "model": None,
            "used_user_key": False,
        }
    it = sum(int(r.input_tokens) for r in rows)
    ot = sum(int(r.output_tokens) for r in rows)
    tt = sum(int(r.total_tokens) for r in rows)
    ctot = 0.0
    for r in rows:
        ctot += float(r.estimated_cost_usd) if r.estimated_cost_usd is not None else 0.0
    pset = {r.provider for r in rows if (r.provider or "").strip()}
    mset = {r.model for r in rows if (r.model or "").strip()}
    prov: str | None
    mdl: str | None
    if len(pset) <= 1:
        prov = (rows[0].provider or None) if pset else None
    else:
        prov = "mixed"
    if len(mset) <= 1:
        mdl = (rows[0].model or None) if mset else None
    else:
        mdl = "mixed"
    uuk = any(bool(r.used_user_key) for r in rows)
    return {
        "used_llm": True,
        "input_tokens": it,
        "output_tokens": ot,
        "total_tokens": tt,
        "estimated_cost_usd": round(ctot, 6) if ctot else None,
        "provider": prov,
        "model": mdl,
        "used_user_key": uuk,
    }


def record_response_turn(
    db: Session,
    *,
    user_id: str,
    session_id: str,
    request_id: str,
    had_llm: bool,
) -> None:
    try:
        ev = ResponseTurnEvent(
            user_id=(user_id or "").strip()[:64],
            session_id=(session_id or "default").strip()[:128] or "default",
            request_id=(request_id or "").strip()[:64] or "unknown",
            had_llm=bool(had_llm),
        )
        db.add(ev)
        db.commit()
    except Exception:  # noqa: BLE001
        try:
            db.rollback()
        except Exception:  # noqa: BLE001
            pass
        logger.debug("response turn record failed", exc_info=True)


def get_session_usage_summary(
    db: Session, session_id: str, app_user_id: str | None, *, is_owner: bool
) -> dict[str, Any]:
    s = (session_id or "default").strip() or "default"
    parts: list[Any] = [LlmUsageEvent.session_id == s] + _user_where_clause(app_user_id, is_owner)
    q: Any
    if len(parts) == 1:
        q = parts[0]
    else:
        q = and_(*parts)
    rows = list(
        db.scalars(select(LlmUsageEvent).where(q)).all()  # type: ignore[call-overload]
    )
    ttot = sum(int(r.total_tokens) for r in rows)
    call_count = len(rows)
    csum = 0.0
    for r in rows:
        csum += float(r.estimated_cost_usd) if r.estimated_cost_usd is not None else 0.0
    return {
        "session_id": s,
        "total_tokens": ttot,
        "total_cost_usd": round(csum, 6) if csum else None,
        "call_count": call_count,
    }


def _efficiency_block(
    db: Session, start: datetime, end: datetime, app_user_id: str | None, is_owner: bool
) -> dict[str, Any]:
    c = and_(ResponseTurnEvent.created_at >= start, ResponseTurnEvent.created_at < end)
    ws = _user_scope(app_user_id, is_owner)
    if ws is not None:
        c = and_(c, ResponseTurnEvent.user_id == ws)
    total = int(db.scalar(select(func.count()).select_from(ResponseTurnEvent).where(c)) or 0)
    llm_q = and_(c, ResponseTurnEvent.had_llm.is_(True))  # type: ignore[union-attr]
    no_llm = and_(c, ResponseTurnEvent.had_llm.is_(False))
    llm_calls = int(
        db.scalar(select(func.count()).select_from(ResponseTurnEvent).where(llm_q))  # type: ignore[arg-type]
        or 0
    )
    non_llm = int(
        db.scalar(select(func.count()).select_from(ResponseTurnEvent).where(no_llm))  # type: ignore[arg-type]
        or 0
    )
    if total and abs(llm_calls + non_llm - total) > 1:  # pragma: no cover
        non_llm = max(0, total - llm_calls)
    ratio: float | None
    if total:
        ratio = float(non_llm) / float(total) if total else 0.0
    else:
        ratio = None
    return {
        "total_actions": total,
        "llm_calls": llm_calls,
        "non_llm_actions": non_llm,
        "efficiency_ratio": (round(ratio, 4) if ratio is not None else None),
    }


def _top_cost_drivers(rows: Sequence[LlmUsageEvent], *, top_n: int = 6) -> list[dict[str, Any]]:
    by_act: dict[str, list[LlmUsageEvent]] = {}
    for r in rows:
        a = (r.action_type or "none")
        a = str(a) if a else "none"
        a = normalize_action_type(a) if a != "none" else a
        by_act.setdefault(a, []).append(r)
    items: list[tuple[str, int, float]] = []
    for a, g in by_act.items():
        cost = 0.0
        for r in g:
            cost += float(r.estimated_cost_usd) if r.estimated_cost_usd is not None else 0.0
        items.append((a, len(g), cost))
    cost_total = sum(x[2] for x in items) or 0.0
    tcalls = len(rows)
    out: list[dict[str, Any]] = []
    for a, cnt, cost in sorted(items, key=lambda t: -t[2])[:top_n]:
        if cost_total > 0:
            pctf = int(min(100, max(0, round(100.0 * cost / cost_total))))
        else:
            pctf = int(min(100, max(0, round(100.0 * cnt / tcalls)))) if tcalls else 0
        out.append(
            {
                "action": a,
                "count": cnt,
                "cost": round(cost, 6) if cost else 0.0,
                "percent": pctf,
            }
        )
    return out


def count_llm_events_for_request(db: Session, request_id: str | None) -> int:
    if not (request_id or "").strip():
        return 0
    rid = (request_id or "").strip()
    n = int(
        db.scalar(
            select(func.count())
            .select_from(LlmUsageEvent)
            .where(LlmUsageEvent.request_id == rid)  # type: ignore[arg-type]
        )
        or 0
    )
    return n


def format_usage_subline(usage: dict[str, Any]) -> str:
    """Single-line copy for web/Telegram; no secrets."""
    if not usage.get("used_llm"):
        return "No LLM call · handled via tools"
    tok = int(usage.get("total_tokens", 0) or 0)
    if tok >= 1000:
        tks = f"≈ {tok / 1000.0:.1f}k"
    else:
        tks = f"≈ {tok}"
    c = usage.get("estimated_cost_usd")
    p = str(usage.get("provider") or "?")
    pcap = "mixed" if p == "mixed" else (p[0:1].upper() + p[1:].lower() if p else "?")
    if usage.get("used_user_key"):
        if c is not None:
            return f"{tks} tokens · ${float(c):.3f} · user key"
        return f"{tks} tokens · user key"
    if c is not None:
        return f"{tks} tokens · ${float(c):.3f} · {pcap} · system key"
    return f"{tks} tokens · {pcap} · system key"


def build_llm_usage_summary(
    period: str,
    db: Session,
    app_user_id: str | None,
    *,
    is_owner: bool,
) -> dict[str, Any]:
    s, e, p = _date_filter(period)
    rows = _events_in_range(db, s, e, app_user_id, is_owner)
    t = _sum_block(rows)
    by_provider: list[dict[str, Any]] = []
    for b in _by_dim(rows, "provider", "provider"):
        b = dict(b)
        by_provider.append(
            {
                "provider": b.get("provider"),
                "calls": b["total_calls"],
                "input_tokens": b["total_input_tokens"],
                "output_tokens": b["total_output_tokens"],
                "total_tokens": b["total_tokens"],
                "estimated_cost_usd": b["estimated_cost_usd"],
            }
        )
    by_agent: list[dict[str, Any]] = []
    for b in _by_dim(rows, "agent_key", "agent"):
        b = dict(b)
        by_agent.append(
            {
                "agent": b.get("agent"),
                "calls": b["total_calls"],
                "input_tokens": b["total_input_tokens"],
                "output_tokens": b["total_output_tokens"],
                "total_tokens": b["total_tokens"],
                "estimated_cost_usd": b["estimated_cost_usd"],
            }
        )
    by_action: list[dict[str, Any]] = []
    for b in _by_dim(rows, "action_type", "action"):
        b = dict(b)
        by_action.append(
            {
                "action": b.get("action"),
                "calls": b["total_calls"],
                "input_tokens": b["total_input_tokens"],
                "output_tokens": b["total_output_tokens"],
                "total_tokens": b["total_tokens"],
                "estimated_cost_usd": b["estimated_cost_usd"],
            }
        )
    t_cost = float(t["estimated_cost_usd"] or 0) or 0.0
    t_e_calls = int(t.get("total_calls", 0) or 0)
    for item in by_action:
        cst = float((item or {}).get("estimated_cost_usd") or 0) or 0.0
        if t_cost > 0:
            item["percent"] = int(min(100, max(0, round(100.0 * cst / t_cost))))  # type: ignore[assignment,operator]
        else:
            c_int = int((item or {}).get("total_calls", 0) or 0)
            if t_e_calls and c_int:
                item["percent"] = int(min(100, max(0, round(100.0 * c_int / t_e_calls))))  # type: ignore[assignment]
            else:
                item["percent"] = 0  # type: ignore[assignment]
        item["cost"] = round(cst, 6)  # type: ignore[assignment,typeddict]
    top_cost = _top_cost_drivers(rows)
    eff = _efficiency_block(db, s, e, app_user_id, is_owner)
    return {
        "period": p,
        "time_start_utc": s.replace(tzinfo=UTC).isoformat() if s else None,
        "time_end_utc": e.replace(tzinfo=UTC).isoformat() if e else None,
        "total_calls": t["total_calls"],
        "total_input_tokens": t["total_input_tokens"],
        "total_output_tokens": t["total_output_tokens"],
        "total_tokens": t["total_tokens"],
        "estimated_cost_usd": t["estimated_cost_usd"],
        "system_key_cost_usd": t["system_key_cost_usd"],
        "user_key_cost_usd": t["user_key_cost_usd"],
        "by_provider": by_provider,
        "by_agent": by_agent,
        "by_action": by_action,
        "top_cost_drivers": top_cost,
        "efficiency": eff,
    }


def get_cost_summary_today(
    db: Session,
    app_user_id: str | None,
    *,
    is_owner: bool,
) -> dict[str, Any]:
    """
    Phase 72 — compact "today's cost" block for the CEO dashboard.

    Reuses :func:`build_llm_usage_summary` so the CEO dashboard and the
    `/usage/*` API stay on a single aggregation source. Returns a stable shape
    the web UI can render directly:

    .. code-block:: python

        {
            "total_cost_usd": 0.0123,
            "system_key_cost_usd": 0.0090,
            "user_key_cost_usd": 0.0033,
            "total_calls": 47,
            "total_tokens": 18432,
            "by_provider": [{"provider": "anthropic", "calls": ..., "estimated_cost_usd": ...}, ...],
            "top_actions": [{"action": "...", "count": ..., "cost": ..., "percent": ...}, ...],
            "scope": "owner" | "user",
        }
    """
    summary = build_llm_usage_summary("today", db, app_user_id, is_owner=is_owner)
    return {
        "total_cost_usd": float(summary.get("estimated_cost_usd") or 0.0),
        "system_key_cost_usd": float(summary.get("system_key_cost_usd") or 0.0),
        "user_key_cost_usd": float(summary.get("user_key_cost_usd") or 0.0),
        "total_calls": int(summary.get("total_calls") or 0),
        "total_tokens": int(summary.get("total_tokens") or 0),
        "by_provider": list(summary.get("by_provider") or []),
        "top_actions": list((summary.get("top_cost_drivers") or [])[:5]),
        "scope": "owner" if is_owner else "user",
    }


def get_recent_llm_usage(
    db: Session, limit: int, app_user_id: str | None, *, is_owner: bool
) -> list[dict[str, Any]]:
    lim = max(1, min(500, int(limit)))
    q = select(LlmUsageEvent)
    s = _user_scope(app_user_id, is_owner)
    if s is not None:
        q = q.where(LlmUsageEvent.user_id == s)  # type: ignore[assignment]
    q = q.order_by(LlmUsageEvent.id.desc()).limit(lim)
    rows = list(db.scalars(q).all())
    out: list[dict[str, Any]] = []
    for r in rows:
        out.append(
            {
                "at": (r.created_at or datetime(1970, 1, 1)).replace(tzinfo=UTC).isoformat()
                if r.created_at
                else None,
                "provider": r.provider,
                "model": r.model,
                "source": r.source,
                "agent": r.agent_key,
                "action": r.action_type,
                "input_tokens": r.input_tokens,
                "output_tokens": r.output_tokens,
                "total_tokens": r.total_tokens,
                "estimated_cost_usd": r.estimated_cost_usd,
                "used_user_key": r.used_user_key,
                "success": r.success,
                "error_type": r.error_type,
            }
        )
    return out


def get_usage_by_action(
    period: str,
    db: Session,
    app_user_id: str | None,
    *,
    is_owner: bool,
) -> list[dict[str, Any]]:
    s, e, _p = _date_filter(period)
    rows = _events_in_range(db, s, e, app_user_id, is_owner)
    r: list[dict[str, Any]] = []
    for b in _by_dim(rows, "action_type", "action"):
        b = dict(b)
        r.append(
            {
                "action": b.get("action"),
                "calls": b["total_calls"],
                "input_tokens": b["total_input_tokens"],
                "output_tokens": b["total_output_tokens"],
                "total_tokens": b["total_tokens"],
                "estimated_cost_usd": b["estimated_cost_usd"],
            }
        )
    return r


def get_usage_by_day(
    days: int,
    db: Session,
    app_user_id: str | None,
    *,
    is_owner: bool,
) -> list[dict[str, Any]]:
    d = max(1, min(90, int(days)))
    as_n = _as_naive_utc(datetime.now(UTC))
    start = as_n - timedelta(days=d)
    rows = _events_in_range(db, start, as_n + timedelta(seconds=1), app_user_id, is_owner)
    by: dict[date, list[LlmUsageEvent]] = {}
    for r in rows:
        t = r.created_at
        if t is None:
            continue
        dkey = t.date() if isinstance(t, datetime) else t
        by.setdefault(dkey, []).append(r)  # type: ignore[union-attr]
    out: list[dict[str, Any]] = []
    for dkey in sorted(by.keys(), reverse=True):
        g = by[dkey]
        t = _sum_block(g)
        out.append(
            {
                "day": dkey.isoformat(),
                "total_calls": t["total_calls"],
                "total_input_tokens": t["total_input_tokens"],
                "total_output_tokens": t["total_output_tokens"],
                "total_tokens": t["total_tokens"],
                "estimated_cost_usd": t["estimated_cost_usd"],
                "system_key_cost_usd": t["system_key_cost_usd"],
                "user_key_cost_usd": t["user_key_cost_usd"],
            }
        )
    return out
