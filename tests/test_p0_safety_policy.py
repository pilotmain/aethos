# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2025 AethOS AI

"""P0 structural safety: immutable policy, provenance, egress gates, permissions."""

from __future__ import annotations

import uuid
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

import pytest

from app.core.db import SessionLocal, ensure_schema
from app.services import access_permissions as ap
from app.services.content_provenance import InstructionSource
from app.services.nexa_safety_policy import (
    POLICY_SHA256,
    POLICY_TEXT,
    POLICY_VERSION,
    POLICY_VERSION_INT,
    stamp_host_payload,
    verify_payload_policy,
)
from app.services.nexa_policy_guard import enforce_nexa_privileged_policy
from app.services.secret_egress_gate import (
    assert_safe_for_external_send,
    looks_like_secret_material,
)
from app.services import host_executor


def test_immutable_policy_version_and_hash_stable() -> None:
    assert POLICY_VERSION
    assert len(POLICY_SHA256) == 64
    assert "privileged execution" in POLICY_TEXT.lower() or "nexa" in POLICY_TEXT.lower()


def test_stamp_preserves_explicit_version_for_drift_detection() -> None:
    stamped = stamp_host_payload(
        {"nexa_safety_policy_version": "legacy.x", "nexa_safety_policy_sha256": "deadbeef"}
    )
    assert stamped["nexa_safety_policy_version"] == "legacy.x"
    ok, detail = verify_payload_policy(stamped)
    assert ok is False
    assert "mismatch" in detail.lower()


def test_verify_passes_when_current_version_stamped() -> None:
    p = stamp_host_payload({"host_action": "git_status"})
    ok, detail = verify_payload_policy(p)
    assert ok is True
    assert detail == ""
    assert p.get("nexa_safety_policy_version_int") == POLICY_VERSION_INT


def test_policy_version_int_downgrade_rejected() -> None:
    p = {
        "host_action": "git_status",
        "nexa_safety_policy_version": POLICY_VERSION,
        "nexa_safety_policy_sha256": POLICY_SHA256,
        "nexa_safety_policy_version_int": max(0, POLICY_VERSION_INT - 1),
    }
    ok, detail = verify_payload_policy(p)
    assert ok is False
    assert "downgrade" in detail.lower()


def test_guard_overwrites_untrusted_instruction_source_at_boundary() -> None:
    raw = {"host_action": "git_status", "instruction_source": InstructionSource.UPLOADED_FILE.value}
    out = enforce_nexa_privileged_policy(
        raw,
        trusted_instruction_source=InstructionSource.USER_MESSAGE.value,
        boundary="unit_test",
    )
    assert out["instruction_source"] == InstructionSource.USER_MESSAGE.value


def test_chained_prompt_injection_blocked_before_sensitive_path() -> None:
    """Untrusted provenance cannot start host chain (no .env read / exfil step)."""
    job = MagicMock()
    job.user_id = None

    class HS:
        nexa_host_executor_enabled = True

    with patch.object(host_executor, "_host_settings", lambda: HS()):
        with pytest.raises(ValueError, match="untrusted"):
            host_executor.execute_payload(
                {
                    "host_action": "file_read",
                    "relative_path": ".env",
                    "instruction_source": InstructionSource.UPLOADED_FILE.value,
                },
                db=None,
                job=None,
            )


def test_untrusted_source_blocks_privileged_host_action() -> None:
    job = MagicMock()
    job.user_id = None

    class HS:
        nexa_host_executor_enabled = True

    with patch.object(host_executor, "_host_settings", lambda: HS()):
        with pytest.raises(ValueError, match="untrusted"):
            host_executor.execute_payload(
                {
                    "host_action": "git_status",
                    "instruction_source": InstructionSource.UPLOADED_FILE.value,
                },
                db=None,
                job=None,
            )


def test_secret_material_detection() -> None:
    assert looks_like_secret_material("-----BEGIN RSA PRIVATE KEY-----\n MII")
    assert looks_like_secret_material("API_KEY=abcdefghijklmnop")


def test_secret_external_send_blocked_without_explicit_allow() -> None:
    with pytest.raises(ValueError, match="Refusing|approval"):
        assert_safe_for_external_send(
            "-----BEGIN OPENSSH PRIVATE KEY-----",
            allow_when=False,
            detail="Refusing outbound POST",
        )


@pytest.mark.parametrize(
    "grant,host,expect",
    [
        ("example.com", "example.com", True),
        ("example.com", "api.example.com", True),
        ("*.example.com", "api.example.com", True),
        ("other.com", "example.com", False),
    ],
)
def test_hostname_grants_match(grant: str, host: str, expect: bool) -> None:
    assert ap.hostname_covers_external_send_target(grant, host) is expect


