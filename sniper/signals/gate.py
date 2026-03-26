"""
Entry gate — all 7 conditions must pass before a trade is executed.
"""
import pandas as pd
from datetime import date, timezone
from sniper.signals.aggregator import SignalResult
from sniper.utils.db import get_daily_pnl, get_open_trades
from sniper.monitoring.logger import get_logger
from config.settings import settings
import yaml
from pathlib import Path

logger = get_logger(__name__)

_gate_cfg = yaml.safe_load(
    open(Path(__file__).parent.parent.parent / "config" / "strategy.yaml")
)["gate"]


async def check_entry_gate(
    signal: SignalResult,
    df_primary: pd.DataFrame,
    df_htf: pd.DataFrame,
    is_blackout: bool,
    account_balance: float,
) -> tuple[bool, str]:
    """
    Check all 7 entry conditions.
    Returns (passed: bool, reason: str).
    reason is empty string if passed, or the failure reason.
    """

    # 1. Confidence threshold
    if signal.confidence < _gate_cfg["min_confidence"]:
        return False, f"low_confidence:{signal.confidence:.3f}"

    # 2. Economic blackout
    if is_blackout:
        return False, "economic_blackout"

    # 3. Max concurrent trades
    open_trades = await get_open_trades()
    if len(open_trades) >= settings.MAX_CONCURRENT_TRADES:
        return False, f"max_positions_reached:{len(open_trades)}"

    # 4. Daily loss limit
    today = date.today().isoformat()
    daily_pnl = await get_daily_pnl(today)
    max_loss = account_balance * (settings.MAX_DAILY_LOSS_PCT / 100) * -1
    if daily_pnl < max_loss:
        return False, f"daily_loss_limit:{daily_pnl:.2f}"

    # 5. ATR above minimum (not dead flat market)
    current_atr = df_primary["atr"].iloc[-1] if "atr" in df_primary.columns else 0.0
    if current_atr < _gate_cfg["min_atr_usd"]:
        return False, f"atr_too_low:{current_atr:.2f}"

    # 6. Volume above minimum
    if "volume_ratio" in df_primary.columns:
        vol_ratio = df_primary["volume_ratio"].iloc[-1]
        if vol_ratio < _gate_cfg["min_volume_multiplier"]:
            return False, f"low_volume:{vol_ratio:.2f}"

    # 7. HTF trend confirmation (1h timeframe should not oppose signal)
    if _gate_cfg["htf_conflict_block"] and len(df_htf) > 0:
        htf_trend = _get_htf_trend(df_htf)
        if htf_trend and htf_trend != signal.direction and htf_trend != "NEUTRAL":
            return False, f"htf_conflict:{htf_trend}_vs_{signal.direction}"

    logger.info(
        "gate_passed",
        confidence=round(signal.confidence, 4),
        direction=signal.direction,
        atr=round(current_atr, 2),
    )
    return True, ""


def _get_htf_trend(df_htf: pd.DataFrame) -> str:
    """Simple HTF trend: compare close to EMA50 if available, else use last 3 candles."""
    if "ema_trend" in df_htf.columns:
        last = df_htf.iloc[-1]
        if last["close"] > last["ema_trend"]:
            return "LONG"
        elif last["close"] < last["ema_trend"]:
            return "SHORT"
        return "NEUTRAL"

    # Fallback: 3-candle trend
    if len(df_htf) < 3:
        return "NEUTRAL"
    last_3 = df_htf["close"].iloc[-3:]
    if last_3.iloc[-1] > last_3.iloc[0]:
        return "LONG"
    elif last_3.iloc[-1] < last_3.iloc[0]:
        return "SHORT"
    return "NEUTRAL"
