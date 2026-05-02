"""Registry for coding-agent adapters (Phase 24)."""

from __future__ import annotations

from app.services.dev_runtime.coding_agents.aider_adapter import AiderCodingAgent
from app.services.dev_runtime.coding_agents.claude_code_adapter import ClaudeCodeAgent
from app.services.dev_runtime.coding_agents.codex_adapter import CodexCodingAgent
from app.services.dev_runtime.coding_agents.cursor_adapter import CursorCodingAgent
from app.services.dev_runtime.coding_agents.local_stub import LocalStubCodingAgent


def available_adapters():
    adapters = [
        LocalStubCodingAgent(),
        AiderCodingAgent(),
        CursorCodingAgent(),
        ClaudeCodeAgent(),
        CodexCodingAgent(),
    ]
    return [a for a in adapters if a.available()]


def choose_adapter(
    preferred: str | None = None,
    *,
    user_id: str | None = None,
    task_goal: str | None = None,
):
    adapters = available_adapters()

    if preferred:
        pref = str(preferred).strip().lower().replace("-", "_")
        if pref in ("claude", "claude_code_cli"):
            pref = "claude_code"
        for adapter in adapters:
            if adapter.name == pref:
                return adapter

    if user_id and task_goal and adapters:
        try:
            from app.services.agents.agent_intel_store import list_agent_intel_profiles
            from app.services.agents.agent_selection import select_best_agent
            from app.services.tasks.unified_task import NexaTask

            prof_by_handle = {str(p.get("handle") or "").lower(): p for p in list_agent_intel_profiles(user_id)}
            agents_list: list[dict] = []
            for ad in adapters:
                pid = ad.name.lower()
                meta = prof_by_handle.get(pid) or {}
                agents_list.append(
                    {
                        "handle": ad.name,
                        "performance_score": float(meta.get("performance_score") or 0.55),
                        "runs": int(meta.get("runs") or 0),
                        "specialization": meta.get("specialization")
                        if isinstance(meta.get("specialization"), list)
                        else [],
                    }
                )
            nt = NexaTask(
                id="adapter_pick",
                type="dev",
                input=(task_goal or "")[:50_000],
                context={},
                priority=0,
                origin="dev_runtime",
            )
            best = select_best_agent(nt, agents_list)
            if best:
                pick = str(best.get("handle") or "").strip()
                for adapter in adapters:
                    if adapter.name == pick:
                        return adapter
        except Exception:
            pass

    for name in ("cursor", "claude_code", "codex", "aider", "local_stub"):
        for adapter in adapters:
            if adapter.name == name:
                return adapter

    return LocalStubCodingAgent()


__all__ = ["available_adapters", "choose_adapter"]
