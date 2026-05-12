# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2025 AethOS AI

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models import BrainDump


class BrainDumpRepository:
    def create(self, db: Session, user_id: str, text: str, input_source: str, emotional_state: str | None = None) -> BrainDump:
        dump = BrainDump(
            user_id=user_id,
            input_text=text,
            input_source=input_source,
            emotional_state=emotional_state,
        )
        db.add(dump)
        db.commit()
        db.refresh(dump)
        return dump

    def get(self, db: Session, dump_id: str, user_id: str) -> BrainDump | None:
        return db.scalar(select(BrainDump).where(BrainDump.id == dump_id, BrainDump.user_id == user_id))
