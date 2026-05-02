"""Phase 51D — only approved modules may import legacy_behavior_utils directly."""

from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def test_no_new_legacy_behavior_imports_outside_allowlist() -> None:
    needle = "from app.services.legacy_behavior_utils import"
    allowed = {
        ROOT / "app/services/legacy_behavior_utils.py",
        ROOT / "app/services/response_engine.py",
        ROOT / "app/services/response_composer.py",
        ROOT / "app/bot/telegram_bot.py",
        ROOT / "app/services/agent_orchestrator.py",
        ROOT / "app/services/gateway/runtime.py",
    }
    bad: list[str] = []
    for p in sorted(ROOT.glob("app/**/*.py")):
        if not p.is_file():
            continue
        if needle not in p.read_text(encoding="utf-8", errors="replace"):
            continue
        if p.resolve() not in allowed:
            bad.append(str(p.relative_to(ROOT)))
    assert not bad, f"Disallowed legacy_behavior_utils imports in: {bad}"
