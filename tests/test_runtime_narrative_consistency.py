# SPDX-License-Identifier: Apache-2.0

from app.services.runtime.runtime_launch_experience import build_runtime_launch_experience
from app.services.runtime.runtime_startup_visibility import build_runtime_startup_visibility


def test_runtime_narrative_consistency() -> None:
    launch = build_runtime_launch_experience({})
    vis = build_runtime_startup_visibility({})
    launch_msg = launch["runtime_launch_experience"]["message"]
    vis_banner = vis["runtime_startup_visibility"]["banner"]
    assert "AethOS" in launch_msg
    assert "AethOS" in vis_banner
    assert "Nexa" not in launch_msg
    assert "OpenClaw" not in vis_banner
