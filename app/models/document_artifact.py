"""Persisted generated documents (per-user; files live under .runtime/generated_documents/)."""

from __future__ import annotations

import json
from typing import Any

from sqlalchemy import JSON, DateTime, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.core.db import Base
from app.models.base_mixins import TimestampMixin

_DEFAULT_META: str = "{}"


class DocumentArtifactModel(Base, TimestampMixin):
    __tablename__ = "document_artifacts"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    owner_user_id: Mapped[str] = mapped_column(String(64), index=True, nullable=False)
    title: Mapped[str] = mapped_column(String(500), nullable=False, default="")
    format: Mapped[str] = mapped_column(String(16), nullable=False, default="md")
    file_path: Mapped[str] = mapped_column(String(2000), nullable=False)
    source_type: Mapped[str] = mapped_column(String(64), nullable=False, default="chat")
    source_ref: Mapped[str | None] = mapped_column(String(256), nullable=True)
    # Small JSON: format version, size bytes, not full body
    metadata_json: Mapped[str] = mapped_column(
        Text,
        nullable=False,
        default=_DEFAULT_META,
    )

    def metadata_dict(self) -> dict[str, Any]:
        try:
            o = json.loads(self.metadata_json or "{}")
        except (json.JSONDecodeError, TypeError, ValueError):
            return {}
        return o if isinstance(o, dict) else {}

    def set_metadata(self, d: dict[str, Any]) -> None:
        self.metadata_json = json.dumps(d, ensure_ascii=False)[:20_000]

