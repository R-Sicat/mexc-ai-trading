"""
Combines all sentiment signals into a single (direction, strength) output.
"""
import asyncio
from sniper.sentiment.news_fetcher import fetch_all_headlines
from sniper.sentiment.analyzer import analyze_headlines
from sniper.sentiment.fear_greed import fetch_fear_greed, fear_greed_signal
from sniper.sentiment.economic_calendar import is_blackout_active
from sniper.utils.math_utils import clamp
from sniper.monitoring.logger import get_logger
import yaml
from pathlib import Path

logger = get_logger(__name__)

_cfg = yaml.safe_load(
    open(Path(__file__).parent.parent.parent / "config" / "strategy.yaml")
)["sentiment"]

# Sub-weights within sentiment score
NEWS_WEIGHT = 0.40
FEAR_GREED_WEIGHT = 0.25
CALENDAR_WEIGHT = 0.25  # Blackout check (binary override)
DXY_WEIGHT = 0.10


async def compute_sentiment_score() -> tuple[str, float, bool, str]:
    """
    Returns (direction, strength, is_blackout, blackout_reason).
    direction: 'LONG', 'SHORT', 'NEUTRAL'
    strength: 0.0 to 1.0
    is_blackout: True if trading should be blocked
    """
    # Run all fetches concurrently
    headlines_task = asyncio.create_task(
        fetch_all_headlines(hours=_cfg["news_lookback_hours"])
    )
    fear_greed_task = asyncio.create_task(fetch_fear_greed())
    blackout_task = asyncio.create_task(
        is_blackout_active(
            blackout_before=_cfg["blackout_minutes_before"],
            blackout_after=_cfg["blackout_minutes_after"],
        )
    )

    headlines, fear_greed_data, (is_blackout, blackout_reason) = await asyncio.gather(
        headlines_task, fear_greed_task, blackout_task
    )

    # Hard blackout — override everything
    if is_blackout and _cfg["high_impact_event_blackout"]:
        return "NEUTRAL", 0.0, True, blackout_reason

    long_score = 0.0
    short_score = 0.0

    # News sentiment
    raw_sentiment = analyze_headlines(headlines)
    # Map [-1, 1] to direction + strength
    if raw_sentiment > 0.1:
        long_score += clamp(raw_sentiment) * NEWS_WEIGHT
    elif raw_sentiment < -0.1:
        short_score += clamp(abs(raw_sentiment)) * NEWS_WEIGHT

    # Fear & Greed
    fg_dir, fg_str = fear_greed_signal(
        fear_greed_data["value"],
        extreme_fear=_cfg["fear_greed_extreme_fear_threshold"],
        extreme_greed=_cfg["fear_greed_extreme_greed_threshold"],
    )
    if fg_dir == "LONG":
        long_score += fg_str * FEAR_GREED_WEIGHT
    elif fg_dir == "SHORT":
        short_score += fg_str * FEAR_GREED_WEIGHT

    # Determine final direction and strength
    total = long_score + short_score
    if total < 0.05:
        return "NEUTRAL", 0.0, False, ""

    if long_score > short_score:
        strength = clamp(long_score / (NEWS_WEIGHT + FEAR_GREED_WEIGHT))
        return "LONG", strength, False, ""

    strength = clamp(short_score / (NEWS_WEIGHT + FEAR_GREED_WEIGHT))
    return "SHORT", strength, False, ""
