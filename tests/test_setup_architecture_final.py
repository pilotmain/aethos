# SPDX-License-Identifier: Apache-2.0

from app.services.setup.setup_flow_convergence import build_setup_flow_convergence
from app.services.setup.setup_path_certification import certify_one_curl_path


def test_setup_architecture_final() -> None:
    conv = build_setup_flow_convergence()["setup_flow_convergence"]
    assert "aethos setup" in conv["entrypoints"][2]
    cert = certify_one_curl_path()
    assert cert.get("enterprise_default") is True
