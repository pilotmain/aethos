"""
Phase 73 — agent self-diagnosis (Genesis Loop).

Reads recent failures from :class:`app.services.agent.activity_tracker.AgentActivityTracker`
and classifies them into a small set of recovery-friendly buckets:

* ``no_recent_failures`` — nothing to do.
* ``state_corrupted`` — agent is wedged in BUSY or stuck on a current_task far longer
  than the supervisor's stuck-busy threshold.
* ``repeated_llm_error`` — the failures concentrate on LLM-side errors (rate limit,
  network, auth) and a provider fallback is the natural recovery.
* ``transient`` — failures are scattered across action types with no clear pattern;
  recovery handler will try a state reset only.
* ``unknown`` — failures exist but don't match any heuristic.

The diagnosis is **heuristic-first** (cheap, deterministic, runs every supervisor
tick). When ``nexa_self_healing_enabled`` AND ``nexa_cost_aware_enabled`` are both
on, the diagnosis ALSO consults the LLM via
:func:`app.services.llm.completion.primary_complete_messages` with
``task_type="diagnosis"`` so Phase 72's cost-aware routing puts it on the cheap
tier (e.g., Haiku) automatically. The LLM summary is informational only — the
``cause_class`` always comes from the heuristic so a missing LLM key never breaks
the recovery decision.

Mistake memory (Phase 73 :class:`app.services.agent.learning.MistakeMemory`) is
consulted to surface "we've seen this before" context for the recovery handler.
"""

from __future__ import annotations

import logging
import time
from dataclasses import dataclass, field
from typing import Any

from app.core.config import get_settings
from app.services.agent.activity_tracker import (
    AgentActivityTracker,
    get_activity_tracker,
)
from app.services.agent.learning import (
    MistakeMemory,
    fingerprint_error,
    get_mistake_memory,
)
from app.services.sub_agent_registry import AgentStatus, SubAgent

logger = logging.getLogger(__name__)


# Cause classes — keep in sync with RecoveryHandler.attempt() strategy keys.
CAUSE_NO_FAILURES = "no_recent_failures"
CAUSE_STATE_CORRUPTED = "state_corrupted"
CAUSE_REPEATED_LLM_ERROR = "repeated_llm_error"
CAUSE_TRANSIENT = "transient"
CAUSE_UNKNOWN = "unknown"

ALL_CAUSE_CLASSES = {
    CAUSE_NO_FAILURES,
    CAUSE_STATE_CORRUPTED,
    CAUSE_REPEATED_LLM_ERROR,
    CAUSE_TRANSIENT,
    CAUSE_UNKNOWN,
}

# Substring patterns (lowercased) that point at LLM-layer failures we know how
# to recover from by switching providers / temporary fallback.
_LLM_ERROR_PATTERNS = (
    "rate limit",
    "rate_limit",
    "rate-limit",
    "429",
    "quota",
    "insufficient_quota",
    "invalid_api_key",
    "authentication",
    "anthropic",
    "openai",
    "timeout",
    "connection reset",
    "connection error",
    "read timeout",
    "service unavailable",
    "503",
    "502",
    "overloaded",
)

_STATE_HINT_PATTERNS = (
    "deadlock",
    "stuck",
    "wedged",
    "infinite loop",
    "task already running",
    "already busy",
)


@dataclass
class Diagnosis:
    """Structured output of :meth:`SelfDiagnosis.diagnose`."""

    agent_id: str
    cause_class: str
    summary: str
    error_count: int
    window_minutes: int
    top_errors: list[dict[str, Any]] = field(default_factory=list)
    similar_past_mistakes: list[dict[str, Any]] = field(default_factory=list)
    fingerprint: str | None = None
    llm_summary: str | None = None
    used_llm: bool = False

    def to_dict(self) -> dict[str, Any]:
        return {
            "agent_id": self.agent_id,
            "cause_class": self.cause_class,
            "summary": self.summary,
            "error_count": self.error_count,
            "window_minutes": self.window_minutes,
            "top_errors": list(self.top_errors),
            "similar_past_mistakes": list(self.similar_past_mistakes),
            "fingerprint": self.fingerprint,
            "llm_summary": self.llm_summary,
            "used_llm": self.used_llm,
        }


