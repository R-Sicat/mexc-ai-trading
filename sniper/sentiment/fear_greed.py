"""
Fetch Crypto Fear & Greed Index from alternative.me.
Maps extreme fear/greed to gold safe-haven bias.
"""
import aiohttp
from sniper.monitoring.logger import get_logger

logger = get_logger(__name__)

FEAR_GREED_URL = "https://api.alternative.me/fng/?limit=1"


async def fetch_fear_greed() -> dict:
    """
    Returns {'value': int, 'classification': str}
    value: 0 (extreme fear) to 100 (extreme greed)
    """
    try:
        async with aiohttp.ClientSession() as session:
            async with session.get(FEAR_GREED_URL, timeout=aiohttp.ClientTimeout(total=8)) as resp:
                data = await resp.json()
                entry = data["data"][0]
                value = int(entry["value"])
                classification = entry["value_classification"]
                logger.debug("fear_greed_fetched", value=value, classification=classification)
                return {"value": value, "classification": classification}
    except Exception as e:
        logger.warning("fear_greed_fetch_failed", error=str(e))
        return {"value": 50, "classification": "Neutral"}  # Neutral fallback


def fear_greed_signal(value: int, extreme_fear: int = 25, extreme_greed: int = 75) -> tuple[str, float]:
    """
    Gold safe-haven logic:
    - Extreme fear  → gold demand increases → LONG bias
    - Extreme greed → risk-on, gold sells off → SHORT bias
    Returns (direction, strength).
    """
    if value <= extreme_fear:
        strength = (extreme_fear - value) / extreme_fear
        return "LONG", min(1.0, strength)
    if value >= extreme_greed:
        strength = (value - extreme_greed) / (100 - extreme_greed)
        return "SHORT", min(1.0, strength)
    return "NEUTRAL", 0.0
