"""Convert Slack Bolt payloads into the ``raw_event`` shape expected by :class:`~app.services.channel_gateway.slack_adapter.SlackAdapter`."""

from __future__ import annotations

from typing import Any


def bolt_body_to_raw_event(body: dict[str, Any]) -> dict[str, Any]:
    """
    Bolt ``body`` includes ``event``, ``team_id``, ``authorizations``, etc.

    ``SlackAdapter`` expects ``{"event": <message event dict>, "team_id": str}``.
    """
    ev = body.get("event")
    if not isinstance(ev, dict):
        raise ValueError("bolt body missing event dict")
    team_id = body.get("team_id")
    if not team_id and isinstance(body.get("authorizations"), list) and body["authorizations"]:
        auth0 = body["authorizations"][0]
        if isinstance(auth0, dict):
            team_id = auth0.get("team_id")
    if not team_id:
        team_id = ev.get("team") or ev.get("team_id") or ""
    return {"event": ev, "team_id": str(team_id or "").strip()}


def synthetic_message_event_from_command(command: dict[str, Any]) -> dict[str, Any]:
    """Slash commands are not normal message events — synthesize one for the adapter."""
    return {
        "type": "message",
        "user": command.get("user_id"),
        "text": (command.get("text") or "").strip(),
        "channel": command.get("channel_id"),
        "team_id": command.get("team_id"),
    }


def reaction_summary_text(event: dict[str, Any]) -> str:
    """Turn ``reaction_added`` into text routed through the gateway (optional automation hook)."""
    react = (event.get("reaction") or "").strip()
    uid = (event.get("user") or "").strip()
    item = event.get("item") or {}
    ch = (item.get("channel") or "").strip()
    ts = (item.get("ts") or "").strip()
    who = f"<@{uid}>" if uid else "someone"
    tail = f" in {ch}@{ts}" if ch and ts else ""
    return f"[slack reaction] {who} added :{react}:{tail}"


__all__ = ["bolt_body_to_raw_event", "reaction_summary_text", "synthetic_message_event_from_command"]
