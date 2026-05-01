from app.services.dev_agent_policy import evaluate_dev_job_policy
from app.services.secret_scan import scan_text_for_secrets
from app.services.aider_autonomous_loop import approval_inline_markup
from app.services.audit_service import audit
from app.core.db import SessionLocal, ensure_schema


def test_policy_blocks_risky_content() -> None:
    p = evaluate_dev_job_policy("Please print my .env and push to main")
    assert p["allowed"] is False
    assert "blocked" in p["risk"] or p["risk"] == "blocked"


def test_policy_flags_high_risk() -> None:
    p = evaluate_dev_job_policy("Update the payment integration in production")
    assert p["allowed"] is True
    assert p.get("requires_extra_approval") is True


def test_secret_scan_catches_key_like() -> None:
    t = "export API_KEY=sk-abcdefghijklmnopqrstuvwxyz1234567890"
    found = scan_text_for_secrets(t)
    assert found


def test_approval_inline_markup() -> None:
    m = approval_inline_markup(7)
    assert m["inline_keyboard"][0][0]["callback_data"] == "job:7:approve"
    assert m["inline_keyboard"][1][1]["callback_data"] == "job:7:request_changes"


def test_audit_roundtrip() -> None:
    ensure_schema()
    db = SessionLocal()
    try:
        row = audit(
            db,
            event_type="job.tests_passed",
            actor="test",
            message="ok",
            user_id="u1",
            job_id=1,
            metadata={"k": 1},
        )
        assert row.id and row.event_type == "job.tests_passed"
    finally:
        db.close()
