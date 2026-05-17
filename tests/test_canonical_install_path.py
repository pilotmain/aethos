# SPDX-License-Identifier: Apache-2.0

from app.services.setup.canonical_install_path import PUBLIC_INSTALL_COMMAND, build_canonical_install_path


def test_canonical_install_path_locked() -> None:
    out = build_canonical_install_path()
    path = out["canonical_install_path"]
    assert "install.sh" in path["canonical_flow"][0]
    assert "aethos setup" in path["canonical_flow"][2]
    assert path.get("locked") is True
    assert "curl" in PUBLIC_INSTALL_COMMAND
