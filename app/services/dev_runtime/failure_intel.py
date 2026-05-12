# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2025 AethOS AI

"""Phase 44–45 — classify dev run outcomes and suggest remediation strategies."""

from __future__ import annotations


def refine_dev_failure_detail(test_summary: str | None, error_text: str | None) -> str:
    """Narrow ``test_failure`` into build vs test signals for adaptive fixes (Phase 45C)."""
    blob = f"{test_summary or ''} {error_text or ''}".lower()
    build_markers = (
        "typescript error",
        "cannot find module",
        "npm err",
        "compilation",
        "syntaxerror",
        "esbuild",
        "webpack",
        "build failed",
        "tsc ",
        "cargo build",
        "go build",
    )
    if any(m in blob for m in build_markers):
        return "build_error"
    return "test_error"


def adaptive_next_goal(
    mission_goal: str,
    _current_goal: str,
    detail: str,
    test_summary: str,
    *,
    memory_notes: str | None = None,
) -> str:
    """Pivot instruction text when tests fail (Phase 45C). Memory steers fix focus (Phase 55)."""
    ts = (test_summary or "").strip()
    mem = (memory_notes or "").lower()
    mg = (mission_goal or "").lower()
    authish = any(
        k in mem or k in mg
        for k in (
            "oidc",
            "oauth",
            "irsa",
            "iam",
            "auth",
            "token",
            "401",
            "403",
            "unauthorized",
        )
    )
    dataish = any(k in mem or k in mg for k in ("mongo", "mongodb", "spring", "datasource"))
    k8s = any(k in mem or k in mg for k in ("eks", "kubernetes", "k8s", "pod", "serviceaccount"))

    if detail != "build_error" and (authish or (k8s and dataish)):
        return (
            f"Focus on identity + data path (IRSA/OIDC, service account, Mongo/Spring config) using this signal: {ts[:1200]}"
        )
    if detail == "build_error":
        return f"Fix build/compile errors before re-running tests: {ts[:1400]}"
    return f"Fix failing tests: {ts[:1200]}"


def detect_stagnation_signal(sig: str, prev_sig: str | None, count: int) -> tuple[bool, int, str | None]:
    """Stop when the same failure summary repeats without progress (Phase 45C)."""
    s = (sig or "").strip()
    if not s:
        return False, count, prev_sig
    if prev_sig is not None and s == prev_sig:
        count += 1
    else:
        count = 0
    return (count >= 2, count, s)


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


def select_fix_strategy_detail(detail: str) -> str:
    """Phase 45C — strategy keyed off :func:`refine_dev_failure_detail` output."""
    return {
        "build_error": "apply_build_fix_strategy",
        "test_error": "apply_test_fix_strategy",
    }.get(detail, "iterate_fix_loop_with_focused_tests")


__all__ = [
    "adaptive_next_goal",
    "classify_dev_failure",
    "detect_stagnation_signal",
    "refine_dev_failure_detail",
    "select_fix_strategy",
    "select_fix_strategy_detail",
]
