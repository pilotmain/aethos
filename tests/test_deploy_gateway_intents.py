"""Deploy gateway NL helpers: cancel, reset, available-clouds intent."""

from __future__ import annotations

from pathlib import Path

from app.services.gateway.deploy_nl import (
    format_cloud_choice_prompt,
    get_cloud_choices,
    install_instructions_text,
)
from app.services.host_executor_intent import (
    is_cancel_deploy_intent,
    is_reset_deploy_intent,
    parse_available_clouds_intent,
    parse_deploy_from_intent,
    parse_deploy_root_intent,
)


def test_cancel_deploy_intent() -> None:
    assert is_cancel_deploy_intent("cancel")
    assert is_cancel_deploy_intent("  STOP \n")
    assert is_cancel_deploy_intent("never mind")
    assert is_cancel_deploy_intent("cancel that")
    assert not is_cancel_deploy_intent("cancel my subscription")


def test_reset_deploy_intent() -> None:
    assert is_reset_deploy_intent("reset deploy")
    assert is_reset_deploy_intent("clear deploy state")
    assert not is_reset_deploy_intent("deploy")


def test_parse_available_clouds_intent() -> None:
    assert parse_available_clouds_intent("what clouds can I use?")
    assert parse_available_clouds_intent("where can I deploy")
    assert not parse_available_clouds_intent("deploy to vercel")
    assert not parse_available_clouds_intent("deploy")


def test_format_cloud_choice_prompt_nonempty(tmp_path: Path) -> None:
    text = format_cloud_choice_prompt(tmp_path)
    assert "Which cloud should deploy" in text or "No deployment tools" in text


def test_install_instructions_nonempty() -> None:
    assert "vercel" in install_instructions_text().lower()


def test_get_cloud_choices_shape(tmp_path: Path) -> None:
    rows = get_cloud_choices(tmp_path)
    assert isinstance(rows, list)
    for r in rows:
        assert "name" in r and "display" in r and "command" in r


def test_parse_deploy_from_intent() -> None:
    r = parse_deploy_from_intent("deploy from /tmp/foo")
    assert r is not None
    assert r.get("folder") == "/tmp/foo"
    assert parse_deploy_from_intent("deploy to vercel") is None


def test_parse_deploy_root_intent() -> None:
    r = parse_deploy_root_intent("change deploy root to /Users/me/app")
    assert r is not None
    assert "/Users/me/app" in (r.get("folder") or "")
    assert parse_deploy_root_intent("deploy") is None
