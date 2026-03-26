import asyncio
from typing import Optional
import ccxt.async_support as ccxt
from sniper.monitoring.logger import get_logger
from config.settings import settings

logger = get_logger(__name__)


class MEXCClient:
    def __init__(self):
        self._exchange: Optional[ccxt.mexc] = None

    async def connect(self) -> None:
        options = {
            "defaultType": "swap",
            "adjustForTimeDifference": True,
        }
        self._exchange = ccxt.mexc({
            "apiKey": settings.MEXC_API_KEY,
            "secret": settings.MEXC_SECRET,
            "options": options,
            "enableRateLimit": True,
        })
        # MEXC does not support a sandbox URL — paper mode is handled internally
        await self._exchange.load_markets()
        logger.info("mexc_connected", paper_mode=settings.MEXC_SANDBOX, symbol=settings.SYMBOL)

    async def close(self) -> None:
        if self._exchange:
            await self._exchange.close()

    @property
    def exchange(self) -> ccxt.mexc:
        if not self._exchange:
            raise RuntimeError("Client not connected. Call connect() first.")
        return self._exchange

    async def fetch_balance(self) -> dict:
        if settings.MEXC_SANDBOX:
            return {"total": 10000.0, "free": 10000.0, "used": 0.0}
        balance = await self.exchange.fetch_balance({"type": "swap"})
        usdt = balance.get("USDT", {})
        return {
            "total": usdt.get("total", 0.0),
            "free": usdt.get("free", 0.0),
            "used": usdt.get("used", 0.0),
        }

    async def fetch_ticker(self) -> dict:
        return await self.exchange.fetch_ticker(settings.SYMBOL)

    async def set_leverage(self, leverage: int) -> None:
        if settings.MEXC_SANDBOX:
            logger.info("leverage_set_skipped_paper_mode", leverage=leverage)
            return
        try:
            # MEXC requires openType (1=isolated, 2=cross) and positionType (1=long, 2=short)
            params = {"openType": 1, "positionType": 1}
            await self.exchange.set_leverage(leverage, settings.SYMBOL, params=params)
            params2 = {"openType": 1, "positionType": 2}
            await self.exchange.set_leverage(leverage, settings.SYMBOL, params=params2)
            logger.info("leverage_set", leverage=leverage)
        except Exception as e:
            logger.warning("leverage_set_failed", error=str(e))
