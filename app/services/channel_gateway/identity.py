# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2025 AethOS AI

from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.models.channel_user import ChannelUser


def resolve_channel_user(
    db: Session,
    *,
    channel: str,
    channel_user_id: str,
    default_user_id: str,
    display_name: str | None = None,
    username: str | None = None,
) -> str:
    """
    Resolve Nexa `user_id` for a channel-scoped identity.

    If a row exists for (channel, channel_user_id), returns its user_id.
    Otherwise inserts with user_id=default_user_id (e.g. tg_<telegram_id> for Telegram).

    Updates display_name / username when provided and different from stored values.
    Commits when persisting changes (matches TelegramRepository-style commits).
    """
    row = db.scalar(
        select(ChannelUser).where(
            ChannelUser.channel == channel,
            ChannelUser.channel_user_id == channel_user_id,
        )
    )
    if row:
        changed = False
        if display_name is not None and row.display_name != display_name:
            row.display_name = display_name
            changed = True
        if username is not None and row.username != username:
            row.username = username
            changed = True
        if changed:
            db.commit()
            db.refresh(row)
        return row.user_id

    cu = ChannelUser(
        user_id=default_user_id,
        channel=channel,
        channel_user_id=channel_user_id,
        display_name=display_name,
        username=username,
    )
    db.add(cu)
    try:
        db.commit()
        db.refresh(cu)
        return cu.user_id
    except IntegrityError:
        db.rollback()
        again = db.scalar(
            select(ChannelUser).where(
                ChannelUser.channel == channel,
                ChannelUser.channel_user_id == channel_user_id,
            )
        )
        if again:
            return again.user_id
        raise
