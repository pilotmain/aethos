"""One-shot React app scaffolding (argv-only subprocesses; never shell=True)."""

from __future__ import annotations

import re
import shutil
import subprocess
from pathlib import Path
from typing import Any

_APP_NAME_RE = re.compile(r"^[a-zA-Z][a-zA-Z0-9_-]{0,63}$")


def create_react_app(app_name: str, workspace_root: str) -> dict[str, Any]:
    """Create a React app with ``npx create-react-app``, run ``npm install``, best-effort ``npm start``."""
    name = (app_name or "").strip()
    if not name or not _APP_NAME_RE.fullmatch(name):
        return {
            "success": False,
            "steps": [{"step": "validate", "success": False, "output": "Invalid app name"}],
            "app_url": "http://localhost:3000",
            "app_path": "",
        }
    root = Path(workspace_root).expanduser().resolve()
    root.mkdir(parents=True, exist_ok=True)
    app_path = root / name
    results: list[dict[str, Any]] = []

    def run_step(argv: list[str], cwd: Path, description: str, timeout: int) -> None:
        try:
            r = subprocess.run(
                argv,
                cwd=str(cwd),
                capture_output=True,
                text=True,
                timeout=timeout,
            )
            ok = r.returncode == 0
            out = ((r.stdout or "")[:800] or (r.stderr or "")[:800]).strip()
            results.append({"step": description, "success": ok, "output": out or "(no output)"})
        except subprocess.TimeoutExpired:
            results.append({"step": description, "success": False, "output": "Timeout"})
        except (OSError, FileNotFoundError) as e:
            results.append({"step": description, "success": False, "output": str(e)[:500]})

    npx = shutil.which("npx") or "npx"
    run_step([npx, "--yes", "create-react-app", name], root, "Creating React app", 600)
    if not results or not results[-1].get("success"):
        return {
            "success": False,
            "steps": results,
            "app_url": "http://localhost:3000",
            "app_path": str(app_path),
        }

    npm = shutil.which("npm") or "npm"
    run_step([npm, "install"], app_path, "Installing dependencies", 600)

    try:
        subprocess.Popen(
            [npm, "start"],
            cwd=str(app_path),
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            start_new_session=True,
        )
        results.append(
            {"step": "Starting dev server", "success": True, "output": "Started in background"}
        )
    except (OSError, FileNotFoundError) as e:
        results.append(
            {"step": "Starting dev server", "success": False, "output": str(e)[:400]}
        )

    ok_all = all(bool(s.get("success")) for s in results)
    return {
        "success": ok_all,
        "steps": results,
        "app_url": "http://localhost:3000",
        "app_path": str(app_path),
    }


def parse_react_app_intent(text: str) -> dict[str, Any] | None:
    """Parse React app creation intent."""
    if not text or not isinstance(text, str):
        return None
    low = text.strip().splitlines()[0].strip().lower()
    patterns = [
        r"create\s+(?:a|an)?\s*react\s+app\s+called\s+(\w+)",
        r"make\s+(?:a|an)?\s*react\s+app\s+(\w+)",
        r"build\s+(?:a|an)?\s*react\s+app\s+(\w+)",
    ]
    for pattern in patterns:
        match = re.search(pattern, low)
        if match:
            return {"intent": "react_app", "app_name": match.group(1)}
    return None
