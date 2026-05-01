from sqlalchemy import String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from app.core.db import Base
from app.models.base_mixins import TimestampMixin


class ChannelUser(Base, TimestampMixin):
    """Maps (channel, channel_user_id) to Nexa `user_id` (e.g. tg_123). One row per provider identity."""

    __tablename__ = "channel_users"
    __table_args__ = (UniqueConstraint("channel", "channel_user_id", name="uq_channel_user_identity"),)

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    user_id: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    channel: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    channel_user_id: Mapped[str] = mapped_column(String(255), nullable=False, index=True)
    display_name: Mapped[str | None] = mapped_column(String(512), nullable=True)
    username: Mapped[str | None] = mapped_column(String(255), nullable=True)
