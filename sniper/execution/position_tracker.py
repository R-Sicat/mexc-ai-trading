"""
Live position state tracker — syncs with exchange every 30s.
"""
import asyncio
from dataclasses import dataclass, field
from typing import Optional
from sniper.exchange.client import MEXCClient
from sniper.exchange.order_manager import OrderManager
from sniper.risk.stop_manager import should_move_to_breakeven, calculate_trailing_stop
from sniper.monitoring.logger import get_logger
from config.settings import settings

logger = get_logger(__name__)


@dataclass
class LivePosition:
    trade_id: int
    direction: str
    entry_price: float
    contracts: float
    sl_price: float
    tp_price: float
    sl_order_id: str = ""
    tp_order_id: str = ""
    peak_price: float = 0.0
    atr: float = 0.0
    breakeven_moved: bool = False


class PositionTracker:
    def __init__(self, client: MEXCClient, order_manager: OrderManager):
        self.client = client
        self.order_manager = order_manager
        self.position: Optional[LivePosition] = None
        self._running = False

    def set_position(self, pos: LivePosition) -> None:
        self.position = pos
        if pos:
            self.position.peak_price = pos.entry_price

    async def start_monitoring(self) -> None:
        self._running = True
        while self._running and self.position:
            await asyncio.sleep(30)
            await self._check_position()

    def stop_monitoring(self) -> None:
        self._running = False

    async def _check_position(self) -> None:
        if not self.position:
            return
        pos = self.position

        try:
            ticker = await self.client.fetch_ticker()
            current_price = float(ticker["last"])

            # Update peak price
            if pos.direction == "LONG":
                pos.peak_price = max(pos.peak_price, current_price)
            else:
                pos.peak_price = min(pos.peak_price, current_price)

            # Check break-even
            if not pos.breakeven_moved:
                should_be, new_sl = should_move_to_breakeven(
                    pos.entry_price, current_price, pos.direction, pos.atr
                )
                if should_be and new_sl != pos.sl_price:
                    await self._update_sl(new_sl)
                    pos.breakeven_moved = True
                    logger.info("breakeven_moved", trade_id=pos.trade_id, new_sl=round(new_sl, 2))

            # Check trailing stop
            new_sl, should_update = calculate_trailing_stop(
                pos.entry_price, current_price, pos.peak_price,
                pos.sl_price, pos.direction, pos.atr
            )
            if should_update:
                await self._update_sl(new_sl)
                logger.info("trailing_stop_updated", trade_id=pos.trade_id, new_sl=round(new_sl, 2))

            # Verify exchange position still exists
            live_positions = await self.order_manager.fetch_positions()
            if not live_positions:
                logger.info("position_closed_externally", trade_id=pos.trade_id)
                self.position = None
                self._running = False

        except Exception as e:
            logger.error("position_check_failed", error=str(e))

    async def _update_sl(self, new_sl: float) -> None:
        pos = self.position
        if not pos:
            return
        # Cancel old SL order
        if pos.sl_order_id:
            await self.order_manager.cancel_order(pos.sl_order_id)

        # Place new SL order
        side = "buy" if pos.direction == "LONG" else "sell"
        new_order = await self.order_manager.place_stop_loss(
            side, pos.contracts, new_sl
        )
        pos.sl_price = new_sl
        pos.sl_order_id = new_order.get("id", "")
