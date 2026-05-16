# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2025 AethOS AI

"""Brain-routed structured repair planning (Phase 2 Step 7)."""

from __future__ import annotations

import json
import os
from typing import Any

from app.brain.brain_capabilities import brain_is_local
from app.brain.brain_events import record_brain_decision
from app.brain.brain_selection import brain_allows_external_call, select_brain_for_task
from app.core.config import get_settings
from app.privacy.egress_guard import EgressBlocked
from app.privacy.llm_privacy_gate import apply_llm_privacy_gate, evaluate_text_egress
from app.privacy.privacy_modes import PrivacyMode
from app.privacy.privacy_policy import current_privacy_mode
from app.providers.repair.repair_plan_validation import validate_repair_plan
from app.services.llm.base import Message


def _evidence_blob(evidence: dict[str, Any]) -> str:
    return json.dumps(
        {
            "failure_category": evidence.get("failure_category"),
            "logs_summary": evidence.get("logs_summary"),
            "package_scripts": evidence.get("package_scripts"),
            "workspace_files": (evidence.get("workspace_files") or [])[:20],
        },
        ensure_ascii=False,
    )[:12_000]


def _deterministic_brain_plan(evidence: dict[str, Any]) -> dict[str, Any]:
    category = str(evidence.get("failure_category") or "unknown")
    scripts = evidence.get("package_scripts") if isinstance(evidence.get("package_scripts"), dict) else {}
    steps: list[dict[str, Any]] = [{"type": "inspect", "path": "package.json"}]
    if category in ("dependency_failure", "build_failure"):
        steps.append({"type": "shell", "command": "npm install"})
    verify_cmd = None
    for name in ("test", "build", "lint"):
        if name in scripts:
            verify_cmd = f"npm run {name}"
            break
    if verify_cmd:
        steps.append({"type": "verify", "command": verify_cmd})
    elif scripts:
        steps.append({"type": "verify", "command": "npm run build"})
    diagnosis = {
        "build_failure": "Build failed — run install and rebuild.",
        "dependency_failure": "Dependency issue — reinstall packages.",
        "test_failure": "Tests failed — inspect failing tests.",
        "lint_failure": "Lint errors — fix static analysis issues.",
    }.get(category, f"Repair plan for {category}")
    return {
        "diagnosis": diagnosis,
        "confidence": 0.78 if category not in ("unknown",) else 0.52,
        "steps": steps,
        "redeploy_after_verify": True,
        "planner": "brain_deterministic",
    }


def _should_escalate_to_brain(evidence: dict[str, Any], diagnosis: dict[str, Any] | None) -> bool:
    if (os.environ.get("FORCE_REPAIR_BRAIN") or "").strip() in ("1", "true", "yes"):
        return True
    diag = diagnosis or {}
    if diag.get("needs_workspace_edit"):
        return True
    cat = str(evidence.get("failure_category") or diag.get("failure_category") or "")
    if cat in ("unknown", "deployment_failure", "runtime_error", "environment_variable_missing"):
        return True
    try:
        conf = float(diag.get("confidence") or 0)
    except (TypeError, ValueError):
        conf = 0
    return conf < 0.65


def _call_external_brain(
    *,
    provider: str,
    model: str,
    evidence: dict[str, Any],
) -> dict[str, Any] | None:
    from app.services.providers.gateway import call_provider
    from app.services.providers.types import ProviderRequest

    prompt = (
        "Return ONLY JSON for a repair plan with keys: diagnosis, confidence (0-1), "
        "steps (inspect|edit|verify|shell), redeploy_after_verify (bool). "
        f"Evidence: {_evidence_blob(evidence)}"
    )
    messages = [Message(role="user", content=prompt)]
    try:
        gated, privacy_meta = apply_llm_privacy_gate(messages, provider_name=provider, model_id=model)
    except EgressBlocked:
        return None
    payload = {
        "tool": "repair_plan",
        "task": "repair_plan",
        "inputs": [m.content if isinstance(m.content, str) else str(m.content) for m in gated],
        "model": model,
    }
    if provider == "deterministic":
        return _deterministic_brain_plan(evidence)
    try:
        resp = call_provider(
            ProviderRequest(
                user_id="repair",
                mission_id=None,
                agent_handle="repair",
                provider=provider,
                model=model,
                purpose="repair_plan",
                payload=payload,
            )
        )
    except Exception:
        return None
    raw = resp.output if hasattr(resp, "output") else resp
    if isinstance(raw, dict) and raw.get("repair_plan"):
        plan = raw["repair_plan"]
        return plan if isinstance(plan, dict) else None
    if isinstance(raw, dict) and raw.get("type") == "repair_plan":
        return raw
    return None


