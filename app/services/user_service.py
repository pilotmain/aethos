from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.repositories.user_repo import UserRepository


class UserService:
    def __init__(self) -> None:
        self.repo = UserRepository()
        self.settings = get_settings()

    def get(self, db: Session, user_id: str):
        return self.repo.get(db, user_id)

    def get_or_create(self, db: Session, user_id: str):
        return self.repo.get_or_create(db, user_id, timezone=self.settings.default_timezone)

    def mark_user_onboarded(self, db: Session, user_id: str) -> None:
        self.repo.clear_new_user_flag(db, user_id)
