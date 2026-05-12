# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2025 AethOS AI

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models import User


class UserRepository:
    def get(self, db: Session, user_id: str) -> User | None:
        return db.scalar(select(User).where(User.id == user_id))

    def get_or_create(self, db: Session, user_id: str, timezone: str) -> User:
        user = self.get(db, user_id)
        if user:
            return user
        import sqlalchemy.exc
        try:
            user = User(id=user_id, timezone=timezone, is_new=True)
            db.add(user)
            db.commit()
            db.refresh(user)
            return user
        except sqlalchemy.exc.IntegrityError:
            db.rollback()
            return self.get(db, user_id)

    def clear_new_user_flag(self, db: Session, user_id: str) -> None:
        user = self.get(db, user_id)
        if user and user.is_new:
            user.is_new = False
            db.add(user)
            db.commit()