def test_fetch_url_blocked_without_external_send_grant_when_enforced(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.chdir(tmp_path)
    ensure_schema()
    db = SessionLocal()
    try:
        uid = f"egress_gate_{uuid.uuid4().hex[:16]}"
        settings = SimpleNamespace(
            nexa_web_access_enabled=True,
            nexa_web_fetch_timeout_seconds=15,
            nexa_web_max_bytes=500_000,
            nexa_web_max_redirects=5,
            nexa_network_external_send_enforced=True,
            nexa_web_user_agent="test",
            safe_llm_max_chars=6000,
        )
        from app.services import web_access as wa

        monkeypatch.setattr(wa, "get_settings", lambda: settings)
        with patch.object(wa.httpx, "Client") as mock_http:
            fr = wa.fetch_url(
                "https://example.com/hello",
                allow_internal=False,
                respect_robots=False,
                db=db,
                owner_user_id=uid,
            )
            mock_http.assert_not_called()
        assert fr.error is not None
        assert "network_external_send" in (fr.error or "").lower()

        pend = ap.request_permission(
            db,
            uid,
            scope=ap.SCOPE_NETWORK_EXTERNAL_SEND,
            target="example.com",
            risk_level=ap.RISK_MEDIUM,
            reason="test egress",
        )
        ap.grant_permission(db, uid, pend.id, granted_by_user_id=uid)
        ok, _ = ap.check_network_external_send_permission(
            db, uid, hostname="example.com"
        )
        assert ok is True
    finally:
        db.close()


def test_one_time_grant_consumed_after_host_finalize(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    import subprocess

    monkeypatch.chdir(tmp_path)
    subprocess.run(["git", "init"], cwd=str(tmp_path), check=True, capture_output=True)
    ensure_schema()
    db = SessionLocal()
    try:
        uid = "once_grant_u"
        root = str(tmp_path.resolve())
        try:
            from app.services.workspace_registry import add_root

            add_root(db, uid, root)
        except ValueError:
            pass

        pend = ap.request_permission(
            db,
            uid,
            scope=ap.SCOPE_GIT_OPERATIONS,
            target=root,
            risk_level=ap.RISK_LOW,
            reason="once",
        )
        md = dict(pend.metadata_json or {})
        md["grant_mode"] = ap.GRANT_MODE_ONCE
        pend.metadata_json = md
        db.add(pend)
        db.commit()

        gr = ap.grant_permission(db, uid, pend.id, granted_by_user_id=uid)
        assert gr is not None

        job = MagicMock()
        job.user_id = uid

        class HE:
            nexa_host_executor_enabled = True
            nexa_access_permissions_enforced = True
            nexa_workspace_strict = False
            host_executor_work_root = root
            host_executor_timeout_seconds = 120
            host_executor_max_file_bytes = 262_144

        with patch.object(host_executor, "_host_settings", lambda: HE()):
            host_executor.execute_payload(
                {"host_action": "git_status"},
                db=db,
                job=job,
            )

        db.refresh(gr)
        assert gr.status == ap.STATUS_CONSUMED
    finally:
        db.close()


def test_revoked_grant_cannot_be_reused(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    import subprocess

    monkeypatch.chdir(tmp_path)
    subprocess.run(["git", "init"], cwd=str(tmp_path), check=True, capture_output=True)
    ensure_schema()
    db = SessionLocal()
    try:
        uid = "revoke_u"
        root = str(tmp_path.resolve())
        try:
            from app.services.workspace_registry import add_root

            add_root(db, uid, root)
        except ValueError:
            pass

        pend = ap.request_permission(
            db,
            uid,
            scope=ap.SCOPE_FILE_READ,
            target=root,
            risk_level=ap.RISK_LOW,
            reason="rev",
        )
        ap.grant_permission(db, uid, pend.id, granted_by_user_id=uid)
        ap.revoke_permission(db, uid, pend.id)

        job = MagicMock()
        job.user_id = uid

        class HE:
            nexa_host_executor_enabled = True
            nexa_access_permissions_enforced = True
            nexa_workspace_strict = False
            host_executor_work_root = root
            host_executor_timeout_seconds = 120
            host_executor_max_file_bytes = 262_144

        with patch.object(host_executor, "_host_settings", lambda: HE()):
            with pytest.raises(ValueError, match="permission|granted"):
                host_executor.execute_payload(
                    {"host_action": "git_status"},
                    db=db,
                    job=job,
                )
    finally:
        db.close()


def test_long_chat_summary_does_not_remove_policy_from_payload() -> None:
    """Regression: policy lives on payload dicts, not in rolling chat JSON."""
    huge_summary = "x" * 50_000
    p = stamp_host_payload({"host_action": "run_command", "run_name": "pytest"})
    p["_simulated_context_summary_only"] = huge_summary
    ok, _ = verify_payload_policy(p)
    assert ok is True
    assert p["nexa_safety_policy_version"] == POLICY_VERSION
    assert p.get("nexa_safety_policy_version_int") == POLICY_VERSION_INT
