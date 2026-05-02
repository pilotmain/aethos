from app.services.mention_control import MENTION_ALIASES, parse_mention, map_catalog_key_to_internal
from app.services.agent_catalog import AGENTS
from app.services.agent_telegram_copy import format_command_center, format_agents_list


def test_parse_orchestrator_aliases_to_strategy() -> None:
    r = parse_mention("@orchestrator assign @research-analyst to plan Q3")
    assert r.is_explicit and not r.error
    assert r.agent_key == "strategy"
    assert r.text == "assign @research-analyst to plan Q3"


def test_parse_dev_and_cursor() -> None:
    r1 = parse_mention("@dev fix X")
    assert r1.is_explicit
    assert r1.agent_key == "dev"
    assert r1.text == "fix X"
    assert map_catalog_key_to_internal(r1.agent_key) == "developer"
    r2 = parse_mention("@cursor fix X")
    assert r2.agent_key == "dev"
    assert r2.text == "fix X"


def test_parse_unknown() -> None:
    u = parse_mention("@unknown test")
    assert u.is_explicit
    assert u.error
    assert u.raw_mention == "unknown"
    assert u.text == "test"


def test_agents_list_is_nexa_next_only() -> None:
    body = format_agents_list()
    assert "Nexa" in body
    assert "assistant" in body.lower() or "chat" in body.lower()
    assert "@dev" not in body
    assert "@ops" not in body


def test_command_center_format_nexa_next() -> None:
    cmd = format_command_center()
    assert "Nexa" in cmd
    assert "Command Center" not in cmd
    assert "@dev" not in cmd
    assert "Mission Control" in cmd or "workspace" in cmd.lower()


def test_catalog_matches_spec_keys() -> None:
    assert set(AGENTS) == {
        "reset",
        "dev",
        "qa",
        "ops",
        "strategy",
        "marketing",
        "research",
    }
    assert "cursor" in MENTION_ALIASES
    assert MENTION_ALIASES["cursor"] == "dev"
