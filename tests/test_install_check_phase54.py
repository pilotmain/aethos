from __future__ import annotations

import json
import subprocess
from pathlib import Path


def test_install_check_supports_json_flag() -> None:
    root = Path(__file__).resolve().parents[1]
    script = root / "scripts" / "install_check.sh"
    r = subprocess.run(
        ["bash", str(script), "--json"],
        cwd=str(root),
        capture_output=True,
        text=True,
        timeout=120,
    )
    assert r.returncode in (0, 1)
    payload = json.loads(r.stdout.strip().splitlines()[-1])
    assert "checks" in payload
    assert isinstance(payload["checks"], list)
