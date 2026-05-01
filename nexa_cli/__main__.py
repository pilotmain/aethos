"""CLI entrypoint: ``python -m nexa_cli`` — talks to the Nexa API over HTTP."""

from __future__ import annotations

import argparse
import json
import os
import sys
import urllib.error
import urllib.parse
import urllib.request


def _base_url() -> str:
    return (os.environ.get("NEXA_API_BASE") or "http://127.0.0.1:8000").rstrip("/")


def _headers(uid: str) -> dict[str, str]:
    h = {"X-User-Id": uid, "Accept": "application/json"}
    tok = (os.environ.get("NEXA_WEB_API_TOKEN") or "").strip()
    if tok:
        h["Authorization"] = f"Bearer {tok}"
    return h


def _req(method: str, path: str, *, uid: str, body: bytes | None = None) -> tuple[int, str]:
    url = f"{_base_url()}{path}"
    r = urllib.request.Request(url, data=body, method=method, headers=_headers(uid))
    try:
        with urllib.request.urlopen(r, timeout=60) as resp:
            return resp.getcode(), resp.read().decode()
    except urllib.error.HTTPError as e:
        return e.code, e.read().decode()


def main() -> None:
    p = argparse.ArgumentParser(prog="nexa", description="Nexa Next CLI (HTTP)")
    p.add_argument("--user-id", default=os.environ.get("NEXA_CLI_USER_ID") or "cli_user", help="X-User-Id header")
    sub = p.add_subparsers(dest="cmd", required=True)

    sp_state = sub.add_parser("state", help="GET /api/v1/mission-control/state")
    sp_state.add_argument("--mission-user", default=None, help="Query user_id for snapshot scope")

    sp_run = sub.add_parser("run", help="POST /api/v1/mission-control/gateway/run (stub)")
    sp_run.add_argument("text", help="Mission text")

    sp_replay = sub.add_parser("replay", help="Placeholder — wire to your replay endpoint when available")
    sp_replay.add_argument("mission_id")

    args = p.parse_args()
    uid = str(args.user_id)

    if args.cmd == "state":
        q = f"?user_id={urllib.parse.quote(args.mission_user)}" if args.mission_user else ""
        code, body = _req("GET", f"/api/v1/mission-control/state{q}", uid=uid)
        print(code, body[:8000])
        sys.exit(0 if code == 200 else 1)

    if args.cmd == "run":
        payload = json.dumps({"text": args.text, "user_id": uid}).encode()
        req = urllib.request.Request(
            f"{_base_url()}/api/v1/mission-control/gateway/run",
            data=payload,
            method="POST",
            headers={**_headers(uid), "Content-Type": "application/json"},
        )
        try:
            with urllib.request.urlopen(req, timeout=120) as resp:
                print(resp.getcode(), resp.read().decode()[:8000])
        except urllib.error.HTTPError as e:
            print(e.code, e.read().decode())
            sys.exit(1)
        sys.exit(0)

    if args.cmd == "replay":
        print(
            "replay is not wired to a stable replay API in this build; use Mission Control UI or add an API route.",
            file=sys.stderr,
        )
        sys.exit(2)


if __name__ == "__main__":
    main()
