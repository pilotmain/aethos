"""Cron CLI — thin wrapper around HTTP cron API (Phase 13)."""

from __future__ import annotations

import json
import sys

from app.channels.commands.cron_http import cron_cli_http


def cron_main(argv: list[str] | None = None) -> int:
    args = argv if argv is not None else sys.argv[1:]
    if not args:
        print("usage: cron list | add <cron> <message> | remove <id> | pause <id> | resume <id>")
        return 2
    cmd = args[0].lower()
    if cmd == "list":
        out = cron_cli_http("GET", "/cron/jobs")
        print(json.dumps(out, indent=2))
        return 0
    if cmd == "add" and len(args) >= 3:
        expr, msg = args[1], " ".join(args[2:])
        body = {
            "name": f"CLI: {msg[:80]}",
            "cron_expression": expr,
            "action_type": "channel_message",
            "action_payload": {
                "channel": "telegram",
                "chat_id": "",
                "message": msg,
            },
            "created_by": "cli",
            "created_by_channel": "cli",
        }
        out = cron_cli_http("POST", "/cron/jobs", json_body=body)
        print(json.dumps(out, indent=2))
        return 0
    if cmd == "remove" and len(args) >= 2:
        jid = args[1]
        out = cron_cli_http("DELETE", f"/cron/jobs/{jid}")
        print(json.dumps(out, indent=2))
        return 0
    if cmd == "pause" and len(args) >= 2:
        out = cron_cli_http("POST", f"/cron/jobs/{args[1]}/pause", json_body={})
        print(json.dumps(out, indent=2))
        return 0
    if cmd == "resume" and len(args) >= 2:
        out = cron_cli_http("POST", f"/cron/jobs/{args[1]}/resume", json_body={})
        print(json.dumps(out, indent=2))
        return 0
    print("usage: cron list | add <cron> <message> | remove <id> | pause <id> | resume <id>")
    return 2


__all__ = ["cron_main"]
