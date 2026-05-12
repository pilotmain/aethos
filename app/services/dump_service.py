# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2025 AethOS AI

from sqlalchemy.orm import Session

from app.repositories.dump_repo import BrainDumpRepository


class DumpService:
    def __init__(self) -> None:
        self.repo = BrainDumpRepository()

    def create_dump(self, db: Session, user_id: str, text: str, input_source: str, emotional_state: str | None = None):
        return self.repo.create(db, user_id, text, input_source, emotional_state)

    def get_dump(self, db: Session, dump_id: str, user_id: str):
        return self.repo.get(db, dump_id, user_id)
