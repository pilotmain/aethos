from sqlalchemy.orm import Session

from app.repositories.telegram_repo import TelegramRepository


class TelegramService:
    def __init__(self) -> None:
        self.repo = TelegramRepository()

    def link_user(self, db: Session, telegram_user_id: int, chat_id: int, username: str | None) -> str:
        app_user_id = f"tg_{telegram_user_id}"
        self.repo.upsert_link(db, telegram_user_id, app_user_id, chat_id, username)
        return app_user_id

    def get_link(self, db: Session, telegram_user_id: int):
        return self.repo.get_by_telegram_user(db, telegram_user_id)
