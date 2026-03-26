import pandas as pd
from typing import Optional
from sniper.exchange.client import MEXCClient
from sniper.monitoring.logger import get_logger
from config.settings import settings

logger = get_logger(__name__)


class MarketData:
    def __init__(self, client: MEXCClient):
        self.client = client

    async def fetch_ohlcv(
        self,
        timeframe: Optional[str] = None,
        limit: int = 200,
    ) -> pd.DataFrame:
        tf = timeframe or settings.TIMEFRAME
        raw = await self.client.exchange.fetch_ohlcv(
            settings.SYMBOL, tf, limit=limit
        )
        df = pd.DataFrame(raw, columns=["timestamp", "open", "high", "low", "close", "volume"])
        df["timestamp"] = pd.to_datetime(df["timestamp"], unit="ms", utc=True)
        df.set_index("timestamp", inplace=True)
        logger.debug("ohlcv_fetched", timeframe=tf, rows=len(df))
        return df

    async def fetch_funding_rate(self) -> float:
        try:
            data = await self.client.exchange.fetch_funding_rate(settings.SYMBOL)
            return float(data.get("fundingRate", 0.0))
        except Exception as e:
            logger.warning("funding_rate_fetch_failed", error=str(e))
            return 0.0

    async def fetch_open_interest(self) -> float:
        try:
            data = await self.client.exchange.fetch_open_interest(settings.SYMBOL)
            return float(data.get("openInterestAmount", 0.0))
        except Exception as e:
            logger.warning("oi_fetch_failed", error=str(e))
            return 0.0
