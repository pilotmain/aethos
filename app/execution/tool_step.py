"""Dispatch one execution-plan step to a concrete tool runtime."""

from __future__ import annotations

import json
import time
import urllib.error
import urllib.request
from typing import Any

from app.tools import runtime_deploy
from app.tools import runtime_files
from app.tools import runtime_shell
from app.tools import runtime_workspace


def _inp(step: dict[str, Any]) -> dict[str, Any]:
    t = step.get("tool")
    if isinstance(t, dict):
        raw = t.get("input")
        return dict(raw) if isinstance(raw, dict) else {}
    return {}


def execute_tool_step(step: dict[str, Any]) -> dict[str, Any]:
    """
    Run the tool described by ``step`` (``tool.name`` + ``tool.input``, or ``type``).
    Returns a result dict (never raises for normal tool failures).
    """
    t = step.get("tool")
    name = ""
    if isinstance(t, dict):
        name = str(t.get("name") or "").strip()
    if not name:
        name = str(step.get("type") or "noop").strip() or "noop"
    inp = _inp(step)

    if name == "noop":
        return {"tool": "noop", "ok": True}

    if name == "shell":
        cmd = str(inp.get("command") or "").strip()
        timeout = float(inp.get("timeout_sec") or 120.0)
        return runtime_shell.run_shell_command(cmd, timeout_sec=timeout)

    if name == "file_read":
        return runtime_files.file_read(str(inp.get("path") or ""))

    if name == "file_write":
        return runtime_files.file_write(str(inp.get("path") or ""), str(inp.get("content") or ""))

    if name == "file_patch":
        return runtime_files.file_patch(
            str(inp.get("path") or ""),
            str(inp.get("old") or ""),
            str(inp.get("new") or ""),
        )

    if name == "workspace_list":
        return runtime_workspace.workspace_list()

    if name == "workspace_search":
        return runtime_workspace.workspace_search(str(inp.get("substring") or ""))

    if name == "deploy":
        return runtime_deploy.run_deploy_step(stage=inp.get("stage"), note=inp.get("note"))

    if name == "http_request":
        return _http_request_tool(inp)

    if name == "internal_api":
        return _internal_api_tool(inp)

    return {"tool": name, "ok": False, "error": "unknown_tool"}


def _http_request_tool(inp: dict[str, Any]) -> dict[str, Any]:
    url = str(inp.get("url") or "").strip()
    method = str(inp.get("method") or "GET").upper()
    low = url.lower()
    if not low.startswith(("http://127.0.0.1", "http://localhost")):
        return {"tool": "http_request", "ok": False, "error": "url_not_allowed", "url": url}
    if method not in ("GET", "POST"):
        return {"tool": "http_request", "ok": False, "error": "method_not_allowed"}
    started = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
    try:
        data = None
        headers = {"Accept": "application/json"}
        if method == "POST":
            body_obj = inp.get("json")
            payload = json.dumps(body_obj if body_obj is not None else {}).encode("utf-8")
            data = payload
            headers["Content-Type"] = "application/json"
        req = urllib.request.Request(url, data=data, method=method, headers=headers)
        with urllib.request.urlopen(req, timeout=float(inp.get("timeout_sec") or 15.0)) as resp:
            raw = resp.read()[:200_000].decode("utf-8", errors="replace")
            code = int(getattr(resp, "status", 200) or 200)
    except urllib.error.HTTPError as exc:
        raw = (exc.read() or b"")[:50_000].decode("utf-8", errors="replace")
        code = int(exc.code)
    except Exception as exc:  # noqa: BLE001
        return {
            "tool": "http_request",
            "ok": False,
            "error": str(exc),
            "url": url,
            "started_at": started,
            "completed_at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        }
    done = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
    ok = 200 <= code < 300
    return {
        "tool": "http_request",
        "ok": ok,
        "status_code": code,
        "body": raw,
        "url": url,
        "started_at": started,
        "completed_at": done,
    }


def _internal_api_tool(inp: dict[str, Any]) -> dict[str, Any]:
    path = str(inp.get("path") or "").strip()
    if not path.startswith("/"):
        path = "/" + path
    base = str(inp.get("base_url") or "http://127.0.0.1:8000").rstrip("/")
    return _http_request_tool({"url": base + path, "method": "GET"})


def tool_result_ok(tool_name: str, result: dict[str, Any]) -> bool:
    """Interpret ``execute_tool_step`` result as success for plan progression."""
    if result.get("ok") is True:
        return True
    if tool_name == "shell":
        if result.get("ok") is False:
            return False
        rc = result.get("returncode")
        if rc is None:
            return False
        return int(rc) == 0
    if tool_name in ("file_read", "file_write", "file_patch"):
        return bool(result.get("ok"))
    if tool_name in ("workspace_list", "workspace_search"):
        return "error" not in result
    if tool_name == "deploy":
        return str(result.get("status") or "") == "recorded"
    if tool_name in ("http_request", "internal_api"):
        return bool(result.get("ok")) and 200 <= int(result.get("status_code") or 0) < 300
    if tool_name == "noop":
        return True
    return False


def step_tool_name(step: dict[str, Any]) -> str:
    t = step.get("tool")
    if isinstance(t, dict) and t.get("name"):
        return str(t.get("name"))
    return str(step.get("type") or "noop")
