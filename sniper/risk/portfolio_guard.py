"""
Portfolio-level risk controls: daily loss limit, drawdown guard, consecutive loss tracking.
"""
from datetime import date, timezone
from sniper.utils.db import get_daily_pnl
from sniper.monitoring.logger import get_logger
from config.settings import settings

logger = get_logger(__name__)

# In-memory state (reset on bot restart — acceptable for intraday guards)
_session_high_balance: float = 0.0
_consecutive_losses: int = 0
_paper_mode_forced: bool = False


def update_session_high(balance: float) -> None:
    global _session_high_balance
    if balance > _session_high_balance:
        _session_high_balance = balance


def record_trade_result(net_pnl: float) -> None:
    global _consecutive_losses
    if net_pnl < 0:
        _consecutive_losses += 1
    else:
        _consecutive_losses = max(0, _consecutive_losses - 1)
    logger.debug("consecutive_losses", count=_consecutive_losses)


def get_effective_risk_pct() -> float:
    """Reduce risk after 3 consecutive losses."""
    if _consecutive_losses >= 3:
        logger.info("risk_reduced", reason="consecutive_losses", count=_consecutive_losses)
        return 0.5
    return settings.RISK_PER_TRADE_PCT


async def check_portfolio_guards(balance: float) -> tuple[bool, str]:
    """
    Returns (trading_allowed: bool, reason: str).
    """
    global _paper_mode_forced

    update_session_high(balance)

    # Daily loss circuit breaker
    today = date.today().isoformat()
    daily_pnl = await get_daily_pnl(today)
    max_daily_loss = balance * (settings.MAX_DAILY_LOSS_PCT / 100) * -1

    if daily_pnl < max_daily_loss:
        reason = f"daily_loss_circuit_breaker: {daily_pnl:.2f} < {max_daily_loss:.2f}"
        logger.warning("trading_halted", reason=reason)
        return False, reason

    # Drawdown guard: if balance dropped >15% from session high
    if _session_high_balance > 0:
        drawdown = (_session_high_balance - balance) / _session_high_balance
        if drawdown > 0.15:
            _paper_mode_forced = True
            reason = f"drawdown_guard: {drawdown:.1%} from session high"
            logger.warning("paper_mode_forced", reason=reason)
            return False, reason

    return True, ""
