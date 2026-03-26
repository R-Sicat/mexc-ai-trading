"""
Economic calendar blackout — prevents trading around high-impact events.
Uses a hardcoded schedule for known recurring events + optional API.
"""
from datetime import datetime, timezone, timedelta
from sniper.monitoring.logger import get_logger

logger = get_logger(__name__)

# High-impact event keywords that trigger blackout
HIGH_IMPACT_KEYWORDS = [
    "nonfarm", "nfp", "cpi", "fomc", "fed", "interest rate",
    "ppi", "gdp", "unemployment", "payroll", "powell", "inflation"
]

# Known recurring event schedule (UTC weekday, hour, minute)
# Format: (weekday 0=Mon, hour, minute, name)
RECURRING_EVENTS = [
    # US CPI — typically 2nd or 3rd Tuesday of month at 12:30 UTC
    # US NFP — first Friday of month at 12:30 UTC
    # FOMC — ~8 times/year, Wednesday at 18:00 UTC
    # These are approximate — supplement with live API if possible
]

_cached_events: list[dict] = []
_cache_timestamp: datetime | None = None
CACHE_TTL_MINUTES = 60


async def fetch_upcoming_events(hours_ahead: int = 24) -> list[dict]:
    """
    Fetch upcoming high-impact economic events.
    Returns list of {'name': str, 'time': datetime, 'impact': str}.

    Uses Finnhub economic calendar if API key available, else returns empty.
    """
    global _cached_events, _cache_timestamp

    now = datetime.now(timezone.utc)
    if _cache_timestamp and (now - _cache_timestamp).seconds < CACHE_TTL_MINUTES * 60:
        return _cached_events

    events = []
    try:
        from config.settings import settings
        if settings.FINNHUB_API_KEY:
            import aiohttp
            from_dt = now.strftime("%Y-%m-%d")
            to_dt = (now + timedelta(days=2)).strftime("%Y-%m-%d")
            url = f"https://finnhub.io/api/v1/calendar/economic?from={from_dt}&to={to_dt}&token={settings.FINNHUB_API_KEY}"
            async with aiohttp.ClientSession() as session:
                async with session.get(url, timeout=aiohttp.ClientTimeout(total=8)) as resp:
                    data = await resp.json()
                    for event in data.get("economicCalendar", []):
                        if event.get("impact") == "high":
                            events.append({
                                "name": event.get("event", ""),
                                "time": datetime.fromisoformat(event["time"]).replace(tzinfo=timezone.utc),
                                "impact": "high",
                            })
    except Exception as e:
        logger.warning("economic_calendar_fetch_failed", error=str(e))

    _cached_events = events
    _cache_timestamp = now
    return events


async def is_blackout_active(blackout_before: int = 30, blackout_after: int = 30) -> tuple[bool, str]:
    """
    Returns (is_blackout, reason_string).
    Blackout if a high-impact event is within blackout_before minutes or happened within blackout_after minutes.
    """
    events = await fetch_upcoming_events()
    now = datetime.now(timezone.utc)

    for event in events:
        event_time = event["time"]
        minutes_to = (event_time - now).total_seconds() / 60
        minutes_since = (now - event_time).total_seconds() / 60

        if -blackout_after <= minutes_since <= 0 or 0 <= minutes_to <= blackout_before:
            reason = f"Blackout: {event['name']} at {event_time.strftime('%H:%M UTC')}"
            logger.info("blackout_active", reason=reason)
            return True, reason

    return False, ""
