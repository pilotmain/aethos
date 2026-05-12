# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2025 AethOS AI

"""
Phase 73 — agent auto-recovery (Genesis Loop).

Sub-agents are **logical**, not OS subprocesses (see the docstring on
:class:`app.services.sub_agent_registry.SubAgent`), so the recovery primitives
here are in-process state mutations: status reset, ``current_task`` clear,
per-agent fallback-LLM flag in ``metadata``, and pause + escalate when nothing
works.

``RecoveryHandler`` is the single entry point — given a
:class:`app.services.agent.self_diagnosis.Diagnosis` it picks a strategy keyed
off ``diagnosis.cause_class``, applies it via the registry, and records the
attempt to :class:`app.services.agent.learning.MistakeMemory` so future
diagnoses can prefer a known-good strategy. Per-agent recovery attempts are
counted in ``agent.metadata.recovery_attempts`` and capped by
:data:`Settings.nexa_agent_max_auto_recovery_attempts` so a flapping agent
escalates instead of looping forever.
"""

from __future__ import annotations

import logging
import time
from dataclasses import dataclass
from typing import Any

from app.core.config import get_settings
from app.services.agent.activity_tracker import (
    AgentActivityTracker,
    get_activity_tracker,
)
from app.services.agent.learning import MistakeMemory, get_mistake_memory
from app.services.agent.self_diagnosis import (
    CAUSE_NO_FAILURES,
    CAUSE_REPEATED_LLM_ERROR,
    CAUSE_STATE_CORRUPTED,
    CAUSE_TRANSIENT,
    CAUSE_UNKNOWN,
    Diagnosis,
)
from app.services.sub_agent_registry import AgentRegistry, AgentStatus, SubAgent

logger = logging.getLogger(__name__)


# Recovery strategy ids — referenced by tests + mistake memory + tracker logs.
STRATEGY_NONE = "none"
STRATEGY_STATE_RESET = "state_reset"
STRATEGY_LLM_FALLBACK = "llm_fallback"
STRATEGY_PAUSE = "pause"
STRATEGY_CAPPED = "capped"


@dataclass
class RecoveryResult:
    """Outcome of a single :meth:`RecoveryHandler.attempt` call."""

    agent_id: str
    cause_class: str
    strategy: str
    succeeded: bool
    reason: str
    attempts_used: int
    escalate: bool

    def to_dict(self) -> dict[str, Any]:
        return {
            "agent_id": self.agent_id,
            "cause_class": self.cause_class,
            "strategy": self.strategy,
            "succeeded": self.succeeded,
            "reason": self.reason,
            "attempts_used": self.attempts_used,
            "escalate": self.escalate,
        }


