# SPDX-License-Identifier: Apache-2.0

from __future__ import annotations

from aethos_cli.setup_secrets import mask_secret


def test_e2e_mask_secret() -> None:
    assert "full-secret-value" not in mask_secret("full-secret-value-here")
