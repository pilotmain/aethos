# SPDX-License-Identifier: Apache-2.0

from __future__ import annotations

from app.services.setup.setup_path_certification import certify_one_curl_path


def test_one_curl_enterprise_path_certified() -> None:
    out = certify_one_curl_path()
    assert out["certified"] is True
    assert "scripts/setup.sh" in out["flow"][2]
