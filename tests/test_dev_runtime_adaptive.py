"""Phase 45C — adaptive failure typing, goals, and stagnation stopping."""

from __future__ import annotations

from app.services.dev_runtime.failure_intel import (
    adaptive_next_goal,
    detect_stagnation_signal,
    refine_dev_failure_detail,
    select_fix_strategy_detail,
)


def test_refine_build_error() -> None:
    d = refine_dev_failure_detail("npm ERR! compilation failed", None)
    assert d == "build_error"
    assert select_fix_strategy_detail(d) == "apply_build_fix_strategy"


def test_refine_test_error() -> None:
    d = refine_dev_failure_detail("AssertionError: expected 1 == 2", None)
    assert d == "test_error"


def test_adaptive_next_goal() -> None:
    g = adaptive_next_goal("ship", "old", "build_error", "tsc failed")
    assert "build" in g.lower() or "compile" in g.lower()


def test_stagnation_abort() -> None:
    abort, c1, p1 = detect_stagnation_signal("same", None, 0)
    assert abort is False and c1 == 0 and p1 == "same"
    abort2, c2, p2 = detect_stagnation_signal("same", p1, c1)
    assert abort2 is False and c2 == 1
    abort3, c3, _ = detect_stagnation_signal("same", p2, c2)
    assert abort3 is True and c3 == 2
