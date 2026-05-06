"""Railway CLI helper — deploy / auth probes (fixed argv only).

Supports **`RAILWAY_TOKEN`** / **`RAILWAY_API_TOKEN`** so CI-style deploys work without `railway link`.
Optional: **`RAILWAY_PROJECT_ID`** (CLI selects project when not linked).
"""

from __future__ import annotations

import logging
import re
import shutil
import subprocess
import threading
import time
from typing import Any

from app.services.infra.cli_env import cli_auth_env

logger = logging.getLogger(__name__)

_RAILWAY_HTTP_RE = re.compile(r"https?://[^\s\)<>`\"']+", re.I)


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

        env = cli_auth_env()
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
        argv_candidates = (
            ["railway", "up", "--detach"],
            ["railway", "up"],
        )
        last_out = ""
        last_err = ""
        last_code = 1
        for argv in argv_candidates:
            try:
                r = subprocess.run(
                    argv,
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
            last_out, last_err, last_code = out, err, r.returncode
            if r.returncode == 0:
                return {"success": True, "output": out or "(no stdout)", "stderr": err}
            blob = (err or out or "").lower()
            if "--detach" in argv and ("unknown" in blob or "invalid" in blob) and "detach" in blob:
                continue

        hint = ""
        b = (last_err or last_out or "").lower()
        if "link" in b or "no linked" in b or "not linked" in b:
            hint = (
                "\n💡 Set **RAILWAY_TOKEN** (and optionally **RAILWAY_PROJECT_ID**) in `.env`, "
                "or run `railway link` once on the worker."
            )
        return {
            "success": False,
            "error": (last_err or last_out or f"exit {last_code}") + hint,
            "stdout": last_out,
            "stderr": last_err,
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
                env=cli_auth_env(),
            )
        except (OSError, subprocess.TimeoutExpired) as exc:
            return {"logged_in": False, "error": str(exc)}
        out = (r.stdout or "").strip()
        if r.returncode == 0 and out:
            return {"logged_in": True, "user": out}
        return {"logged_in": False, "error": (r.stderr or out or "not logged in")[:500]}

    @staticmethod
    def _first_http_url(text: str, *, substr: str | None = None) -> str | None:
        blob = text or ""
        for m in _RAILWAY_HTTP_RE.finditer(blob):
            u = (m.group(0) or "").rstrip(".,;)")
            if substr and substr.lower() not in u.lower():
                continue
            return u
        return None

    def _extract_service_url(self, output: str) -> str | None:
        """Best-effort deploy URL from CLI stdout/stderr."""
        for needle in ("railway.app", "railway"):
            u = self._first_http_url(output, substr=needle)
            if u:
                return u
        return self._first_http_url(output)

    def _extract_logs_dashboard_url(self, output: str) -> str | None:
        u = self._first_http_url(output, substr="railway.app")
        if u and "/deploy" in u:
            return u
        return self._first_http_url(output, substr="railway")

    def fetch_recent_logs(self, *, tail: int = 100, timeout_sec: int = 90) -> str:
        """Tail Railway service logs via CLI (same auth env as deploy)."""
        if not shutil.which("railway"):
            return ""
        env = cli_auth_env()
        argv_sets = (
            ["railway", "logs", "--tail", str(tail)],
            ["railway", "logs", "--lines", str(tail)],
            ["railway", "logs"],
        )
        last = ""
        for argv in argv_sets:
            try:
                r = subprocess.run(
                    argv,
                    capture_output=True,
                    text=True,
                    timeout=timeout_sec,
                    env=env,
                )
            except (OSError, subprocess.TimeoutExpired) as exc:
                logger.debug("railway logs argv=%s err=%s", argv, exc)
                continue
            out = (r.stdout or "").strip()
            err = (r.stderr or "").strip()
            blob = out or err
            if blob:
                last = blob
            if r.returncode == 0 and blob:
                return blob[:12000]
            if blob and ("unknown" not in blob.lower() or len(blob) > 80):
                last = blob
        return last[:12000]

    def _collect_logs_background(self, session_id: int) -> None:
        """Poll ``railway logs`` periodically and persist tail text for session recall."""

        def worker() -> None:
            from app.services.deployment.session import get_deployment_session

            store = get_deployment_session()
            for _attempt in range(30):
                time.sleep(10)
                logs = self.fetch_recent_logs(tail=120)
                if logs:
                    store.store_logs(session_id, logs)
                low = (logs or "").lower()
                if any(x in low for x in ("build failed", "error:", "fatal", "npm err", " exited with ")):
                    break

        threading.Thread(
            target=worker,
            daemon=True,
            name=f"railway-log-tail-{session_id}",
        ).start()

    def deploy_and_track(
        self,
        *,
        chat_id: str | None,
        extra_env: dict[str, str] | None = None,
        retry_alt_port: int | None = None,
        timeout_sec: int = 180,
        metadata: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        """
        Run ``deploy`` and record a deployment session for ops memory + background log tail.

        When ``chat_id`` is omitted (non-chat callers), behaves like plain :meth:`deploy`.
        """
        from app.services.deployment.session import get_deployment_session

        session_store = get_deployment_session()
        sid: int | None = None
        cid = (chat_id or "").strip()
        if cid:
            sid = session_store.start_session(cid, "railway", metadata)

        res = self.deploy(extra_env=extra_env, retry_alt_port=retry_alt_port, timeout_sec=timeout_sec)

        if sid is None:
            return res

        if res.get("success"):
            blob = (res.get("output") or "") + "\n" + (res.get("stderr") or "")
            url = self._extract_service_url(blob)
            logs_url = self._extract_logs_dashboard_url(blob)
            session_store.update_session(
                sid,
                "success",
                url=url,
                logs_url=logs_url,
                set_completed=True,
                clear_error=True,
            )
            self._collect_logs_background(sid)
        else:
            err = (res.get("error") or res.get("stderr") or "unknown error")[:8000]
            session_store.update_session(sid, "failed", error=err, set_completed=True)

        out = dict(res)
        out["deployment_session_id"] = sid
        return out


_railway: RailwayClient | None = None


def get_railway_client() -> RailwayClient:
    global _railway
    if _railway is None:
        _railway = RailwayClient()
    return _railway


__all__ = ["RailwayClient", "get_railway_client"]
