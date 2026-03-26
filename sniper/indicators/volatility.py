import pandas as pd
import ta
import yaml
from pathlib import Path
from sniper.utils.math_utils import clamp

_cfg = yaml.safe_load(open(Path(__file__).parent.parent.parent / "config" / "strategy.yaml"))["indicators"]


def add_volatility_indicators(df: pd.DataFrame) -> pd.DataFrame:
    close = df["close"]
    high = df["high"]
    low = df["low"]

    # ATR
    df["atr"] = ta.volatility.AverageTrueRange(
        high, low, close, window=_cfg["atr_period"]
    ).average_true_range()
    df["atr_pct"] = df["atr"] / close

    # Bollinger Bands
    bb = ta.volatility.BollingerBands(
        close, window=_cfg["bb_period"], window_dev=_cfg["bb_std"]
    )
    df["bb_upper"] = bb.bollinger_hband()
    df["bb_lower"] = bb.bollinger_lband()
    df["bb_mid"] = bb.bollinger_mavg()
    df["bb_pct_b"] = bb.bollinger_pband()
    df["bb_bandwidth"] = bb.bollinger_wband()

    # Keltner Channel
    kc = ta.volatility.KeltnerChannel(high, low, close)
    df["kc_upper"] = kc.keltner_channel_hband()
    df["kc_lower"] = kc.keltner_channel_lband()
    df["kc_mid"] = kc.keltner_channel_mband()

    return df


def volatility_signal(df: pd.DataFrame) -> tuple[str, float]:
    row = df.iloc[-1]
    prev = df.iloc[-2] if len(df) > 1 else row
    scores = []

    # BB squeeze then expansion — detect direction of breakout
    bb_bw_current = row["bb_bandwidth"]
    bb_bw_prev = prev["bb_bandwidth"]
    bb_squeeze = bb_bw_current < df["bb_bandwidth"].rolling(20).mean().iloc[-1]

    close = row["close"]
    if not bb_squeeze:
        # Active expansion — directional signal
        if close > row["bb_upper"]:
            scores.append(("LONG", 0.7))
        elif close < row["bb_lower"]:
            scores.append(("SHORT", 0.7))
        else:
            scores.append(("NEUTRAL", 0.0))
    else:
        scores.append(("NEUTRAL", 0.0))

    # Keltner Channel breakout
    if close > row["kc_upper"]:
        scores.append(("LONG", 0.65))
    elif close < row["kc_lower"]:
        scores.append(("SHORT", 0.65))
    else:
        scores.append(("NEUTRAL", 0.0))

    # BB %B position
    pct_b = row["bb_pct_b"]
    if pct_b > 1.0:
        scores.append(("LONG", clamp((pct_b - 1.0) * 2 + 0.4)))
    elif pct_b < 0.0:
        scores.append(("SHORT", clamp(abs(pct_b) * 2 + 0.4)))
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
