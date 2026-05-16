# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2025 AethOS AI

import pytest

from app.plugins.plugin_installer import validate_manifest_for_install


def test_untrusted_requires_permissions() -> None:
    with pytest.raises(ValueError, match="permissions"):
        validate_manifest_for_install({"plugin_id": "x", "trust_tier": "community", "permissions": []})


def test_trusted_with_permissions_ok() -> None:
    validate_manifest_for_install(
        {"plugin_id": "x", "trust_tier": "community", "permissions": ["provider.test"]}
    )
