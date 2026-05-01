"""Phase 27 — no frontend references to deprecated Mission Control summary path."""

from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def test_web_sources_do_not_fetch_mission_control_summary() -> None:
    needle = "mission-control/summary"
    hits: list[str] = []
    for p in (ROOT / "web").rglob("*.ts*"):
        if "node_modules" in p.parts or p.suffix not in (".ts", ".tsx"):
            continue
        text = p.read_text(encoding="utf-8", errors="replace")
        if needle in text:
            hits.append(str(p.relative_to(ROOT)))
    assert not hits, f"Found {needle} in: {hits}"
