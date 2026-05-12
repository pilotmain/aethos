# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2025 AethOS AI

"""Workspace root registration aligns with unified owner gates (AETHOS_OWNER_IDS)."""

from __future__ import annotations

from unittest.mock import patch

import pytest
from fastapi import HTTPException

from app.services.user_capabilities import require_personal_workspace_mutation_allowed


def test_telegram_guest_allowed_when_in_aethos_owner_ids(db_session) -> None:
    uid = "tg_9000000000001"

    class S:
        aethos_owner_ids = uid

    with (
        patch("app.core.config.get_settings", return_value=S()),
        patch(
            "app.services.user_capabilities.get_telegram_role_for_app_user",
            return_value="guest",
        ),
    ):
        require_personal_workspace_mutation_allowed(db_session, uid)


def test_telegram_guest_blocked_without_aethos_or_trust(db_session) -> None:
    uid = "tg_9000000000002"

    class S:
        aethos_owner_ids = ""

    with (
        patch("app.core.config.get_settings", return_value=S()),
        patch(
            "app.services.user_capabilities.get_telegram_role_for_app_user",
            return_value="guest",
        ),
    ):
        with pytest.raises(HTTPException) as ei:
            require_personal_workspace_mutation_allowed(db_session, uid)
        assert ei.value.status_code == 403


def test_web_shaped_user_skips_telegram_gate(db_session) -> None:
    with patch(
        "app.services.user_capabilities.get_telegram_role_for_app_user",
        side_effect=AssertionError("should not check telegram role for web ids"),
    ):
        require_personal_workspace_mutation_allowed(db_session, "web_someone_abc")
