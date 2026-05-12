# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2025 AethOS AI

from datetime import datetime
from zoneinfo import ZoneInfo


def now_in_tz(tz_name: str) -> datetime:
    return datetime.now(ZoneInfo(tz_name)).replace(tzinfo=None)
