"""Phase 32 — legacy Telegram slash handlers removed; no stray legacy path hints outside HTTP routes."""

from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def _iter_app_py_excluding_api() -> list[Path]:
    out: list[Path] = []
    app_root = ROOT / "app"
    skip_top = frozenset({"api", "channels", "cli"})
    for p in app_root.rglob("*.py"):
        parts = p.parts
        if "app" not in parts:
            continue
        i = parts.index("app")
        if len(parts) > i + 1 and parts[i + 1] in skip_top:
            continue
        out.append(p)
    return sorted(out)


def test_legacy_handler_symbols_removed() -> None:
    bad_syms = ("jobs_cmd", "context_cmd", "job_cmd")
    problems: list[str] = []
    for path in _iter_app_py_excluding_api():
        text = path.read_text(encoding="utf-8", errors="replace")
        rel = path.relative_to(ROOT)
        for s in bad_syms:
            if s in text:
                problems.append(f"{rel}: contains {s!r}")
    assert not problems, "\n".join(problems)


def test_no_legacy_slash_jobs_or_context_outside_app_api() -> None:
    """REST routers under app/api keep path segments like `/jobs`; intent UX must not."""
    problems: list[str] = []
    for path in _iter_app_py_excluding_api():
        text = path.read_text(encoding="utf-8", errors="replace")
        rel = path.relative_to(ROOT)
        if "/jobs" in text:
            problems.append(f"{rel}: contains '/jobs'")
        if "/context" in text:
            problems.append(f"{rel}: contains '/context'")
    assert not problems, "\n".join(problems)


def test_telegram_adapter_has_no_legacy_command_handlers() -> None:
    text = (ROOT / "app/services/channel_gateway/telegram_adapter.py").read_text(encoding="utf-8")
    assert 'CommandHandler("jobs"' not in text
    assert 'CommandHandler("job"' not in text
    assert 'CommandHandler("context"' not in text
