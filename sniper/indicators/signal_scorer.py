import pandas as pd
from sniper.indicators.trend import add_trend_indicators, trend_signal
from sniper.indicators.momentum import add_momentum_indicators, momentum_signal
from sniper.indicators.volatility import add_volatility_indicators, volatility_signal
from sniper.indicators.volume import add_volume_indicators, volume_signal
from sniper.utils.math_utils import clamp
from sniper.monitoring.logger import get_logger

logger = get_logger(__name__)

# Group weights within technical score
TREND_WEIGHT = 0.40
MOMENTUM_WEIGHT = 0.35
VOLATILITY_WEIGHT = 0.15
VOLUME_WEIGHT = 0.10


def compute_technical_score(df: pd.DataFrame) -> tuple[str, float]:
    """
    Add all indicators to df and compute final technical (direction, strength).
    Returns (direction, strength) where direction in {LONG, SHORT, NEUTRAL}.
    """
    df = df.copy()
    add_trend_indicators(df)
    add_momentum_indicators(df)
    add_volatility_indicators(df)
    add_volume_indicators(df)

    t_dir, t_str = trend_signal(df)
    m_dir, m_str = momentum_signal(df)
    v_dir, v_str = volatility_signal(df)
    vol_dir, vol_str = volume_signal(df)

    # Weighted vote
    long_score = 0.0
    short_score = 0.0

    for direction, strength, weight in [
        (t_dir, t_str, TREND_WEIGHT),
        (m_dir, m_str, MOMENTUM_WEIGHT),
        (v_dir, v_str, VOLATILITY_WEIGHT),
        (vol_dir, vol_str, VOLUME_WEIGHT),
    ]:
        if direction == "LONG":
            long_score += strength * weight
        elif direction == "SHORT":
            short_score += strength * weight

    if long_score == 0 and short_score == 0:
        return "NEUTRAL", 0.0

    final_dir = "LONG" if long_score > short_score else "SHORT"
    final_str = clamp(long_score if final_dir == "LONG" else short_score)

    logger.debug(
        "tech_subgroups",
        trend=f"{t_dir}/{round(t_str,2)}",
        momentum=f"{m_dir}/{round(m_str,2)}",
        volatility=f"{v_dir}/{round(v_str,2)}",
        volume=f"{vol_dir}/{round(vol_str,2)}",
        long_score=round(long_score, 3),
        short_score=round(short_score, 3),
        result=f"{final_dir}/{round(final_str,2)}",
    )
    return final_dir, final_str


def enrich_dataframe(df: pd.DataFrame) -> pd.DataFrame:
    """Add all indicators to a dataframe for feature engineering or display."""
    df = df.copy()
    add_trend_indicators(df)
    add_momentum_indicators(df)
    add_volatility_indicators(df)
    add_volume_indicators(df)
    return df
