# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2025 AethOS AI

from sqlalchemy import delete, select
from sqlalchemy.orm import Session

from app.models import UserMemory


class MemoryRepository:
    def get(self, db: Session, user_id: str, key: str) -> UserMemory | None:
        return db.scalar(select(UserMemory).where(UserMemory.user_id == user_id, UserMemory.key == key))

    def upsert(self, db: Session, user_id: str, key: str, value_json: dict, source: str = "system") -> UserMemory:
        row = self.get(db, user_id, key)
        if row:
            row.value_json = value_json
            row.source = source
        else:
            row = UserMemory(user_id=user_id, key=key, value_json=value_json, source=source)
            db.add(row)
        db.commit()
        db.refresh(row)
        return row

    def list_for_user(self, db: Session, user_id: str, prefix: str | None = None) -> list[UserMemory]:
        stmt = select(UserMemory).where(UserMemory.user_id == user_id)
        if prefix:
            stmt = stmt.where(UserMemory.key.startswith(prefix))
        stmt = stmt.order_by(UserMemory.updated_at.desc(), UserMemory.created_at.desc())
        return list(db.scalars(stmt).all())

    def search_notes(self, db: Session, user_id: str, query: str) -> list[UserMemory]:
        q = query.lower().strip()
        rows = self.list_for_user(db, user_id, prefix="memory:")
        matches: list[UserMemory] = []
        for row in rows:
            data = row.value_json or {}
            haystacks = [row.key, str(data.get("content") or ""), str(data.get("summary") or "")]
            if any(q in value.lower() for value in haystacks if value):
                matches.append(row)
        return matches

    def delete(self, db: Session, row: UserMemory) -> None:
        db.delete(row)
        db.commit()

    def delete_many(self, db: Session, user_id: str, keys: list[str]) -> int:
        if not keys:
            return 0
        stmt = delete(UserMemory).where(UserMemory.user_id == user_id, UserMemory.key.in_(keys))
        result = db.execute(stmt)
        db.commit()
        return int(result.rowcount or 0)
