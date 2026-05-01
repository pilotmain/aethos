from datetime import datetime
from zoneinfo import ZoneInfo


def now_in_tz(tz_name: str) -> datetime:
    return datetime.now(ZoneInfo(tz_name)).replace(tzinfo=None)
