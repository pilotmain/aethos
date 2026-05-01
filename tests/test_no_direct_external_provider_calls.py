"""Ensure third-party SDK usage stays confined to ``app/services/providers/``."""

from __future__ import annotations

from pathlib import Path

_REPO_ROOT = Path(__file__).resolve().parents[1]
_APP = (_REPO_ROOT / "app").resolve()
_PROVIDERS = (_APP / "services" / "providers").resolve()

_FORBIDDEN_LINE_MARKERS = (
    "import openai",
    "from openai ",
    "from openai.",
    "import anthropic",
    "from anthropic ",
    "from anthropic.",
)


def _iter_py_outside_providers() -> list[Path]:
    out: list[Path] = []
    for p in _APP.rglob("*.py"):
        if "__pycache__" in p.parts:
            continue
        try:
            p.resolve().relative_to(_PROVIDERS)
        except ValueError:
            out.append(p)
        else:
            continue
    return out


def test_no_openai_or_anthropic_imports_outside_providers_package() -> None:
    bad: list[str] = []
    for path in _iter_py_outside_providers():
        text = path.read_text(encoding="utf-8", errors="replace")
        for i, line in enumerate(text.splitlines(), start=1):
            if line.strip().startswith("#"):
                continue
            if "app.services.providers.sdk" in line:
                continue
            low = line.lower()
            if any(m in low for m in _FORBIDDEN_LINE_MARKERS):
                bad.append(f"{path.relative_to(_REPO_ROOT)}:{i}:{line.strip()}")
    assert not bad, "Forbidden provider imports outside app/services/providers:\n" + "\n".join(bad)
