"""Phase 44 — classify dev run outcomes and suggest remediation strategies."""

from __future__ import annotations


def classify_dev_failure(
    *,
    error_text: str | None,
    tests_passed: bool,
    adapter_round_ok: bool,
    privacy_blocked: bool,
) -> str:
    if privacy_blocked:
        return "privacy_blocked"
    if not adapter_round_ok:
        return "adapter_error"
    if not tests_passed:
        return "test_failure"
    low = (error_text or "").lower()
    if "timeout" in low:
        return "timeout"
    return "none"


def select_fix_strategy(failure_class: str) -> str:
    return {
        "privacy_blocked": "relax_scope_or_privacy_gate",
        "adapter_error": "switch_adapter_or_reduce_goal",
        "test_failure": "iterate_fix_loop_with_focused_tests",
        "timeout": "narrow_iteration_budget_or_split_goal",
        "none": "pipeline_complete",
    }.get(failure_class, "manual_review")


__all__ = ["classify_dev_failure", "select_fix_strategy"]
