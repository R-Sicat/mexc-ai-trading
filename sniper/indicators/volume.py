import pandas as pd
import ta
from sniper.utils.math_utils import clamp


def add_volume_indicators(df: pd.DataFrame) -> pd.DataFrame:
    close = df["close"]
    high = df["high"]
    low = df["low"]
    volume = df["volume"]

    # OBV
    df["obv"] = ta.volume.OnBalanceVolumeIndicator(close, volume).on_balance_volume()
    df["obv_ema"] = df["obv"].ewm(span=10).mean()

    # MFI
    df["mfi"] = ta.volume.MFIIndicator(high, low, close, volume, window=14).money_flow_index()

    # VWAP (rolling 100-candle proxy — avoids cumsum drift over long datasets)
    df["vwap"] = (close * volume).rolling(100).sum() / volume.rolling(100).sum()

    # Volume ratio vs 20-period MA
    df["volume_ma20"] = volume.rolling(20).mean()
    df["volume_ratio"] = volume / df["volume_ma20"]

    return df


def volume_signal(df: pd.DataFrame) -> tuple[str, float]:
    row = df.iloc[-1]
    scores = []

    # OBV trend vs price trend
    if row["obv"] > row["obv_ema"]:
        scores.append(("LONG", 0.6))
    elif row["obv"] < row["obv_ema"]:
        scores.append(("SHORT", 0.6))
    else:
        scores.append(("NEUTRAL", 0.0))

    # MFI
    mfi = row["mfi"]
    if mfi < 20:
        scores.append(("LONG", clamp((20 - mfi) / 20 + 0.3)))
    elif mfi > 80:
        scores.append(("SHORT", clamp((mfi - 80) / 20 + 0.3)))
    else:
        scores.append(("NEUTRAL", 0.0))

    # Price vs VWAP
    if row["close"] > row["vwap"]:
        scores.append(("LONG", 0.55))
    elif row["close"] < row["vwap"]:
        scores.append(("SHORT", 0.55))
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
