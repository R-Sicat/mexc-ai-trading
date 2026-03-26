"""
Position sizing: fixed % risk per trade mapped to contract quantity.
"""
from sniper.utils.math_utils import safe_divide
from sniper.monitoring.logger import get_logger
from config.settings import settings
import yaml
from pathlib import Path

logger = get_logger(__name__)

_risk_cfg = yaml.safe_load(
    open(Path(__file__).parent.parent.parent / "config" / "strategy.yaml")
)["risk"]


def calculate_position(
    balance: float,
    entry_price: float,
    atr: float,
    risk_pct_override: float = None,
) -> dict:
    """
    Calculate position size, SL price, and TP price.

    Returns dict with:
      contracts: float — number of contracts to trade
      sl_price: float — stop loss price
      tp_price: float — take profit price
      risk_amount: float — USD at risk
      sl_distance: float — USD distance from entry to SL
    """
    risk_pct = risk_pct_override if risk_pct_override is not None else settings.RISK_PER_TRADE_PCT
    risk_amount = balance * (risk_pct / 100)

    sl_distance = atr * _risk_cfg["sl_atr_multiplier"]
    tp_distance = atr * _risk_cfg["tp_atr_multiplier"]

    if sl_distance <= 0:
        logger.warning("invalid_sl_distance", atr=atr)
        return {"contracts": 0.0, "sl_price": 0.0, "tp_price": 0.0, "risk_amount": 0.0, "sl_distance": 0.0}

    # Base position size from risk
    contracts = safe_divide(risk_amount, sl_distance)

    # Cap notional exposure — at high leverage (500x), use only 10% of max capacity
    # to avoid instant liquidation on tiny adverse moves
    lev_safety_factor = 0.10 if settings.LEVERAGE >= 200 else 0.80
    max_notional = balance * settings.LEVERAGE * lev_safety_factor
    max_contracts = safe_divide(max_notional, entry_price)
    contracts = min(contracts, max_contracts)

    # Round to reasonable precision (gold futures typically 0.01 contract)
    contracts = round(contracts, 2)

    logger.debug(
        "position_sized",
        balance=round(balance, 2),
        risk_pct=risk_pct,
        risk_amount=round(risk_amount, 2),
        contracts=contracts,
        sl_distance=round(sl_distance, 2),
    )

    return {
        "contracts": contracts,
        "sl_distance": sl_distance,
        "tp_distance": tp_distance,
        "risk_amount": risk_amount,
        # Actual SL/TP prices depend on direction — set by stop_manager
        "sl_price": 0.0,
        "tp_price": 0.0,
    }
