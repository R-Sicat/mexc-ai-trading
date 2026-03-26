"""
Async news fetcher for gold-related headlines.
Supports NewsAPI and Finnhub as sources.
"""
import asyncio
import aiohttp
from datetime import datetime, timedelta, timezone
from sniper.monitoring.logger import get_logger
from config.settings import settings

logger = get_logger(__name__)

GOLD_KEYWORDS = ["gold", "XAU", "XAUUSDT", "precious metals", "bullion", "Fed", "inflation", "USD", "DXY"]


async def fetch_newsapi_headlines(hours: int = 4) -> list[str]:
    """Fetch recent gold news from NewsAPI."""
    if not settings.NEWS_API_KEY:
        return []
    from_time = (datetime.now(timezone.utc) - timedelta(hours=hours)).strftime("%Y-%m-%dT%H:%M:%S")
    url = "https://newsapi.org/v2/everything"
    params = {
        "q": "gold OR XAU OR \"precious metals\"",
        "from": from_time,
        "sortBy": "publishedAt",
        "language": "en",
        "pageSize": 50,
        "apiKey": settings.NEWS_API_KEY,
    }
    try:
        async with aiohttp.ClientSession() as session:
            async with session.get(url, params=params, timeout=aiohttp.ClientTimeout(total=10)) as resp:
                data = await resp.json()
                articles = data.get("articles", [])
                headlines = [a["title"] for a in articles if a.get("title")]
                logger.debug("newsapi_fetched", count=len(headlines))
                return headlines
    except Exception as e:
        logger.warning("newsapi_fetch_failed", error=str(e))
        return []


async def fetch_finnhub_headlines(hours: int = 4) -> list[str]:
    """Fetch gold/forex news from Finnhub."""
    if not settings.FINNHUB_API_KEY or settings.FINNHUB_API_KEY == "your_finnhub_key_here":
        return []
    url = "https://finnhub.io/api/v1/news"
    params = {"category": "forex", "token": settings.FINNHUB_API_KEY}
    cutoff = datetime.now(timezone.utc) - timedelta(hours=hours)
    try:
        async with aiohttp.ClientSession() as session:
            async with session.get(url, params=params, timeout=aiohttp.ClientTimeout(total=10)) as resp:
                articles = await resp.json()
                if not isinstance(articles, list):
                    return []
                headlines = []
                for a in articles:
                    if not isinstance(a, dict):
                        continue
                    ts = datetime.fromtimestamp(a.get("datetime", 0), tz=timezone.utc)
                    if ts >= cutoff:
                        headline = a.get("headline", "")
                        if any(kw.lower() in headline.lower() for kw in GOLD_KEYWORDS):
                            headlines.append(headline)
                logger.debug("finnhub_fetched", count=len(headlines))
                return headlines
    except Exception as e:
        logger.warning("finnhub_fetch_failed", error=str(e))
        return []


async def fetch_all_headlines(hours: int = 4) -> list[str]:
    """Fetch from all sources concurrently."""
    results = await asyncio.gather(
        fetch_newsapi_headlines(hours),
        fetch_finnhub_headlines(hours),
        return_exceptions=True,
    )
    headlines = []
    for r in results:
        if isinstance(r, list):
            headlines.extend(r)
    return list(set(headlines))  # Deduplicate
