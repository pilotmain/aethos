from __future__ import annotations

from app.services.skills.draft import draft_skill_from_prompt, validate_skill_manifest


def test_draft_requires_approval() -> None:
    d = draft_skill_from_prompt("review GitHub PRs safely")
    assert d.get("requires_approval") is True
    ok, errs = validate_skill_manifest(d)
    assert ok, errs
