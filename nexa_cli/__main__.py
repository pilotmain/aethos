"""CLI entrypoint: ``python -m nexa_cli`` — Nexa Next HTTP API client (Phase 21)."""

from __future__ import annotations

import argparse
import json
import os
import sys
import urllib.error
import urllib.parse
import urllib.request
from typing import Any


def _base_url() -> str:
    return (os.environ.get("NEXA_API_BASE") or "http://127.0.0.1:8000").rstrip("/")


def _headers(uid: str) -> dict[str, str]:
    h = {"X-User-Id": uid, "Accept": "application/json"}
    tok = (os.environ.get("NEXA_WEB_API_TOKEN") or "").strip()
    if tok:
        h["Authorization"] = f"Bearer {tok}"
    return h


def _req(
    method: str,
    path: str,
    *,
    uid: str,
    body: bytes | None = None,
    content_type: str | None = None,
) -> tuple[int, str]:
    url = f"{_base_url()}{path}"
    h = _headers(uid)
    if content_type:
        h["Content-Type"] = content_type
    elif body is not None:
        h["Content-Type"] = "application/json"
    r = urllib.request.Request(url, data=body, method=method, headers=h)
    try:
        with urllib.request.urlopen(r, timeout=120) as resp:
            return resp.getcode(), resp.read().decode()
    except urllib.error.HTTPError as e:
        return e.code, e.read().decode()


def merge_settings_payload(base: dict[str, Any], pairs: list[str]) -> dict[str, Any]:
    """Merge key=value pairs onto a GET /user/settings JSON document for POST."""
    ui = dict(base.get("ui_preferences") or {})
    out_priv = base.get("privacy_mode")
    for p in pairs:
        k, _, v = p.partition("=")
        k, v = k.strip(), v.strip()
        if not k:
            continue
        if k == "privacy_mode":
            out_priv = v
        elif k == "theme":
            ui["theme"] = v
        elif k == "auto_refresh":
            ui["auto_refresh"] = v.lower() in ("1", "true", "yes", "on")
    payload: dict[str, Any] = {"ui_preferences": ui}
    if out_priv is not None:
        payload["privacy_mode"] = out_priv
    return payload


def cmd_settings_get(uid: str) -> int:
    code, body = _req("GET", "/api/v1/user/settings", uid=uid)
    print(body)
    return 0 if code == 200 else 1


def cmd_settings_set(uid: str, pairs: list[str]) -> int:
    code0, b0 = _req("GET", "/api/v1/user/settings", uid=uid)
    if code0 != 200:
        print(b0, file=sys.stderr)
        return 1
    cur = json.loads(b0)
    merged = merge_settings_payload(cur, pairs)
    payload = json.dumps(merged).encode()
    code1, b1 = _req("POST", "/api/v1/user/settings", uid=uid, body=payload)
    print(b1)
    return 0 if code1 == 200 else 1


def cmd_replay(uid: str, mission_id: str) -> int:
    mid = urllib.parse.quote(mission_id, safe="")
    code, body = _req(
        "POST",
        f"/api/v1/mission-control/replay/{mid}",
        uid=uid,
        body=b"{}",
    )
    print(f"HTTP {code}")
    print(body[:24000])
    return 0 if code == 200 else 1


def main() -> int:
    p = argparse.ArgumentParser(prog="nexa", description="Nexa Next CLI (HTTP)")
    p.add_argument(
        "--user-id",
        default=os.environ.get("NEXA_CLI_USER_ID") or "cli_user",
        help="X-User-Id header (or env NEXA_CLI_USER_ID)",
    )
    sub = p.add_subparsers(dest="cmd", required=True)

    sp_state = sub.add_parser("state", help="GET mission-control/state")
    sp_state.add_argument("--mission-user", default=None, help="Query user_id scope")

    sp_run = sub.add_parser("run", help="POST mission-control/gateway/run")
    sp_run.add_argument("text", help="Mission text")

    sp_replay = sub.add_parser("replay", help="POST mission-control/replay/{mission_id}")
    sp_replay.add_argument("mission_id")

    sp_settings = sub.add_parser("settings", help="User settings API")
    ss = sp_settings.add_subparsers(dest="settings_cmd", required=True)
    ss.add_parser("get", help="GET /api/v1/user/settings")
    sp_set = ss.add_parser("set", help="POST merged settings (key=value …)")
    sp_set.add_argument(
        "pairs",
        nargs="+",
        metavar="KEY=VALUE",
        help="e.g. privacy_mode=strict theme=dark auto_refresh=true",
    )

    args = p.parse_args()
    uid = str(args.user_id)

    if args.cmd == "state":
        q = f"?user_id={urllib.parse.quote(args.mission_user)}" if args.mission_user else ""
        code, body = _req("GET", f"/api/v1/mission-control/state{q}", uid=uid)
        print(body[:24000])
        return 0 if code == 200 else 1

    if args.cmd == "run":
        payload = json.dumps({"text": args.text, "user_id": uid}).encode()
        code, body = _req(
            "POST",
            "/api/v1/mission-control/gateway/run",
            uid=uid,
            body=payload,
        )
        print(body[:24000])
        return 0 if code == 200 else 1

    if args.cmd == "replay":
        return cmd_replay(uid, args.mission_id)

    if args.cmd == "settings":
        if args.settings_cmd == "get":
            return cmd_settings_get(uid)
        if args.settings_cmd == "set":
            return cmd_settings_set(uid, list(args.pairs))

    return 1


if __name__ == "__main__":
    raise SystemExit(main())