class SelfDiagnosis:
    """
    Stateless analyzer. Pass an :class:`AgentActivityTracker` and
    :class:`MistakeMemory` for tests; defaults wire to the singletons.
    """

    def __init__(
        self,
        *,
        tracker: AgentActivityTracker | None = None,
        mistake_memory: MistakeMemory | None = None,
        clock: callable | None = None,
    ) -> None:
        self.tracker = tracker or get_activity_tracker()
        self.mistake_memory = mistake_memory or get_mistake_memory()
        self._clock = clock or time.time

    def diagnose(
        self,
        agent: SubAgent,
        *,
        use_llm: bool | None = None,
    ) -> Diagnosis:
        """Run the heuristic + (optionally) the LLM summary for ``agent``."""
        s = get_settings()
        window_min = max(1, int(getattr(s, "nexa_agent_failure_window_minutes", 60) or 60))
        # Pull a slightly wider window so we don't miss failures right at the boundary,
        # then filter by occurrence time.
        history = self.tracker.get_agent_history(
            agent.id, hours=max(1, (window_min // 60) + 1), limit=200
        )
        # Within-window filter is approximate (tracker stores ISO strings) — the
        # activity tracker's hours filter already bounds the result; we rely on it.
        errors = [h for h in history if not h.get("success")]

        if not errors:
            return Diagnosis(
                agent_id=agent.id,
                cause_class=CAUSE_NO_FAILURES,
                summary=f"No failures for agent {agent.id} in the last {window_min} minutes.",
                error_count=0,
                window_minutes=window_min,
            )

        # Build a short list of top error strings.
        err_counts: dict[str, int] = {}
        for h in errors:
            txt = (h.get("error") or "").strip()[:200]
            if not txt:
                continue
            err_counts[txt] = err_counts.get(txt, 0) + 1
        top = sorted(err_counts.items(), key=lambda kv: kv[1], reverse=True)[:5]
        top_errors = [{"error": e, "count": c} for e, c in top]

        # Cause classification (highest precedence first).
        cause = self._classify(agent, errors)

        # Fingerprint the dominant error (or a synthetic one for state issues).
        if cause == CAUSE_STATE_CORRUPTED:
            fp_seed = f"state:{agent.status.value}:stuck"
        elif top:
            fp_seed = top[0][0]
        else:
            fp_seed = errors[0].get("error") or ""
        fingerprint = fingerprint_error(fp_seed)

        similar = self.mistake_memory.get_similar_mistakes(
            agent_id=agent.id, fingerprint=fingerprint, limit=5
        )

        summary = self._heuristic_summary(agent, cause, len(errors), top_errors)

        diag = Diagnosis(
            agent_id=agent.id,
            cause_class=cause,
            summary=summary,
            error_count=len(errors),
            window_minutes=window_min,
            top_errors=top_errors,
            similar_past_mistakes=similar,
            fingerprint=fingerprint,
        )

        # Optional LLM summary — informational only.
        want_llm = use_llm if use_llm is not None else bool(
            getattr(s, "nexa_cost_aware_enabled", False)
        )
        if want_llm:
            llm_text = self._llm_summary(agent, diag)
            if llm_text:
                diag.llm_summary = llm_text
                diag.used_llm = True

        logger.info(
            "self_diagnosis agent=%s cause=%s errors=%s used_llm=%s fingerprint=%r",
            agent.id,
            diag.cause_class,
            diag.error_count,
            diag.used_llm,
            (diag.fingerprint or "")[:80],
        )
        return diag

    def _classify(self, agent: SubAgent, errors: list[dict[str, Any]]) -> str:
        """Heuristic: state > LLM > transient > unknown."""
        # State-corrupted: stuck BUSY past the supervisor's reset threshold,
        # or any error string that mentions stuck/deadlock language.
        last_active = float(getattr(agent, "last_active", 0.0) or 0.0)
        stuck_for = self._clock() - last_active if last_active else 0.0
        if (
            agent.status == AgentStatus.BUSY
            and stuck_for >= 600.0  # 10 minutes — past supervisor's 5-minute reset
        ):
            return CAUSE_STATE_CORRUPTED

        joined = " ".join(
            ((h.get("error") or "") for h in errors if h.get("error"))
        ).lower()
        if any(p in joined for p in _STATE_HINT_PATTERNS):
            return CAUSE_STATE_CORRUPTED

        # LLM-side failures: most of the recent errors mention a known LLM pattern.
        llm_hits = sum(
            1
            for h in errors
            if any(p in (h.get("error") or "").lower() for p in _LLM_ERROR_PATTERNS)
        )
        if errors and llm_hits >= max(1, int(len(errors) * 0.5)):
            return CAUSE_REPEATED_LLM_ERROR

        # Transient: failures exist but don't fingerprint to one cluster.
        unique_fps = {fingerprint_error(h.get("error")) for h in errors if h.get("error")}
        if len(unique_fps) >= max(2, len(errors) // 2):
            return CAUSE_TRANSIENT

        return CAUSE_UNKNOWN

    def _heuristic_summary(
        self,
        agent: SubAgent,
        cause: str,
        error_count: int,
        top_errors: list[dict[str, Any]],
    ) -> str:
        head = top_errors[0]["error"] if top_errors else ""
        if cause == CAUSE_STATE_CORRUPTED:
            return (
                f"Agent {agent.id} appears state-corrupted "
                f"(status={agent.status.value}, errors={error_count}). "
                "Recovery: reset to IDLE and clear current_task."
            )
        if cause == CAUSE_REPEATED_LLM_ERROR:
            return (
                f"Agent {agent.id} hit {error_count} LLM-layer failures recently "
                f"(top: {head[:120]!r}). "
                "Recovery: enable a temporary fallback provider for this agent."
            )
        if cause == CAUSE_TRANSIENT:
            return (
                f"Agent {agent.id} has {error_count} scattered failures with no "
                "clear cluster. Recovery: light state reset; monitor for repeats."
            )
        return (
            f"Agent {agent.id} has {error_count} recent failures (top: {head[:120]!r}); "
            "no clear cause class. Recovery: state reset; escalate if repeats."
        )

    def _llm_summary(self, agent: SubAgent, diag: Diagnosis) -> str | None:
        """Best-effort cheap LLM summary. Never raises."""
        try:
            from app.services.llm.base import Message
            from app.services.llm.completion import primary_complete_messages

            system = (
                "You are an SRE assistant for an AI agent platform. Given a list of "
                "recent error strings from one agent, return a 2-3 sentence summary "
                "of the most likely root cause and the safest single recovery action. "
                "Do not invent facts. Plain text only, no markdown."
            )
            user_lines = [
                f"agent_id: {agent.id}",
                f"agent_domain: {agent.domain}",
                f"agent_status: {agent.status.value}",
                f"heuristic_cause: {diag.cause_class}",
                f"window_minutes: {diag.window_minutes}",
                f"error_count: {diag.error_count}",
                "top_errors:",
            ]
            for e in diag.top_errors[:5]:
                user_lines.append(f"  - x{e['count']}: {str(e['error'])[:200]}")
            if diag.similar_past_mistakes:
                user_lines.append("similar_past_mistakes (most recent first):")
                for m in diag.similar_past_mistakes[:3]:
                    user_lines.append(
                        f"  - strategy={m.get('recovery_strategy')!r} "
                        f"succeeded={m.get('recovery_succeeded')} "
                        f"error={str(m.get('error') or '')[:140]!r}"
                    )

            text = primary_complete_messages(
                [
                    Message(role="system", content=system),
                    Message(role="user", content="\n".join(user_lines)),
                ],
                task_type="diagnosis",
                max_tokens=200,
                temperature=0.2,
            )
            return (text or "").strip()[:1000] or None
        except Exception as exc:  # noqa: BLE001
            logger.warning("self_diagnosis LLM summary suppressed: %s", exc)
            return None


_self_diagnosis: SelfDiagnosis | None = None


def get_self_diagnosis() -> SelfDiagnosis:
    global _self_diagnosis
    if _self_diagnosis is None:
        _self_diagnosis = SelfDiagnosis()
    return _self_diagnosis


__all__ = [
    "ALL_CAUSE_CLASSES",
    "CAUSE_NO_FAILURES",
    "CAUSE_REPEATED_LLM_ERROR",
    "CAUSE_STATE_CORRUPTED",
    "CAUSE_TRANSIENT",
    "CAUSE_UNKNOWN",
    "Diagnosis",
    "SelfDiagnosis",
    "get_self_diagnosis",
]