def request_repair_plan_from_brain(
    *,
    evidence: dict[str, Any],
    diagnosis: dict[str, Any] | None = None,
    repair_context_id: str | None = None,
    project_id: str | None = None,
) -> tuple[dict[str, Any] | None, dict[str, Any]]:
    """
    Ask selected brain for a structured repair plan.

    Returns ``(plan_or_none, brain_decision_record)``.
    """
    s = get_settings()
    blob = _evidence_blob(evidence)
    egress = evaluate_text_egress(blob, boundary="repair_brain")
    mode = current_privacy_mode(s)
    if mode in (PrivacyMode.BLOCK, PrivacyMode.LOCAL_ONLY) and not egress.get("allowed"):
        selection = select_brain_for_task("repair_plan", evidence_text=blob, force_deterministic=True)
    else:
        selection = select_brain_for_task("repair_plan", evidence_text=blob)

    provider = str(selection["selected_provider"])
    model = str(selection["selected_model"])
    if not brain_allows_external_call(selection) and not brain_is_local(provider):
        selection = select_brain_for_task("repair_plan", evidence_text=blob, force_deterministic=True)
        provider = "deterministic"
        model = "deterministic-repair-v1"
        selection["fallback_used"] = True
        selection["reason"] = "privacy_blocked_external_brain"

    decision = record_brain_decision(
        task="repair_plan",
        selected_provider=provider,
        selected_model=model,
        reason=str(selection.get("reason") or ""),
        local_first=bool(selection.get("local_first")),
        fallback_used=bool(selection.get("fallback_used")),
        privacy_meta={"egress_allowed": egress.get("allowed"), "redactions_applied": 0},
        repair_context_id=repair_context_id,
        project_id=project_id,
        fallback_chain=selection.get("fallback_chain"),
        cost_estimate=selection.get("cost_estimate"),
    )

    plan: dict[str, Any] | None = None
    if provider == "deterministic":
        plan = _deterministic_brain_plan(evidence)
    elif brain_is_local(provider):
        ext = _call_external_brain(provider=provider, model=model, evidence=evidence)
        plan = ext or _deterministic_brain_plan(evidence)
        if ext is None:
            decision["fallback_used"] = True
    elif mode == PrivacyMode.BLOCK and egress.get("pii_categories"):
        plan = _deterministic_brain_plan(evidence)
        decision["fallback_used"] = True
    else:
        ext = _call_external_brain(provider=provider, model=model, evidence=evidence)
        plan = ext or _deterministic_brain_plan(evidence)
        if ext is None:
            decision["fallback_used"] = True

    if plan is None:
        return None, decision

    repo = str(evidence.get("repo_path") or "")
    validation = validate_repair_plan(plan, repo_path=repo)
    if not validation.get("valid"):
        decision["plan_rejected"] = True
        decision["validation_errors"] = validation.get("errors")
        return None, decision

    plan["validation"] = validation
    plan["brain_decision_id"] = decision.get("brain_decision_id")
    return plan, decision


def needs_brain_escalation(evidence: dict[str, Any], diagnosis: dict[str, Any] | None = None) -> bool:
    return _should_escalate_to_brain(evidence, diagnosis)


__all__ = ["needs_brain_escalation", "request_repair_plan_from_brain"]
