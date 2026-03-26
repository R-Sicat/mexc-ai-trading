"""
Rolling performance metrics: win rate, Sharpe, drawdown.
"""
import numpy as np
from sniper.monitoring.logger import get_logger

logger = get_logger(__name__)

_trade_history: list[float] = []  # Net PnL per closed trade


def record_trade(net_pnl: float) -> None:
    _trade_history.append(net_pnl)


def get_win_rate() -> float:
    if not _trade_history:
        return 0.0
    wins = sum(1 for p in _trade_history if p > 0)
    return wins / len(_trade_history)


def get_sharpe(window: int = 30) -> float:
    recent = _trade_history[-window:] if len(_trade_history) >= window else _trade_history
    if len(recent) < 5:
        return 0.0
    arr = np.array(recent)
    std = np.std(arr)
    if std == 0:
        return 0.0
    return float(np.mean(arr) / std * np.sqrt(252))  # Annualized approximation


def get_max_drawdown() -> float:
    if not _trade_history:
        return 0.0
    cumulative = np.cumsum(_trade_history)
    peak = np.maximum.accumulate(cumulative)
    drawdown = peak - cumulative
    return float(np.max(drawdown))


def get_summary() -> dict:
    return {
        "total_trades": len(_trade_history),
        "win_rate": round(get_win_rate(), 4),
        "sharpe_30": round(get_sharpe(30), 2),
        "max_drawdown": round(get_max_drawdown(), 2),
        "total_pnl": round(sum(_trade_history), 2),
    }
