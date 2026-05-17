# SPDX-License-Identifier: Apache-2.0

from app.services.runtime.enterprise_operational_command_authority import build_enterprise_operational_command_authority


def test_runtime_command_authority_e2e() -> None:
    assert build_enterprise_operational_command_authority({})["enterprise_operational_command_integrity"]
