"""
Main async trade engine — orchestrates the full signal → order flow.
Runs on each 15m candle close.
"""
import asyncio
from datetime import datetime, timezone

from sniper.exchange.client import MEXCClient
from sniper.exchange.market_data import MarketData
from sniper.exchange.order_manager import OrderManager
from sniper.indicators.signal_scorer import compute_technical_score, enrich_dataframe
from sniper.patterns.pattern_scorer import compute_pattern_score
from sniper.ml.predictor import compute_ml_score
from sniper.sentiment.sentiment_scorer import compute_sentiment_score
from sniper.signals.aggregator import aggregate_signals
from sniper.signals.gate import check_entry_gate
from sniper.risk.position_sizer import calculate_position
from sniper.risk.stop_manager import calculate_sl_tp
from sniper.risk.portfolio_guard import check_portfolio_guards, get_effective_risk_pct, record_trade_result
from sniper.execution.position_tracker import PositionTracker, LivePosition
from sniper.utils.db import insert_signal, insert_trade, close_trade
from sniper.utils.time_utils import utcnow_str
from sniper.monitoring.logger import get_logger
from dashboard.state import bot_state
from config.settings import settings

logger = get_logger(__name__)


class TradeEngine:
    def __init__(self):
        self.client = MEXCClient()
        self.market_data: MarketData = None
        self.order_manager: OrderManager = None
        self.tracker: PositionTracker = None
        self._running = False

    async def start(self) -> None:
        await self.client.connect()
        await self.client.set_leverage(settings.LEVERAGE)
        self.market_data = MarketData(self.client)
        self.order_manager = OrderManager(self.client)
        self.tracker = PositionTracker(self.client, self.order_manager)
        self._running = True
        bot_state.is_running = True
        bot_state.sandbox = settings.MEXC_SANDBOX
        logger.info("trade_engine_started", symbol=settings.SYMBOL, sandbox=settings.MEXC_SANDBOX)

        while self._running:
            try:
                await self._run_cycle()
            except Exception as e:
                logger.error("cycle_error", error=str(e))
            await self._wait_for_next_candle()

    async def stop(self) -> None:
        self._running = False
        bot_state.is_running = False
        self.tracker.stop_monitoring()
        await self.client.close()

    async def _run_cycle(self) -> None:
        """Full signal → gate → order cycle."""
        logger.info("cycle_start", time=utcnow_str())

        # 1. Fetch market data
        df_primary, df_htf, funding_rate = await asyncio.gather(
            self.market_data.fetch_ohlcv(settings.TIMEFRAME, limit=200),
            self.market_data.fetch_ohlcv(settings.CONFIRM_TIMEFRAME, limit=60),
            self.market_data.fetch_funding_rate(),
        )

        # Add indicators to HTF dataframe for gate check
        df_htf_enriched = enrich_dataframe(df_htf)

        # 2. Generate all 4 signals concurrently
        tech_task = asyncio.create_task(
            asyncio.to_thread(compute_technical_score, df_primary)
        )
        pattern_task = asyncio.create_task(
            asyncio.to_thread(compute_pattern_score, df_primary)
        )
        ml_task = asyncio.create_task(
            asyncio.to_thread(compute_ml_score, df_primary)
        )
        sentiment_task = asyncio.create_task(compute_sentiment_score())

        tech, pattern, ml, sentiment_result = await asyncio.gather(
            tech_task, pattern_task, ml_task, sentiment_task
        )
        sent_dir, sent_str, is_blackout, blackout_reason = sentiment_result

        # 3. Aggregate signals
        signal = aggregate_signals(tech, ml, pattern, (sent_dir, sent_str))

        # 4. Fetch balance for gate/risk checks
        balance_info = await self.client.fetch_balance()
        balance = balance_info["free"]
        bot_state.balance = balance

        # 5. Portfolio guard
        trading_allowed, guard_reason = await check_portfolio_guards(balance)

        # 6. Log signal to DB
        atr = df_primary["atr"].iloc[-1] if "atr" in df_primary.columns else 0.0
        signal_record = {
            "timestamp": utcnow_str(),
            "symbol": settings.SYMBOL,
            "timeframe": settings.TIMEFRAME,
            "direction": signal.direction,
            "confidence": signal.confidence,
            "tech_score": signal.tech_strength,
            "ml_score": signal.ml_strength,
            "pattern_score": signal.pattern_strength,
            "sentiment_score": sent_str,
            "gate_passed": False,
            "gate_fail_reason": None,
            "candle_open": float(df_primary["open"].iloc[-1]),
            "candle_close": float(df_primary["close"].iloc[-1]),
            "atr": float(atr),
        }

        if not trading_allowed:
            signal_record["gate_fail_reason"] = guard_reason
            await insert_signal(signal_record)
            logger.info("trading_blocked", reason=guard_reason)
            return

        # 7. Gate check
        gate_passed, gate_reason = await check_entry_gate(
            signal, df_primary, df_htf_enriched, is_blackout, balance
        )

        signal_record["gate_passed"] = gate_passed
        signal_record["gate_fail_reason"] = gate_reason if not gate_passed else None
        signal_id = await insert_signal(signal_record)
        bot_state.last_signal = signal_record

        if not gate_passed:
            logger.info(
                "gate_blocked",
                reason=gate_reason,
                confidence=round(signal.confidence, 4),
                direction=signal.direction,
                agreeing=signal.agreeing_sources,
                tech=f"{signal.tech_direction}/{round(signal.tech_strength,2)}",
                ml=f"{signal.ml_direction}/{round(signal.ml_strength,2)}",
                pattern=f"{signal.pattern_direction}/{round(signal.pattern_strength,2)}",
                sentiment=f"{signal.sentiment_direction}/{round(signal.sentiment_strength,2)}",
            )
            return

        # 8. Size position
        entry_price = float(df_primary["close"].iloc[-1])
        risk_pct = get_effective_risk_pct()
        sizing = calculate_position(balance, entry_price, float(atr), risk_pct_override=risk_pct)

        if sizing["contracts"] <= 0:
            logger.warning("invalid_position_size", sizing=sizing)
            return

        sl_price, tp_price = calculate_sl_tp(entry_price, signal.direction, float(atr))
        sizing["sl_price"] = sl_price
        sizing["tp_price"] = tp_price

        # 9. Place orders
        side = "buy" if signal.direction == "LONG" else "sell"
        entry_order = await self.order_manager.place_market_order(side, sizing["contracts"])
        actual_entry = float(entry_order.get("average", entry_price))

        sl_order = await self.order_manager.place_stop_loss(side, sizing["contracts"], sl_price)
        tp_order = await self.order_manager.place_take_profit(side, sizing["contracts"], tp_price)

        # 10. Record trade in DB
        trade_id = await insert_trade({
            "signal_id": signal_id,
            "entry_time": utcnow_str(),
            "direction": signal.direction,
            "entry_price": actual_entry,
            "contracts": sizing["contracts"],
            "sl_price": sl_price,
            "tp_price": tp_price,
        })

        # 11. Start position monitoring
        live_pos = LivePosition(
            trade_id=trade_id,
            direction=signal.direction,
            entry_price=actual_entry,
            contracts=sizing["contracts"],
            sl_price=sl_price,
            tp_price=tp_price,
            sl_order_id=sl_order.get("id", ""),
            tp_order_id=tp_order.get("id", ""),
            atr=float(atr),
        )
        self.tracker.set_position(live_pos)
        bot_state.open_position = {
            "direction": signal.direction,
            "entry_price": actual_entry,
            "contracts": sizing["contracts"],
            "sl_price": sl_price,
            "tp_price": tp_price,
        }
        asyncio.create_task(self.tracker.start_monitoring())

        logger.info(
            "trade_opened",
            trade_id=trade_id,
            direction=signal.direction,
            entry=round(actual_entry, 2),
            sl=round(sl_price, 2),
            tp=round(tp_price, 2),
            contracts=sizing["contracts"],
            confidence=round(signal.confidence, 4),
            risk_usd=round(sizing["risk_amount"], 2),
        )

    async def _wait_for_next_candle(self) -> None:
        """Wait until next 15-minute candle close."""
        now = datetime.now(timezone.utc)
        seconds = now.second + now.minute % 15 * 60
        wait = 15 * 60 - seconds + 2  # 2s buffer after candle close
        logger.debug("waiting_for_candle", seconds=wait)
        await asyncio.sleep(wait)
