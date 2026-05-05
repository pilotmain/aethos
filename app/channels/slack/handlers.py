"""Slack Bolt event handlers — Socket Mode (Phase 12.1)."""

from __future__ import annotations

import asyncio
import logging
from typing import Any

from slack_bolt.async_app import AsyncApp

from app.channels.slack.message_converter import (
    bolt_body_to_raw_event,
    reaction_summary_text,
    synthetic_message_event_from_command,
)
from app.core.config import get_settings
from app.core.db import SessionLocal
from app.services.channel_gateway.metadata import build_channel_origin
from app.services.channel_gateway.origin_context import bind_channel_origin
from app.services.channel_gateway.router import handle_incoming_channel_message
from app.services.channel_gateway.slack_adapter import get_slack_adapter
from app.services.channel_gateway.slack_api import slack_chat_post_message, slack_files_upload
from app.services.channel_gateway.slack_adapter import get_slack_adapter
from app.services.channel_gateway.slack_blocks import permission_blocks
from app.services.channels.slack_bot import slack_inbound_via_gateway
from app.services.orchestrator_service import OrchestratorService

logger = logging.getLogger("nexa.channels.slack")

orchestrator = OrchestratorService()


def _should_ignore_message_event(ev: dict[str, Any]) -> bool:
    if ev.get("bot_id") or ev.get("subtype") in (
        "bot_message",
        "message_changed",
        "message_deleted",
    ):
        return True
    if not ev.get("user"):
        return True
    return False


def _post_reply(
    *,
    token: str,
    channel: str,
    text_out: str,
    thread_ts: str | None,
    blocks: list[dict[str, Any]] | None,
    app_uid: str,
) -> None:
    slack_chat_post_message(
        token,
        channel=channel,
        text=text_out[:39000],
        thread_ts=thread_ts,
        blocks=blocks,
        rate_limit_user_id=app_uid,
    )


def _deliver_normalized(raw_event: dict[str, Any]) -> tuple[dict[str, Any], str]:
    """Run the same gateway branch as :mod:`app.api.routes.slack` Events handler."""
    db = SessionLocal()
    try:
        adapter = get_slack_adapter()
        app_uid = adapter.resolve_app_user_id(db, raw_event)
        orchestrator.users.get_or_create(db, app_uid)
        norm = adapter.normalize_message(raw_event, app_user_id=app_uid)
        if getattr(get_settings(), "nexa_slack_route_inbound", False):
            env = slack_inbound_via_gateway(db, norm)
        else:
            with bind_channel_origin(build_channel_origin(norm)):
                env = handle_incoming_channel_message(db, normalized_message=norm)
        return env, app_uid
    finally:
        db.close()


