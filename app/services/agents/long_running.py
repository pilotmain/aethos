"""Long-running agent sessions — checkpointed state, scheduler-driven ticks (Phase 41)."""

from __future__ import annotations

import json
import uuid
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from app.services.events.envelope import emit_runtime_event
from app.services.logging.logger import get_logger
from app.services.memory.memory_store import MemoryStore

_log = get_logger("agents.long_running")

_REGISTRY: dict[str, "LongRunningSession"] = {}


def _utc_iso() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


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
        }


def register_session(sess: LongRunningSession) -> None:
    key = f"{sess.user_id}:{sess.session_id}"
    _REGISTRY[key] = sess


def unregister_session(user_id: str, session_id: str) -> None:
    _REGISTRY.pop(f"{user_id}:{session_id}", None)


def tick_all_registered() -> list[dict[str, Any]]:
    """Invoke one tick per registered in-memory session (heartbeat hook)."""
    return [sess.tick() for sess in list(_REGISTRY.values())]


__all__ = [
    "LongRunningCheckpoint",
    "LongRunningSession",
    "register_session",
    "tick_all_registered",
    "unregister_session",
]
