"""
HTTP client for Cursor Cloud Agents API.

Public examples commonly use POST /v0/agents with Bearer auth and a body shaped as:
``prompt.text`` + ``source.repository`` / ``source.ref``.

Docs also describe newer /v1 shapes; this client targets the v0 contract above.
"""

from __future__ import annotations

import logging
from typing import Any

import httpx

logger = logging.getLogger(__name__)


class CursorApiError(RuntimeError):
    """HTTP error from Cursor API; ``body`` holds the raw response body (truncated in ``args`` message)."""

    def __init__(self, status_code: int, body: str, *, path: str = "") -> None:
        self.status_code = int(status_code)
        self.body = body
        self.path = path
        snippet = (body or "").strip()
        if len(snippet) > 2000:
            snippet = snippet[:2000] + "…"
        msg = f"Cursor API HTTP {self.status_code}"
        if path:
            msg = f"{msg} {path}"
        if snippet:
            msg = f"{msg}: {snippet}"
        super().__init__(msg)


def _first(d: dict[str, Any], *keys: str) -> Any:
    for k in keys:
        if k in d and d[k] is not None:
            return d[k]
    return None


def dig(obj: Any, *path: str) -> Any:
    cur: Any = obj
    for p in path:
        if not isinstance(cur, dict):
            return None
        cur = cur.get(p)
    return cur


def _require_ok(
    response: httpx.Response,
    *,
    context: str,
    api_path: str = "",
) -> None:
    """Log full response body on failure (especially 400), then raise CursorApiError."""
    if response.is_success:
        return
    raw = response.text or ""
    trimmed = raw.strip()
    if len(trimmed) > 8000:
        trimmed = trimmed[:8000] + "…"
    logger.error(
        "%s: HTTP %s — response body: %s",
        context,
        response.status_code,
        trimmed if trimmed else "(empty)",
    )
    raise CursorApiError(response.status_code, raw, path=api_path)


class CursorCloudClient:
    """Create-agent + get-run client (v0 agents API)."""

    def __init__(
        self,
        *,
        api_key: str,
        base_url: str = "https://api.cursor.com",
        timeout_seconds: float = 120.0,
        transport: httpx.BaseTransport | None = None,
    ) -> None:
        self._api_key = (api_key or "").strip()
        self._base = (base_url or "").strip().rstrip("/") or "https://api.cursor.com"
        self._timeout = timeout_seconds
        self._transport = transport

    def _headers(self) -> dict[str, str]:
        h = {
            "Content-Type": "application/json",
            "Accept": "application/json",
        }
        if self._api_key:
            h["Authorization"] = f"Bearer {self._api_key}"
        return h

    def _client(self) -> httpx.Client:
        kw: dict[str, Any] = {
            "base_url": self._base,
            "headers": self._headers(),
            "timeout": httpx.Timeout(self._timeout),
        }
        if self._transport is not None:
            kw["transport"] = self._transport
        return httpx.Client(**kw)

    def create_agent_run(
        self,
        *,
        prompt_text: str,
        repo_url: str,
        starting_ref: str,
        model_id: str | None,
        auto_create_pr: bool = False,
    ) -> dict[str, Any]:
        """
        POST /v0/agents — returns parsed JSON (agent + run identifiers vary by API version).

        ``model_id`` and ``auto_create_pr`` are omitted from the v0 body unless the API
        adds documented support; keeping parameters preserves the runner call signature.
        """
        body: dict[str, Any] = {
            "prompt": {"text": prompt_text},
            "source": {
                "repository": repo_url.strip(),
                "ref": starting_ref.strip(),
            },
        }
        logger.debug(
            "Cursor v0 POST /v0/agents (model_id and auto_create_pr are not sent on v0 minimal contract): "
            "model_id=%r auto_create_pr=%r",
            model_id,
            auto_create_pr,
        )

        with self._client() as c:
            r = c.post("/v0/agents", json=body)
            _require_ok(r, context="POST /v0/agents", api_path="/v0/agents")
            try:
                data = r.json()
            except ValueError as e:
                logger.error("POST /v0/agents: invalid JSON body (text=%s)", (r.text or "")[:2000])
                raise CursorApiError(r.status_code, r.text or "", path="/v0/agents") from e
        if not isinstance(data, dict):
            raise ValueError("Cursor API returned non-object JSON")
        return data

    def get_run(self, *, agent_id: str, run_id: str) -> dict[str, Any]:
        """GET /v0/agents/{agent_id}/runs/{run_id}"""
        aid = (agent_id or "").strip()
        rid = (run_id or "").strip()
        path = f"/v0/agents/{aid}/runs/{rid}"
        with self._client() as c:
            r = c.get(path)
            _require_ok(r, context=f"GET {path}", api_path=path)
            try:
                data = r.json()
            except ValueError as e:
                logger.error("GET %s: invalid JSON body (text=%s)", path, (r.text or "")[:2000])
                raise CursorApiError(r.status_code, r.text or "", path=path) from e
        if not isinstance(data, dict):
            raise ValueError("Cursor API returned non-object JSON")
        return data


def parse_create_agent_response(payload: dict[str, Any]) -> tuple[str, str, str | None]:
    """
    Extract (agent_id, run_id, run_status) from POST create-agent response.
    Tolerates camelCase / nested shapes from beta API.
    """
    agent = dig(payload, "agent") or payload
    run = dig(payload, "run") or dig(payload, "initialRun") or {}

    agent_id = str(
        _first(agent if isinstance(agent, dict) else {}, "id", "ID")
        or _first(payload, "agentId", "agent_id")
        or ""
    ).strip()

    run_id = str(
        _first(run if isinstance(run, dict) else {}, "id", "ID")
        or _first(payload, "runId", "run_id")
        or ""
    ).strip()

    st: str | None = None
    if isinstance(run, dict):
        st = run.get("status") or run.get("state")
        if st is not None:
            st = str(st).strip().upper()
    return agent_id, run_id, st


def parse_run_status(payload: dict[str, Any]) -> str:
    """Normalize run status string (uppercased) or UNKNOWN."""
    if not isinstance(payload, dict):
        return "UNKNOWN"
    st = payload.get("status") or payload.get("state")
    if st is None:
        return "UNKNOWN"
    return str(st).strip().upper()


def terminal_run_status(status: str) -> bool:
    s = (status or "").strip().upper()
    return s in (
        "COMPLETED",
        "DONE",
        "FAILED",
        "CANCELLED",
        "CANCELED",
        "ERROR",
        "SUCCEEDED",
        "SUCCESS",
    )


def failed_run_status(status: str) -> bool:
    s = (status or "").strip().upper()
    return s in ("FAILED", "ERROR", "CANCELLED", "CANCELED")
