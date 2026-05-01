"""Long-running agent sessions — filesystem checkpoints + DB persistence (Phase 41–42)."""

from __future__ import annotations

import hashlib
import json
import uuid
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.long_running_session import NexaLongRunningSession
from app.services.events.envelope import emit_runtime_event
from app.services.logging.logger import get_logger
from app.services.memory.memory_store import MemoryStore

_log = get_logger("agents.long_running")

_REGISTRY: dict[str, "LongRunningSession"] = {}


def _utc_iso() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


def _utc_now() -> datetime:
    return datetime.now(timezone.utc)


def _stable_session_pk(user_id: str, session_key: str) -> str:
    raw = f"{(user_id or '').strip()}\n{(session_key or '').strip()}".encode()
    return hashlib.sha256(raw).hexdigest()[:24]


@dataclass
class LongRunningCheckpoint:
    """Serializable checkpoint for a session."""

    session_id: str
    user_id: str
    iteration: int = 0
    goal: str = ""
    context: dict[str, Any] = field(default_factory=dict)
    updated_at: str = ""


class LongRunningSession:
    """
    Persists across process cycles via JSON under the user's memory directory.

    Call :meth:`tick` from the scheduler / heartbeat to advance one cycle.
    """

    def __init__(self, user_id: str, session_id: str, goal: str) -> None:
        self.user_id = (user_id or "").strip()
        self.session_id = (session_id or "").strip() or uuid.uuid4().hex[:16]
        self.goal = (goal or "").strip()

    def _checkpoint_path(self) -> Path:
        ms = MemoryStore()
        d = ms.user_dir(self.user_id) / "long_running"
        d.mkdir(parents=True, exist_ok=True)
        return d / f"{self.session_id}.json"

    def load_checkpoint(self) -> LongRunningCheckpoint:
        p = self._checkpoint_path()
        if not p.is_file():
            return LongRunningCheckpoint(
                session_id=self.session_id,
                user_id=self.user_id,
                goal=self.goal,
                updated_at=_utc_iso(),
            )
        try:
            raw = json.loads(p.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            raw = {}
        return LongRunningCheckpoint(
            session_id=str(raw.get("session_id") or self.session_id),
            user_id=str(raw.get("user_id") or self.user_id),
            iteration=int(raw.get("iteration") or 0),
            goal=str(raw.get("goal") or self.goal),
            context=dict(raw.get("context") or {}),
            updated_at=str(raw.get("updated_at") or ""),
        )

    def save_checkpoint(self, cp: LongRunningCheckpoint) -> None:
        cp.updated_at = _utc_iso()
        p = self._checkpoint_path()
        blob = {
            "session_id": cp.session_id,
            "user_id": cp.user_id,
            "iteration": cp.iteration,
            "goal": cp.goal,
            "context": cp.context,
            "updated_at": cp.updated_at,
        }
        p.write_text(json.dumps(blob, ensure_ascii=False, indent=2), encoding="utf-8")

    def tick(self) -> dict[str, Any]:
        """Advance one scheduler cycle; extend with gateway/delegate hooks later."""
        cp = self.load_checkpoint()
        cp.iteration += 1
        cp.goal = self.goal or cp.goal
        cp.context.setdefault("ticks", 0)
        cp.context["ticks"] = int(cp.context["ticks"]) + 1
        self.save_checkpoint(cp)
        emit_runtime_event(
            "long_running.tick",
            user_id=self.user_id,
            payload={
                "session_id": self.session_id,
                "iteration": cp.iteration,
            },
        )
        _log.debug(
            "long_running.tick user=%s session=%s iteration=%s",
            self.user_id,
            self.session_id,
            cp.iteration,
        )
        return {
            "ok": True,
            "session_id": self.session_id,
            "user_id": self.user_id,
            "iteration": cp.iteration,
            "source": "filesystem",
        }


def upsert_db_session(
    db: Session,
    *,
    user_id: str,
    session_key: str,
    goal: str = "",
    interval_seconds: int = 300,
    state: dict[str, Any] | None = None,
    active: bool = True,
) -> NexaLongRunningSession:
    """Create or update a DB-backed session (survives API restart)."""
    pk = _stable_session_pk(user_id, session_key)
    uid = (user_id or "").strip()[:128]
    sk = (session_key or "").strip()[:128]
    row = db.scalar(
        select(NexaLongRunningSession).where(
            NexaLongRunningSession.user_id == uid,
            NexaLongRunningSession.session_key == sk,
        )
    )
    now = _utc_now()
    blob = json.dumps(state or {}, ensure_ascii=False)
    if row is None:
        row = NexaLongRunningSession(
            id=pk,
            user_id=uid,
            session_key=sk,
            goal=(goal or "").strip()[:50_000],
            state_json=blob,
            interval_seconds=max(30, int(interval_seconds or 300)),
            iteration=0,
            last_tick_at=None,
            active=active,
            created_at=now,
            updated_at=now,
        )
        db.add(row)
    else:
        row.goal = (goal or row.goal or "").strip()[:50_000]
        row.state_json = blob
        row.interval_seconds = max(30, int(interval_seconds or row.interval_seconds or 300))
        row.active = active
        row.updated_at = now
    db.commit()
    db.refresh(row)
    return row


def list_db_sessions(db: Session, *, user_id: str | None = None, active_only: bool = True) -> list[NexaLongRunningSession]:
    q = select(NexaLongRunningSession).order_by(NexaLongRunningSession.updated_at.desc())
    if user_id:
        q = q.where(NexaLongRunningSession.user_id == user_id.strip())
    if active_only:
        q = q.where(NexaLongRunningSession.active.is_(True))
    return list(db.scalars(q.limit(200)).all())


def tick_eligible_db_sessions(db: Session) -> list[dict[str, Any]]:
    """Advance DB-backed sessions whose interval has elapsed."""
    now = _utc_now()
    rows = list(
        db.scalars(select(NexaLongRunningSession).where(NexaLongRunningSession.active.is_(True))).all()
    )
    out: list[dict[str, Any]] = []
    for row in rows:
        iv = max(30, int(row.interval_seconds or 300))
        last = row.last_tick_at
        if last is not None:
            last_cmp = last if last.tzinfo else last.replace(tzinfo=timezone.utc)
            if (now - last_cmp).total_seconds() < iv:
                continue
        row.iteration = int(row.iteration or 0) + 1
        row.last_tick_at = now
        row.updated_at = now
        try:
            st = json.loads(row.state_json or "{}")
        except json.JSONDecodeError:
            st = {}
        st["ticks"] = int(st.get("ticks") or 0) + 1
        row.state_json = json.dumps(st, ensure_ascii=False)
        emit_runtime_event(
            "long_running.tick",
            user_id=row.user_id,
            payload={
                "session_key": row.session_key,
                "iteration": row.iteration,
                "source": "database",
            },
        )
        try:
            from app.core.config import get_settings

            st = get_settings()
            if getattr(st, "nexa_autonomous_mode", False) and getattr(st, "nexa_long_running_gateway_tick", False):
                from app.services.gateway.context import GatewayContext
                from app.services.gateway.runtime import NexaGateway

                goal = (row.goal or "").strip() or "Continue the long-running session."
                gctx = GatewayContext.from_channel(
                    row.user_id,
                    "long_running",
                    {
                        "via_gateway": True,
                        "long_running_session_key": row.session_key,
                        "iteration": row.iteration,
                    },
                )
                NexaGateway().handle_message(
                    gctx,
                    f"[long_running tick {row.iteration}] {goal[:4000]}",
                    db=db,
                )
        except Exception:
            _log.warning("long_running.gateway_invoke_failed", exc_info=True)
        out.append(
            {
                "ok": True,
                "session_key": row.session_key,
                "user_id": row.user_id,
                "iteration": row.iteration,
                "source": "database",
            }
        )
    if out:
        db.commit()
    return out


def register_session(sess: LongRunningSession) -> None:
    key = f"{sess.user_id}:{sess.session_id}"
    _REGISTRY[key] = sess


def unregister_session(user_id: str, session_id: str) -> None:
    _REGISTRY.pop(f"{user_id}:{session_id}", None)


def tick_all_registered() -> list[dict[str, Any]]:
    """In-memory ticks plus eligible DB-backed sessions (heartbeat hook)."""
    mem = [sess.tick() for sess in list(_REGISTRY.values())]
    db_out: list[dict[str, Any]] = []
    try:
        from app.core.db import SessionLocal

        with SessionLocal() as db:
            db_out = tick_eligible_db_sessions(db)
    except Exception:
        _log.warning("long_running.db_tick_failed", exc_info=True)
    return mem + db_out


__all__ = [
    "LongRunningCheckpoint",
    "LongRunningSession",
    "list_db_sessions",
    "register_session",
    "tick_all_registered",
    "tick_eligible_db_sessions",
    "unregister_session",
    "upsert_db_session",
]
