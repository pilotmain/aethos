# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2025 AethOS AI

from datetime import datetime

from sqlalchemy import DateTime, func
from sqlalchemy.orm import Mapped, mapped_column


class TimestampMixin:
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=False), default=func.now(), nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=False), default=func.now(), onupdate=func.now(), nullable=False)
