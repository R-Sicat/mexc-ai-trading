import pandas as pd
from sniper.patterns.candlestick import detect_patterns, Pattern
from sniper.utils.math_utils import clamp


def compute_pattern_score(df: pd.DataFrame) -> tuple[str, float]:
    """
    Returns (direction, strength) from candlestick pattern analysis.
    Uses max-strength pattern, penalizes conflicting signals.
    """
    patterns = detect_patterns(df)

    if not patterns:
        return "NEUTRAL", 0.0

    long_patterns = [p for p in patterns if p.direction == "LONG"]
    short_patterns = [p for p in patterns if p.direction == "SHORT"]

    long_max = max((p.strength for p in long_patterns), default=0.0)
    short_max = max((p.strength for p in short_patterns), default=0.0)

    if long_max == 0.0 and short_max == 0.0:
        return "NEUTRAL", 0.0

    # Conflict penalty: if both sides have patterns, reduce strength
    if long_max > 0 and short_max > 0:
        penalty = min(long_max, short_max) * 0.5
        long_max = clamp(long_max - penalty)
        short_max = clamp(short_max - penalty)

    if long_max > short_max:
        return "LONG", long_max
    if short_max > long_max:
        return "SHORT", short_max
    return "NEUTRAL", 0.0


def get_pattern_names(df: pd.DataFrame) -> list[str]:
    return [p.name for p in detect_patterns(df)]
