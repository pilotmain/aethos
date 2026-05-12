# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2025 AethOS AI

from sqlalchemy import desc, select
from sqlalchemy.orm import Session

from app.models import TelegramLink


class TelegramRepository:
    def get_by_telegram_user(self, db: Session, telegram_user_id: int) -> TelegramLink | None:
        return db.scalar(select(TelegramLink).where(TelegramLink.telegram_user_id == telegram_user_id))

    def get_by_app_user(self, db: Session, app_user_id: str) -> TelegramLink | None:
        return db.scalar(select(TelegramLink).where(TelegramLink.app_user_id == app_user_id))

    def upsert_link(self, db: Session, telegram_user_id: int, app_user_id: str, chat_id: int, username: str | None) -> TelegramLink:
        row = self.get_by_telegram_user(db, telegram_user_id)
        if row:
            row.app_user_id = app_user_id
            row.chat_id = chat_id
            row.username = username
        else:
            row = TelegramLink(
                telegram_user_id=telegram_user_id,
                app_user_id=app_user_id,
                chat_id=chat_id,
                username=username,
            )
            db.add(row)
        db.commit()
        db.refresh(row)
        return row

    def list_recent(
        self, db: Session, limit: int = 200
    ) -> list[TelegramLink]:
        return list(
            db.scalars(
                select(TelegramLink).order_by(desc(TelegramLink.created_at)).limit(
                    int(limit)
                )
            ).all()
        )