class RecoveryHandler:
    """
    Stateless dispatcher. Inject ``registry`` / ``tracker`` / ``mistake_memory``
    in tests; defaults wire to the singletons.
    """

    def __init__(
        self,
        *,
        registry: AgentRegistry | None = None,
        tracker: AgentActivityTracker | None = None,
        mistake_memory: MistakeMemory | None = None,
        clock: callable | None = None,
    ) -> None:
        self.registry = registry or AgentRegistry()
        self.tracker = tracker or get_activity_tracker()
        self.mistake_memory = mistake_memory or get_mistake_memory()
        self._clock = clock or time.time

    def attempt(self, agent: SubAgent, diagnosis: Diagnosis) -> RecoveryResult:
        """
        Apply the strategy that matches ``diagnosis.cause_class`` (or the most
        recent known-good strategy for the same fingerprint, when available).
        Always records the attempt to mistake memory + tracker; never raises.
        """
        s = get_settings()
        max_attempts = max(
            1, int(getattr(s, "nexa_agent_max_auto_recovery_attempts", 3) or 3)
        )

        # No failures? nothing to do.
        if diagnosis.cause_class == CAUSE_NO_FAILURES:
            return self._record_and_return(
                agent,
                diagnosis,
                strategy=STRATEGY_NONE,
                succeeded=True,
                reason="no_recent_failures",
                attempts_used=int((agent.metadata or {}).get("recovery_attempts", 0) or 0),
                escalate=False,
            )

        prior_attempts = int((agent.metadata or {}).get("recovery_attempts", 0) or 0)
        if prior_attempts >= max_attempts:
            return self._record_and_return(
                agent,
                diagnosis,
                strategy=STRATEGY_CAPPED,
                succeeded=False,
                reason=(
                    f"recovery_attempts_exhausted ({prior_attempts}/{max_attempts}); "
                    "escalating"
                ),
                attempts_used=prior_attempts,
                escalate=True,
            )

        # Prefer a known-good strategy if mistake memory has one for this fingerprint.
        preferred = (
            self.mistake_memory.successful_strategy_for(diagnosis.fingerprint or "")
            if diagnosis.fingerprint
            else None
        )
        if preferred and preferred not in {STRATEGY_NONE, STRATEGY_CAPPED}:
            strategy = preferred
        else:
            strategy = self._strategy_for(diagnosis.cause_class)

        succeeded, reason = self._apply(agent, strategy, diagnosis)
        new_attempts = prior_attempts + 1
        self._patch_recovery_metadata(agent, attempts=new_attempts, last_strategy=strategy)
        escalate = (not succeeded) or new_attempts >= max_attempts

        return self._record_and_return(
            agent,
            diagnosis,
            strategy=strategy,
            succeeded=succeeded,
            reason=reason,
            attempts_used=new_attempts,
            escalate=escalate,
        )

    def reset_recovery_attempts(self, agent_id: str) -> None:
        """Called externally (e.g. from health API or after a successful task)."""
        agent = self.registry.get_agent(agent_id)
        if not agent:
            return
        if not (agent.metadata or {}).get("recovery_attempts"):
            return
        # ``patch_agent`` only merges keys (no delete semantics), so mutate the
        # registry-owned dict directly and then nudge the registry so the row
        # is persisted. The registry returns the same SubAgent instance from
        # ``get_agent`` that it stores in ``_agents``.
        if agent.metadata:
            agent.metadata.pop("recovery_attempts", None)
            agent.metadata.pop("last_recovery_strategy", None)
            agent.metadata.pop("last_recovery_at", None)
        self.registry.touch_agent(agent_id)

    def _strategy_for(self, cause_class: str) -> str:
        if cause_class == CAUSE_STATE_CORRUPTED:
            return STRATEGY_STATE_RESET
        if cause_class == CAUSE_REPEATED_LLM_ERROR:
            return STRATEGY_LLM_FALLBACK
        if cause_class == CAUSE_TRANSIENT:
            return STRATEGY_STATE_RESET
        if cause_class == CAUSE_UNKNOWN:
            return STRATEGY_STATE_RESET
        return STRATEGY_NONE

    def _apply(
        self, agent: SubAgent, strategy: str, diagnosis: Diagnosis
    ) -> tuple[bool, str]:
        try:
            if strategy == STRATEGY_STATE_RESET:
                changed = self._state_reset(agent)
                return True, ("state_reset_applied" if changed else "state_already_clean")
            if strategy == STRATEGY_LLM_FALLBACK:
                fallback_provider = self._enable_llm_fallback(agent)
                return True, f"llm_fallback_enabled:{fallback_provider}"
            if strategy == STRATEGY_PAUSE:
                self.registry.update_status(agent.id, AgentStatus.PAUSED)
                return True, "agent_paused"
            return False, f"no_strategy_for_cause:{diagnosis.cause_class}"
        except Exception as exc:  # noqa: BLE001
            logger.warning(
                "recovery strategy %s failed for agent %s: %s",
                strategy,
                agent.id,
                exc,
            )
            return False, f"strategy_error:{type(exc).__name__}:{exc}"

    def _state_reset(self, agent: SubAgent) -> bool:
        """BUSY → IDLE; clear current_task in metadata.

        ``patch_agent`` only merges keys (no delete semantics), so to actually
        remove ``current_task`` we mutate the registry-owned dict directly. The
        registry returns the same :class:`SubAgent` instance from ``get_agent``
        that it stores internally, so the mutation is visible everywhere.
        """
        changed = False
        if agent.status in (AgentStatus.BUSY, AgentStatus.ERROR):
            self.registry.update_status(agent.id, AgentStatus.IDLE)
            changed = True
        if agent.metadata and agent.metadata.get("current_task"):
            agent.metadata.pop("current_task", None)
            # Trigger a registry write so the change is persisted.
            self.registry.touch_agent(agent.id)
            changed = True
        return changed

    def _enable_llm_fallback(self, agent: SubAgent) -> str:
        """
        Mark the agent for a temporary fallback provider. Read by future
        ``primary_complete_messages`` call sites that opt-in to per-agent
        overrides; until then, the flag is informational and visible on the
        health endpoint.
        """
        s = get_settings()
        fallback = (
            getattr(s, "nexa_cost_aware_fallback_provider", "") or "ollama"
        ).strip()
        md = dict(agent.metadata or {})
        md["fallback_llm"] = fallback
        md["fallback_llm_set_at"] = self._clock()
        self.registry.patch_agent(agent.id, metadata_patch=md)
        # State reset on top so the agent isn't wedged BUSY behind a dead provider.
        self._state_reset(agent)
        return fallback

    def _patch_recovery_metadata(
        self, agent: SubAgent, *, attempts: int, last_strategy: str
    ) -> None:
        md = dict(agent.metadata or {})
        md["recovery_attempts"] = int(attempts)
        md["last_recovery_strategy"] = last_strategy
        md["last_recovery_at"] = self._clock()
        self.registry.patch_agent(agent.id, metadata_patch=md)

    def _record_and_return(
        self,
        agent: SubAgent,
        diagnosis: Diagnosis,
        *,
        strategy: str,
        succeeded: bool,
        reason: str,
        attempts_used: int,
        escalate: bool,
    ) -> RecoveryResult:
        # Audit log into the existing tracker so the CEO dashboard surfaces it.
        try:
            self.tracker.log_action(
                agent_id=agent.id,
                agent_name=agent.name,
                action_type="self_heal_recovery",
                input_data={
                    "cause_class": diagnosis.cause_class,
                    "fingerprint": diagnosis.fingerprint,
                    "error_count": diagnosis.error_count,
                },
                output_data={
                    "strategy": strategy,
                    "succeeded": succeeded,
                    "attempts_used": attempts_used,
                    "escalate": escalate,
                },
                success=succeeded,
                error=None if succeeded else reason[:500],
                metadata={
                    "phase": "73",
                    "self_healing": True,
                    "domain": agent.domain,
                },
            )
        except Exception:  # noqa: BLE001
            logger.debug("recovery tracker log suppressed", exc_info=True)

        # Record into mistake memory so future runs can pick the same strategy.
        try:
            self.mistake_memory.record_mistake(
                agent_id=agent.id,
                error=(diagnosis.top_errors[0]["error"] if diagnosis.top_errors else diagnosis.summary),
                cause_class=diagnosis.cause_class,
                recovery_strategy=strategy,
                recovery_succeeded=succeeded,
                context={
                    "summary": diagnosis.summary,
                    "fingerprint": diagnosis.fingerprint,
                    "attempts_used": attempts_used,
                },
            )
        except Exception:  # noqa: BLE001
            logger.debug("recovery mistake-memory write suppressed", exc_info=True)

        result = RecoveryResult(
            agent_id=agent.id,
            cause_class=diagnosis.cause_class,
            strategy=strategy,
            succeeded=succeeded,
            reason=reason,
            attempts_used=attempts_used,
            escalate=escalate,
        )
        logger.info(
            "recovery agent=%s cause=%s strategy=%s succeeded=%s attempts=%s escalate=%s",
            agent.id,
            diagnosis.cause_class,
            strategy,
            succeeded,
            attempts_used,
            escalate,
        )
        return result


_recovery_handler: RecoveryHandler | None = None


def get_recovery_handler() -> RecoveryHandler:
    global _recovery_handler
    if _recovery_handler is None:
        _recovery_handler = RecoveryHandler()
    return _recovery_handler


__all__ = [
    "STRATEGY_CAPPED",
    "STRATEGY_LLM_FALLBACK",
    "STRATEGY_NONE",
    "STRATEGY_PAUSE",
    "STRATEGY_STATE_RESET",
    "RecoveryHandler",
    "RecoveryResult",
    "get_recovery_handler",
]
