from sqlalchemy import BigInteger, String
from sqlalchemy.orm import Mapped, mapped_column

from app.core.db import Base
from app.models.base_mixins import TimestampMixin


class TelegramLink(Base, TimestampMixin):
    __tablename__ = "telegram_links"

    telegram_user_id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    app_user_id: Mapped[str] = mapped_column(String(64), unique=True, index=True, nullable=False)
    username: Mapped[str | None] = mapped_column(String(255), nullable=True)
    chat_id: Mapped[int] = mapped_column(BigInteger, nullable=False)
