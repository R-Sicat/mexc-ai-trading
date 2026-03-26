import uuid
from typing import Optional
from sniper.exchange.client import MEXCClient
from sniper.monitoring.logger import get_logger
from config.settings import settings

logger = get_logger(__name__)


def _paper_order(side: str, contracts: float, price: float = 0.0, order_type: str = "market") -> dict:
    """Simulate an order response for paper trading mode."""
    oid = f"PAPER-{uuid.uuid4().hex[:8].upper()}"
    logger.info(
        "paper_order_simulated",
        order_id=oid,
        type=order_type,
        side=side,
        contracts=contracts,
        price=price,
    )
    return {"id": oid, "average": price, "status": "closed", "paper": True}


class OrderManager:
    def __init__(self, client: MEXCClient):
        self.client = client

    @property
    def _paper(self) -> bool:
        return settings.MEXC_SANDBOX

    async def place_market_order(self, side: str, contracts: float) -> dict:
        if self._paper:
            ticker = await self.client.fetch_ticker()
            return _paper_order(side, contracts, price=float(ticker["last"]))

        order = await self.client.exchange.create_order(
            symbol=settings.SYMBOL,
            type="market",
            side=side,
            amount=contracts,
            params={"positionSide": "LONG" if side == "buy" else "SHORT"},
        )
        logger.info("market_order_placed", side=side, contracts=contracts, order_id=order["id"])
        return order

    async def place_stop_loss(self, side: str, contracts: float, stop_price: float) -> dict:
        if self._paper:
            return _paper_order("sell" if side == "buy" else "buy", contracts, stop_price, "stop_loss")

        close_side = "sell" if side == "buy" else "buy"
        order = await self.client.exchange.create_order(
            symbol=settings.SYMBOL,
            type="stop_market",
            side=close_side,
            amount=contracts,
            params={"stopPrice": stop_price, "reduceOnly": True,
                    "positionSide": "LONG" if side == "buy" else "SHORT"},
        )
        logger.info("stop_loss_placed", close_side=close_side, stop_price=stop_price, order_id=order["id"])
        return order

    async def place_take_profit(self, side: str, contracts: float, tp_price: float) -> dict:
        if self._paper:
            return _paper_order("sell" if side == "buy" else "buy", contracts, tp_price, "take_profit")

        close_side = "sell" if side == "buy" else "buy"
        order = await self.client.exchange.create_order(
            symbol=settings.SYMBOL,
            type="take_profit_market",
            side=close_side,
            amount=contracts,
            params={"stopPrice": tp_price, "reduceOnly": True,
                    "positionSide": "LONG" if side == "buy" else "SHORT"},
        )
        logger.info("take_profit_placed", close_side=close_side, tp_price=tp_price, order_id=order["id"])
        return order

    async def cancel_order(self, order_id: str) -> None:
        if self._paper:
            logger.info("paper_order_cancelled", order_id=order_id)
            return
        try:
            await self.client.exchange.cancel_order(order_id, settings.SYMBOL)
            logger.info("order_cancelled", order_id=order_id)
        except Exception as e:
            logger.warning("cancel_order_failed", order_id=order_id, error=str(e))

    async def fetch_open_orders(self) -> list:
        if self._paper:
            return []
        return await self.client.exchange.fetch_open_orders(settings.SYMBOL)

    async def fetch_positions(self) -> list:
        if self._paper:
            return []  # Position tracker handles paper state internally
        positions = await self.client.exchange.fetch_positions([settings.SYMBOL])
        return [p for p in positions if float(p.get("contracts", 0)) != 0]