def register_slack_handlers(app: AsyncApp) -> None:
    @app.event("message")
    async def _on_message(body: dict[str, Any], ack: Any) -> None:
        await ack()
        ev = body.get("event") or {}
        if _should_ignore_message_event(ev):
            return
        text = str(ev.get("text") or "").strip()
        s_set = get_settings()
        files = ev.get("files")
        image_private_url: str | None = None
        audio_private_url: str | None = None
        audio_file_mime: str | None = None
        if isinstance(files, list):
            for fi in files:
                if not isinstance(fi, dict):
                    continue
                mt = str(fi.get("mimetype") or "")
                url = (fi.get("url_private_download") or fi.get("url_private") or "").strip()
                if not url:
                    continue
                if mt.startswith("image/") and not image_private_url:
                    image_private_url = url
                elif mt.startswith("audio/") and not audio_private_url:
                    audio_private_url = url
                    audio_file_mime = mt.split(";")[0].strip()

        if (
            not text
            and image_private_url
            and s_set.nexa_multimodal_enabled
            and s_set.nexa_multimodal_vision_enabled
        ):
            token = (s_set.slack_bot_token or "").strip()
            if not token:
                return
            try:
                raw_event = bolt_body_to_raw_event(body)
            except Exception as exc:  # noqa: BLE001
                logger.warning("slack bolt raw_event build failed: %s", exc)
                return
            db = SessionLocal()
            try:
                app_uid = get_slack_adapter().resolve_app_user_id(db, raw_event)
            finally:
                db.close()
            try:
                import httpx

                from app.services.multimodal.orchestrator import analyze_image_bytes

                headers = {"Authorization": f"Bearer {token}"}
                with httpx.Client(timeout=90.0, follow_redirects=True) as client:
                    im = client.get(image_private_url, headers=headers)
                    im.raise_for_status()
                    raw_b = im.content
                    ct = (im.headers.get("content-type") or "image/png").split(";")[0].strip()
                out = await asyncio.to_thread(
                    analyze_image_bytes,
                    image_bytes=raw_b,
                    mime=ct,
                    prompt=None,
                    session_id=str(ev.get("ts") or ""),
                )
            except Exception as exc:  # noqa: BLE001
                logger.warning("slack vision download/analyze failed: %s", exc)
                return
            ch = str(ev.get("channel") or "")
            thread_ref = str(ev.get("thread_ts")).strip() if ev.get("thread_ts") else None
            text_out = (
                (out.get("text") or "").strip()[:39000]
                if out.get("ok")
                else str(out.get("error") or "vision failed")[:39000]
            )
            if not text_out:
                return
            try:
                await asyncio.to_thread(
                    _post_reply,
                    token=token,
                    channel=ch,
                    text_out=text_out,
                    thread_ts=thread_ref,
                    blocks=None,
                    app_uid=app_uid,
                )
            except Exception as exc:  # noqa: BLE001
                logger.exception("slack vision outbound failed: %s", exc)
            return

        if (
            not text
            and audio_private_url
            and s_set.nexa_multimodal_enabled
        ):
            from app.services.multimodal.orchestrator import audio_input_enabled, transcribe_uploaded_audio_bytes
            from app.services.multimodal.stt import audio_mime_allowed, max_audio_bytes_cap

            if not audio_input_enabled():
                return
            token = (s_set.slack_bot_token or "").strip()
            if not token:
                return
            try:
                import httpx

                headers = {"Authorization": f"Bearer {token}"}
                with httpx.Client(timeout=120.0, follow_redirects=True) as client:
                    resp = client.get(audio_private_url, headers=headers)
                    resp.raise_for_status()
                    raw_b = resp.content
                    ct = (resp.headers.get("content-type") or audio_file_mime or "application/ogg").split(
                        ";"
                    )[0].strip()
                cap_b = max_audio_bytes_cap()
                if len(raw_b) > cap_b:
                    logger.warning("slack audio exceeds configured max bytes")
                    return
                if not audio_mime_allowed(ct):
                    logger.warning("slack audio mime not allowed: %s", ct)
                    return
                ext = (ct.split("/")[-1] if "/" in ct else "ogg").split("+")[0][:32] or "ogg"
                fname = f"slack_audio.{ext}"
                out = await asyncio.to_thread(
                    transcribe_uploaded_audio_bytes,
                    raw_b,
                    filename=fname,
                    mime=ct,
                )
            except Exception as exc:  # noqa: BLE001
                logger.warning("slack audio STT failed: %s", exc)
                return
            if not out.get("ok"):
                return
            transcript = (out.get("text") or "").strip()
            if not transcript:
                return
            ev["text"] = transcript
            text = transcript

        if not text:
            return
        try:
            raw_event = bolt_body_to_raw_event(body)
        except Exception as exc:  # noqa: BLE001
            logger.warning("slack bolt raw_event build failed: %s", exc)
            return

        token = (get_settings().slack_bot_token or "").strip()
        if not token:
            return

        try:
            env, app_uid = await asyncio.to_thread(_deliver_normalized, raw_event)
        except Exception as exc:  # noqa: BLE001
            logger.exception("slack socket inbound failed: %s", exc)
            return

        ch = str(ev.get("channel") or "")
        thread_ref = str(ev.get("thread_ts")).strip() if ev.get("thread_ts") else None
        text_out = (env.get("message") or "")[:39000]
        pr = env.get("permission_required")
        blocks = None
        if pr:
            blocks = permission_blocks(pr=pr, channel_for_reply=ch)
            text_out = text_out or "🔐 Permission required — use the buttons below."
        try:
            await asyncio.to_thread(
                _post_reply,
                token=token,
                channel=ch,
                text_out=text_out,
                thread_ts=thread_ref,
                blocks=blocks,
                app_uid=app_uid,
            )
        except Exception as exc:  # noqa: BLE001
            logger.exception("slack socket outbound failed: %s", exc)

    @app.event("reaction_added")
    async def _on_reaction(body: dict[str, Any], ack: Any) -> None:
        await ack()
        if not getattr(get_settings(), "nexa_slack_reactions_enabled", False):
            return
        ev = body.get("event") or {}
        if ev.get("item", {}).get("type") != "message":
            return
        summary = reaction_summary_text(ev)
        token = (get_settings().slack_bot_token or "").strip()
        if not token:
            return
        try:
            item = ev.get("item") or {}
            inner_event = {
                "type": "message",
                "user": ev.get("user"),
                "text": summary,
                "channel": str(item.get("channel") or ""),
                "ts": item.get("ts"),
            }
            raw_event = {"event": inner_event, "team_id": str(body.get("team_id") or "")}
            env, app_uid = await asyncio.to_thread(_deliver_normalized, raw_event)
        except Exception as exc:  # noqa: BLE001
            logger.warning("slack reaction routing skipped: %s", exc)
            return
        ch_out = str(ev.get("item", {}).get("channel") or "")
        if not ch_out:
            return
        text_out = (env.get("message") or "").strip()
        if not text_out:
            return
        try:
            await asyncio.to_thread(
                _post_reply,
                token=token,
                channel=ch_out,
                text_out=text_out[:39000],
                thread_ts=str(ev.get("item", {}).get("ts") or "") or None,
                blocks=None,
                app_uid=app_uid,
            )
        except Exception as exc:  # noqa: BLE001
            logger.warning("slack reaction reply failed: %s", exc)

    @app.command("/nexa")
    async def _nexa_cmd(ack: Any, command: dict[str, Any]) -> None:
        await ack()
        token = (get_settings().slack_bot_token or "").strip()
        if not token:
            return
        synthetic_ev = synthetic_message_event_from_command(command)
        team_id = str(command.get("team_id") or "").strip()
        raw_event = {"event": synthetic_ev, "team_id": team_id}
        try:
            env, app_uid = await asyncio.to_thread(_deliver_normalized, raw_event)
        except Exception as exc:  # noqa: BLE001
            logger.exception("slack /nexa failed: %s", exc)
            return
        ch = str(command.get("channel_id") or "")
        text_out = (env.get("message") or "")[:39000]
        pr = env.get("permission_required")
        blocks = None
        if pr:
            blocks = permission_blocks(pr=pr, channel_for_reply=ch)
            text_out = text_out or "🔐 Permission required — use the buttons below."
        try:
            await asyncio.to_thread(
                _post_reply,
                token=token,
                channel=ch,
                text_out=text_out,
                thread_ts=None,
                blocks=blocks,
                app_uid=app_uid,
            )
        except Exception as exc:  # noqa: BLE001
            logger.exception("slack /nexa outbound failed: %s", exc)

    @app.command("/nexa_cron")
    async def _nexa_cron_slack(ack: Any, command: dict[str, Any]) -> None:
        await ack()
        from app.channels.commands import cron_http

        raw = (command.get("text") or "").strip()
        channel_id = str(command.get("channel_id") or "")
        user_id = str(command.get("user_id") or "")
        try:
            if not raw or raw.lower() in ("list", "ls"):
                msg = await cron_http.cron_list_via_api()
            elif raw.lower().startswith("remove"):
                parts = raw.split()
                if len(parts) >= 2:
                    msg = await cron_http.cron_remove_via_api(f"/cron_remove {parts[1]}")
                else:
                    msg = "Usage: `/nexa_cron remove <job_id>`"
            elif raw.startswith("schedule ") or raw.startswith("/schedule"):
                line = raw if raw.startswith("/") else f"/{raw}"
                msg = await cron_http.schedule_via_api(
                    line,
                    user_id or channel_id,
                    channel="slack",
                    slack_channel_id=channel_id,
                )
            else:
                msg = (
                    "Usage:\n"
                    "`/nexa_cron list`\n"
                    "`/nexa_cron remove <job_id>`\n"
                    '`/nexa_cron schedule "0 9 * * *" "message"`'
                )
        except Exception as exc:  # noqa: BLE001
            logger.exception("slack /nexa_cron failed: %s", exc)
            msg = str(exc)[:500]
        token = (get_settings().slack_bot_token or "").strip()
        if token and channel_id:
            try:
                await asyncio.to_thread(
                    _post_reply,
                    token=token,
                    channel=channel_id,
                    text_out=msg[:39000],
                    thread_ts=None,
                    blocks=None,
                    app_uid=user_id or "slack_cron",
                )
            except Exception as exc:  # noqa: BLE001
                logger.warning("slack /nexa_cron reply failed: %s", exc)

    @app.command("/nexa_browser")
    async def _nexa_browser_slack(ack: Any, command: dict[str, Any]) -> None:
        await ack()
        from app.channels.commands.browser_http import browser_via_api

        raw = (command.get("text") or "").strip()
        channel_id = str(command.get("channel_id") or "")
        user_id = str(command.get("user_id") or "")
        line = f"/browser {raw}".strip() if raw else "/browser"
        try:
            msg = await browser_via_api(line)
        except Exception as exc:  # noqa: BLE001
            logger.exception("slack /nexa_browser failed: %s", exc)
            msg = str(exc)[:500]
        token = (get_settings().slack_bot_token or "").strip()
        if token and channel_id:
            try:
                await asyncio.to_thread(
                    _post_reply,
                    token=token,
                    channel=channel_id,
                    text_out=msg[:39000],
                    thread_ts=None,
                    blocks=None,
                    app_uid=user_id or "slack_browser",
                )
            except Exception as exc:  # noqa: BLE001
                logger.warning("slack /nexa_browser reply failed: %s", exc)

    @app.command("/imagine")
    async def _imagine_slack(ack: Any, command: dict[str, Any]) -> None:
        await ack()
        from app.services.multimodal.image_generation import first_image_payload_for_telegram
        from app.services.multimodal.orchestrator import generate_images_from_prompt, image_gen_enabled

        s_set = get_settings()
        raw = (command.get("text") or "").strip()
        channel_id = str(command.get("channel_id") or "")
        user_id = str(command.get("user_id") or "")
        token = (s_set.slack_bot_token or "").strip()
        if not token or not channel_id:
            return
        if not s_set.nexa_multimodal_enabled or not image_gen_enabled():
            try:
                await asyncio.to_thread(
                    _post_reply,
                    token=token,
                    channel=channel_id,
                    text_out=(
                        "Image generation is off (enable NEXA_MULTIMODAL_ENABLED and "
                        "NEXA_MULTIMODAL_IMAGE_ENABLED or NEXA_IMAGE_GEN_ENABLED)."
                    ),
                    thread_ts=None,
                    blocks=None,
                    app_uid=user_id or "slack_imagine",
                )
            except Exception as exc:  # noqa: BLE001
                logger.warning("slack /imagine disabled reply failed: %s", exc)
            return
        if not raw:
            try:
                await asyncio.to_thread(
                    _post_reply,
                    token=token,
                    channel=channel_id,
                    text_out="Usage: /imagine <prompt>",
                    thread_ts=None,
                    blocks=None,
                    app_uid=user_id or "slack_imagine",
                )
            except Exception as exc:  # noqa: BLE001
                logger.warning("slack /imagine usage reply failed: %s", exc)
            return
        try:
            out = await asyncio.to_thread(generate_images_from_prompt, raw)
        except Exception as exc:  # noqa: BLE001
            logger.exception("slack /imagine generation failed: %s", exc)
            try:
                await asyncio.to_thread(
                    _post_reply,
                    token=token,
                    channel=channel_id,
                    text_out=f"Image generation failed: {exc!s}"[:500],
                    thread_ts=None,
                    blocks=None,
                    app_uid=user_id or "slack_imagine",
                )
            except Exception as exc2:  # noqa: BLE001
                logger.warning("slack /imagine error reply failed: %s", exc2)
            return
        if not out.get("ok"):
            err = str(out.get("error") or out.get("code") or "failed")
            try:
                await asyncio.to_thread(
                    _post_reply,
                    token=token,
                    channel=channel_id,
                    text_out=err[:39000],
                    thread_ts=None,
                    blocks=None,
                    app_uid=user_id or "slack_imagine",
                )
            except Exception as exc:  # noqa: BLE001
                logger.warning("slack /imagine err reply failed: %s", exc)
            return
        url, raw_b = first_image_payload_for_telegram(out)
        if url:
            blocks: list[dict[str, Any]] = [
                {"type": "image", "image_url": str(url), "alt_text": "Generated image"},
            ]
            try:
                await asyncio.to_thread(
                    _post_reply,
                    token=token,
                    channel=channel_id,
                    text_out="Generated image",
                    thread_ts=None,
                    blocks=blocks,
                    app_uid=user_id or "slack_imagine",
                )
            except Exception as exc:  # noqa: BLE001
                logger.warning("slack /imagine image post failed: %s", exc)
            return
        if raw_b is not None:
            try:
                await asyncio.to_thread(
                    slack_files_upload,
                    token,
                    channel=channel_id,
                    content=raw_b,
                    filename="generated.png",
                    initial_comment="Generated image",
                    rate_limit_user_id=user_id,
                )
            except Exception as exc:  # noqa: BLE001
                logger.warning("slack /imagine file upload failed: %s", exc)
            return
        try:
            await asyncio.to_thread(
                _post_reply,
                token=token,
                channel=channel_id,
                text_out="Generation returned no image data.",
                thread_ts=None,
                blocks=None,
                app_uid=user_id or "slack_imagine",
            )
        except Exception as exc:  # noqa: BLE001
            logger.warning("slack /imagine empty reply failed: %s", exc)


__all__ = ["register_slack_handlers"]
