from app.services.ops_actions import get_action
from app.services.ops_executor import MAX_OUT, sanitize_log_text, execute_action
from app.services.ops_router import parse_ops_command


def test_parse_deploy_staging() -> None:
    r = parse_ops_command("deploy staging", known_project_keys=[])
    assert r["action"] == "deploy_staging"
    r2 = parse_ops_command(
        "deploy nexa staging", known_project_keys=["nexa", "client-dashboard"]
    )
    assert r2["action"] == "deploy_staging"
    assert (r2.get("payload") or {}).get("project_key") == "nexa"


def test_parse_deploy_production() -> None:
    assert (
        parse_ops_command("deploy production", known_project_keys=[])["action"]
        == "deploy_production"
    )
    assert (
        parse_ops_command("deploy prod", known_project_keys=[])["action"] == "deploy_production"
    )


def test_parse_status_and_health() -> None:
    st = parse_ops_command("status nexa", known_project_keys=["nexa"])
    assert st["action"] == "status"
    h = parse_ops_command("health", known_project_keys=[])
    assert h["action"] == "health"
    ws = parse_ops_command("worker status", known_project_keys=[])
    assert ws["action"] == "health"


def test_parse_logs_api() -> None:
    r = parse_ops_command("logs api", known_project_keys=[])
    assert r["action"] == "logs"
    assert r["payload"].get("service") == "api"
    r2 = parse_ops_command(
        "logs nexa api", known_project_keys=["nexa"]
    )
    assert r2["action"] == "logs"
    assert (r2.get("payload") or {}).get("project_key") == "nexa"
    assert (r2.get("payload") or {}).get("service") == "api"


def test_approval_production() -> None:
    assert get_action("deploy_production") is not None
    assert get_action("deploy_production").requires_approval is True


def test_approval_staging() -> None:
    assert get_action("deploy_staging") is not None
    assert get_action("deploy_staging").requires_approval is True


def test_sanitize_truncate() -> None:
    s = "x" * 3000
    t = sanitize_log_text(s, max_len=200)
    assert len(t) <= 200
    t2 = sanitize_log_text("ok sk-test1234567890abcdef " * 5)
    assert "sk-" not in t2 or "[token]" in t2


def test_safe_actions_no_approval() -> None:
    for a in ("health", "status", "queue", "jobs", "logs"):
        assert not get_action(a).requires_approval


def test_logs_truncation_bound() -> None:
    o = execute_action("logs", {"service": "api"}, db=None, app_user_id=None)
    if len(o) > 0 and "Nexa" in o:  # expected message in dry env
        assert len(o) <= 8000
    # Max helper constant
    assert MAX_OUT == 1000


def test_unknown_not_in_ops_dict() -> None:
    o = execute_action("totally_missing", {}, db=None, app_user_id=None)
    assert "allowlist" in o
