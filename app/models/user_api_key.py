# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2025 AethOS AI

import uuid

from sqlalchemy import BigInteger, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from app.core.db import Base
from app.models.base_mixins import TimestampMixin


class UserApiKey(Base, TimestampMixin):
    """Per-Telegram-user encrypted API keys (BYOK). Plain keys are never stored."""

    __tablename__ = "user_api_keys"
    __table_args__ = (
        UniqueConstraint("telegram_user_id", "provider", name="uq_user_api_keys_tg_provider"),
    )

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    telegram_user_id: Mapped[int] = mapped_column(BigInteger, nullable=False, index=True)
    # openai | anthropic
    provider: Mapped[str] = mapped_column(String(32), nullable=False, index=True)
    api_key_encrypted: Mapped[str] = mapped_column(Text, nullable=False)
