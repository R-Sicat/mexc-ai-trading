from datetime import datetime, timezone


def utcnow() -> datetime:
    return datetime.now(timezone.utc)


def utcnow_str() -> str:
    return utcnow().isoformat()


def is_asian_session(dt: datetime) -> bool:
    """Asian session: 00:00 - 08:00 UTC"""
    return 0 <= dt.hour < 8


def is_london_session(dt: datetime) -> bool:
    """London session: 07:00 - 16:00 UTC"""
    return 7 <= dt.hour < 16


def is_ny_session(dt: datetime) -> bool:
    """New York session: 13:00 - 22:00 UTC"""
    return 13 <= dt.hour < 22
