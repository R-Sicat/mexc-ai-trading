"""
ATR-based stop loss, take profit, trailing stop, and break-even logic.
"""
import yaml
from pathlib import Path
from sniper.monitoring.logger import get_logger

logger = get_logger(__name__)

_risk_cfg = yaml.safe_load(
    open(Path(__file__).parent.parent.parent / "config" / "strategy.yaml")
)["risk"]


def calculate_sl_tp(entry_price: float, direction: str, atr: float) -> tuple[float, float]:
    """
    Returns (sl_price, tp_price) for a given entry, direction, and ATR.
    """
    sl_dist = atr * _risk_cfg["sl_atr_multiplier"]
    tp_dist = atr * _risk_cfg["tp_atr_multiplier"]

    if direction == "LONG":
        sl_price = entry_price - sl_dist
        tp_price = entry_price + tp_dist
    else:  # SHORT
        sl_price = entry_price + sl_dist
        tp_price = entry_price - tp_dist

    logger.debug(
        "sl_tp_calculated",
        direction=direction,
        entry=round(entry_price, 2),
        sl=round(sl_price, 2),
        tp=round(tp_price, 2),
        rr=round(tp_dist / sl_dist, 2),
    )
    return sl_price, tp_price


def should_move_to_breakeven(
    entry_price: float,
    current_price: float,
    direction: str,
    atr: float,
) -> tuple[bool, float]:
    """
    Returns (should_move, new_sl_price).
    Triggers break-even once profit >= 1x ATR.
    New SL = entry + 0.1x ATR buffer (locks in a tiny profit).
    """
    profit_dist = atr * _risk_cfg["sl_atr_multiplier"]  # Same as SL distance = 1x
    buffer = atr * _risk_cfg.get("breakeven_buffer_atr", 0.1)

    if direction == "LONG":
        profit_reached = current_price >= entry_price + profit_dist
        new_sl = entry_price + buffer
    else:
        profit_reached = current_price <= entry_price - profit_dist
        new_sl = entry_price - buffer

    return profit_reached, new_sl


def calculate_trailing_stop(
    entry_price: float,
    current_price: float,
    peak_price: float,
    current_sl: float,
    direction: str,
    atr: float,
) -> tuple[float, bool]:
    """
    Returns (new_sl_price, should_update).
    Trailing stop activates once profit >= 1.5x ATR.
    Trails by 2.0x ATR from peak.
    """
    activation_dist = atr * _risk_cfg["sl_atr_multiplier"] * 1.0
    trail_dist = atr * _risk_cfg["trailing_stop_atr"]

    if direction == "LONG":
        activated = current_price >= entry_price + activation_dist
        if not activated:
            return current_sl, False
        new_sl = peak_price - trail_dist
        if new_sl > current_sl:
            return new_sl, True
    else:
        activated = current_price <= entry_price - activation_dist
        if not activated:
            return current_sl, False
        new_sl = peak_price + trail_dist
        if new_sl < current_sl:
            return new_sl, True

    return current_sl, False
