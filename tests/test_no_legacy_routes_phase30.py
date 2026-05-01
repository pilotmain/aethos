"""Phase 30 — legacy REST endpoints stay removed; web clients avoid deprecated paths."""

from __future__ import annotations

from pathlib import Path

from fastapi.testclient import TestClient

from app.main import app

ROOT = Path(__file__).resolve().parents[1]


def test_deprecated_alias_endpoints_still_absent() -> None:
    """Repeat critical Phase 27 surface + legacy memory route."""
    c = TestClient(app)
    h = {"X-User-Id": "phase30"}
    assert c.get("/api/v1/mission-control/summary", headers=h).status_code == 410
    assert c.get("/api/v1/agents", headers=h).status_code == 404
    assert c.get("/api/v1/memory", headers=h).status_code == 410


def test_web_sources_do_not_reference_deprecated_http_paths() -> None:
    """Frontend must use /mission-control/state, /custom-agents, /web/memory/*, not removed aliases."""
    needles = (
        "/api/v1/agents",
        "mission-control/summary",
        "/api/v1/memory",
    )
    hits: list[str] = []
    for p in (ROOT / "web").rglob("*"):
        if (
            not p.is_file()
            or "node_modules" in p.parts
            or ".next" in p.parts
            or p.suffix not in (".ts", ".tsx", ".js", ".jsx")
        ):
            continue
        text = p.read_text(encoding="utf-8", errors="replace")
        for n in needles:
            if n in text:
                hits.append(f"{p.relative_to(ROOT)}: {n}")
    assert not hits, "\n".join(hits)
