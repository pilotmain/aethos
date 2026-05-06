"""Railway CLI helper — deploy / auth probes (fixed argv only)."""

from __future__ import annotations

import os
import shutil
import subprocess
from typing import Any


class RailwayClient:
    """Thin synchronous wrapper around the Railway CLI."""

    def deploy(
        self,
        *,
        extra_env: dict[str, str] | None = None,
        retry_alt_port: int | None = None,
        timeout_sec: int = 180,
    ) -> dict[str, Any]:
        """
        Run ``railway up`` with optional extra env. If the first run fails and the error
        mentions port binding, optionally retry with ``PORT`` set to ``retry_alt_port``.
        """
        if not shutil.which("railway"):
            return {
                "success": False,
                "error": "Railway CLI not found. Install: `npm install -g @railway/cli`",
            }

        env = os.environ.copy()
        if extra_env:
            for k, v in extra_env.items():
                if k and v is not None:
                    env[str(k).strip()] = str(v)

        first = self._run_up(env, timeout_sec=timeout_sec)
        if first.get("success"):
            return first

        err_blob = (first.get("error") or "") + (first.get("stderr") or "")
        if retry_alt_port and "port" in err_blob.lower():
            env["PORT"] = str(retry_alt_port)
            second = self._run_up(env, timeout_sec=timeout_sec)
            second["retried"] = True
            second["retry_port"] = retry_alt_port
            return second
        return first

    def _run_up(self, env: dict[str, str], *, timeout_sec: int) -> dict[str, Any]:
        try:
            r = subprocess.run(
                ["railway", "up"],
                capture_output=True,
                text=True,
                timeout=timeout_sec,
                env=env,
            )
        except subprocess.TimeoutExpired:
            return {"success": False, "error": f"railway up timed out after {timeout_sec}s"}
        except OSError as exc:
            return {"success": False, "error": str(exc)}

        out = (r.stdout or "").strip()
        err = (r.stderr or "").strip()
        if r.returncode == 0:
            return {"success": True, "output": out or "(no stdout)", "stderr": err}
        return {
            "success": False,
            "error": err or out or f"exit {r.returncode}",
            "stdout": out,
            "stderr": err,
        }

    def whoami(self) -> dict[str, Any]:
        if not shutil.which("railway"):
            return {"logged_in": False, "error": "railway CLI not on PATH"}
        try:
            r = subprocess.run(
                ["railway", "whoami"],
                capture_output=True,
                text=True,
                timeout=15,
            )
        except (OSError, subprocess.TimeoutExpired) as exc:
            return {"logged_in": False, "error": str(exc)}
        out = (r.stdout or "").strip()
        if r.returncode == 0 and out:
            return {"logged_in": True, "user": out}
        return {"logged_in": False, "error": (r.stderr or out or "not logged in")[:500]}


_railway: RailwayClient | None = None


def get_railway_client() -> RailwayClient:
    global _railway
    if _railway is None:
        _railway = RailwayClient()
    return _railway


__all__ = ["RailwayClient", "get_railway_client"]
