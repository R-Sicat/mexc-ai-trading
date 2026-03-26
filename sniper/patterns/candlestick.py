import pandas as pd
import numpy as np
from dataclasses import dataclass


@dataclass
class Pattern:
    name: str
    direction: str  # LONG or SHORT
    strength: float  # 0.0 to 1.0


def _body(row) -> float:
    return abs(row["close"] - row["open"])


def _upper_wick(row) -> float:
    return row["high"] - max(row["open"], row["close"])


def _lower_wick(row) -> float:
    return min(row["open"], row["close"]) - row["low"]


def _candle_range(row) -> float:
    return row["high"] - row["low"]


def _is_bullish(row) -> bool:
    return row["close"] > row["open"]


def _is_bearish(row) -> bool:
    return row["close"] < row["open"]


def detect_patterns(df: pd.DataFrame) -> list[Pattern]:
    """
    Detect candlestick patterns in the last 3 candles.
    Returns list of Pattern objects found.
    """
    if len(df) < 3:
        return []

    patterns = []
    c0 = df.iloc[-1]   # current
    c1 = df.iloc[-2]   # previous
    c2 = df.iloc[-3]   # two back

    # --- Single-candle patterns ---
    body0 = _body(c0)
    range0 = _candle_range(c0)
    upper0 = _upper_wick(c0)
    lower0 = _lower_wick(c0)

    if range0 > 0:
        body_ratio = body0 / range0

        # Doji
        if body_ratio < 0.1:
            patterns.append(Pattern("Doji", "NEUTRAL", 0.40))

        # Hammer (bullish reversal after downtrend)
        if (
            body_ratio > 0.2
            and lower0 >= body0 * 2
            and upper0 <= body0 * 0.5
            and _is_bullish(c0)
        ):
            patterns.append(Pattern("Hammer", "LONG", 0.70))

        # Inverted Hammer
        if (
            body_ratio > 0.15
            and upper0 >= body0 * 2
            and lower0 <= body0 * 0.5
            and _is_bullish(c0)
        ):
            patterns.append(Pattern("Inverted Hammer", "LONG", 0.60))

        # Shooting Star (bearish reversal)
        if (
            body_ratio > 0.15
            and upper0 >= body0 * 2
            and lower0 <= body0 * 0.5
            and _is_bearish(c0)
        ):
            patterns.append(Pattern("Shooting Star", "SHORT", 0.70))

        # Hanging Man (bearish reversal)
        if (
            body_ratio > 0.2
            and lower0 >= body0 * 2
            and upper0 <= body0 * 0.5
            and _is_bearish(c0)
        ):
            patterns.append(Pattern("Hanging Man", "SHORT", 0.65))

    # --- Two-candle patterns ---
    body1 = _body(c1)
    range1 = _candle_range(c1)

    if range0 > 0 and range1 > 0:
        # Bullish Engulfing
        if (
            _is_bearish(c1)
            and _is_bullish(c0)
            and c0["close"] > c1["open"]
            and c0["open"] < c1["close"]
            and body0 > body1
        ):
            patterns.append(Pattern("Bullish Engulfing", "LONG", 0.90))

        # Bearish Engulfing
        if (
            _is_bullish(c1)
            and _is_bearish(c0)
            and c0["close"] < c1["open"]
            and c0["open"] > c1["close"]
            and body0 > body1
        ):
            patterns.append(Pattern("Bearish Engulfing", "SHORT", 0.90))

        # Bullish Harami
        if (
            _is_bearish(c1)
            and _is_bullish(c0)
            and c0["open"] > c1["close"]
            and c0["close"] < c1["open"]
            and body0 < body1 * 0.6
        ):
            patterns.append(Pattern("Bullish Harami", "LONG", 0.60))

        # Bearish Harami
        if (
            _is_bullish(c1)
            and _is_bearish(c0)
            and c0["open"] < c1["close"]
            and c0["close"] > c1["open"]
            and body0 < body1 * 0.6
        ):
            patterns.append(Pattern("Bearish Harami", "SHORT", 0.60))

        # Piercing Line
        if (
            _is_bearish(c1)
            and _is_bullish(c0)
            and c0["open"] < c1["low"]
            and c0["close"] > (c1["open"] + c1["close"]) / 2
        ):
            patterns.append(Pattern("Piercing Line", "LONG", 0.75))

        # Dark Cloud Cover
        if (
            _is_bullish(c1)
            and _is_bearish(c0)
            and c0["open"] > c1["high"]
            and c0["close"] < (c1["open"] + c1["close"]) / 2
        ):
            patterns.append(Pattern("Dark Cloud Cover", "SHORT", 0.75))

    # --- Three-candle patterns ---
    body2 = _body(c2)

    if range0 > 0 and range1 > 0 and _candle_range(c2) > 0:
        # Morning Star (bullish reversal)
        if (
            _is_bearish(c2)
            and body1 < body2 * 0.5
            and _is_bullish(c0)
            and c0["close"] > (c2["open"] + c2["close"]) / 2
        ):
            patterns.append(Pattern("Morning Star", "LONG", 0.92))

        # Evening Star (bearish reversal)
        if (
            _is_bullish(c2)
            and body1 < body2 * 0.5
            and _is_bearish(c0)
            and c0["close"] < (c2["open"] + c2["close"]) / 2
        ):
            patterns.append(Pattern("Evening Star", "SHORT", 0.92))

        # Three White Soldiers
        if (
            _is_bullish(c2)
            and _is_bullish(c1)
            and _is_bullish(c0)
            and c1["open"] > c2["open"] and c1["close"] > c2["close"]
            and c0["open"] > c1["open"] and c0["close"] > c1["close"]
        ):
            patterns.append(Pattern("Three White Soldiers", "LONG", 0.88))

        # Three Black Crows
        if (
            _is_bearish(c2)
            and _is_bearish(c1)
            and _is_bearish(c0)
            and c1["open"] < c2["open"] and c1["close"] < c2["close"]
            and c0["open"] < c1["open"] and c0["close"] < c1["close"]
        ):
            patterns.append(Pattern("Three Black Crows", "SHORT", 0.88))

    return patterns
