import pandas as pd
import ta
import yaml
from pathlib import Path

_cfg = yaml.safe_load(open(Path(__file__).parent.parent.parent / "config" / "strategy.yaml"))["indicators"]


def add_trend_indicators(df: pd.DataFrame) -> pd.DataFrame:
    """Add EMA, MACD, ADX to dataframe. Returns df with new columns."""
    close = df["close"]
    high = df["high"]
    low = df["low"]

    # EMAs
    df["ema_fast"] = ta.trend.ema_indicator(close, window=_cfg["ema_fast"])
    df["ema_slow"] = ta.trend.ema_indicator(close, window=_cfg["ema_slow"])
    df["ema_trend"] = ta.trend.ema_indicator(close, window=_cfg["ema_trend"])

    # EMA distances (% of price)
    df["ema_fast_dist"] = (close - df["ema_fast"]) / close
    df["ema_slow_dist"] = (close - df["ema_slow"]) / close
    df["ema_trend_dist"] = (close - df["ema_trend"]) / close

    # MACD
    macd = ta.trend.MACD(
        close,
        window_fast=_cfg["macd_fast"],
        window_slow=_cfg["macd_slow"],
        window_sign=_cfg["macd_signal"],
    )
    df["macd"] = macd.macd()
    df["macd_signal"] = macd.macd_signal()
    df["macd_hist"] = macd.macd_diff()
    df["macd_hist_slope"] = df["macd_hist"].diff()

    # ADX
    adx = ta.trend.ADXIndicator(high, low, close, window=_cfg["adx_period"])
    df["adx"] = adx.adx()
    df["adx_pos"] = adx.adx_pos()
    df["adx_neg"] = adx.adx_neg()

    return df


def trend_signal(df: pd.DataFrame) -> tuple[str, float]:
    """
    Returns (direction, strength) for the latest candle based on trend indicators.
    direction: 'LONG', 'SHORT', or 'NEUTRAL'
    strength: 0.0 to 1.0
    """
    row = df.iloc[-1]
    scores = []

    # EMA 9/21 cross
    if row["ema_fast"] > row["ema_slow"]:
        sep = abs(row["ema_fast_dist"] - row["ema_slow_dist"])
        scores.append(("LONG", min(1.0, sep * 50 + 0.3)))
    elif row["ema_fast"] < row["ema_slow"]:
        sep = abs(row["ema_fast_dist"] - row["ema_slow_dist"])
        scores.append(("SHORT", min(1.0, sep * 50 + 0.3)))
    else:
        scores.append(("NEUTRAL", 0.0))

    # Price vs trend EMA
    if row["close"] > row["ema_trend"]:
        scores.append(("LONG", 0.6))
    elif row["close"] < row["ema_trend"]:
        scores.append(("SHORT", 0.6))
    else:
        scores.append(("NEUTRAL", 0.0))

    # MACD histogram direction + momentum
    if row["macd_hist"] > 0 and row["macd_hist_slope"] > 0:
        scores.append(("LONG", min(1.0, abs(row["macd_hist"]) / (row["close"] * 0.001) + 0.3)))
    elif row["macd_hist"] < 0 and row["macd_hist_slope"] < 0:
        scores.append(("SHORT", min(1.0, abs(row["macd_hist"]) / (row["close"] * 0.001) + 0.3)))
    else:
        scores.append(("NEUTRAL", 0.0))

    # ADX trend strength + direction
    adx_val = row["adx"]
    if adx_val > _cfg["adx_threshold"]:
        adx_strength = min(1.0, (adx_val - _cfg["adx_threshold"]) / 25 + 0.5)
        if row["adx_pos"] > row["adx_neg"]:
            scores.append(("LONG", adx_strength))
        else:
            scores.append(("SHORT", adx_strength))
    else:
        scores.append(("NEUTRAL", 0.0))

    return _aggregate_scores(scores)


def _aggregate_scores(scores: list) -> tuple[str, float]:
    long_score = sum(s for d, s in scores if d == "LONG")
    short_score = sum(s for d, s in scores if d == "SHORT")
    active = sum(1 for d, s in scores if d != "NEUTRAL")
    if active == 0:
        return "NEUTRAL", 0.0
    if long_score > short_score:
        return "LONG", long_score / active
    return "SHORT", short_score / active
