import pandas as pd
import ta
import yaml
from pathlib import Path
from sniper.utils.math_utils import clamp

_cfg = yaml.safe_load(open(Path(__file__).parent.parent.parent / "config" / "strategy.yaml"))["indicators"]


def add_momentum_indicators(df: pd.DataFrame) -> pd.DataFrame:
    close = df["close"]
    high = df["high"]
    low = df["low"]

    # RSI
    df["rsi"] = ta.momentum.RSIIndicator(close, window=_cfg["rsi_period"]).rsi()
    df["rsi_change"] = df["rsi"].diff()

    # Stochastic
    stoch = ta.momentum.StochasticOscillator(
        high, low, close,
        window=_cfg["stoch_k"],
        smooth_window=_cfg["stoch_d"],
    )
    df["stoch_k"] = stoch.stoch()
    df["stoch_d"] = stoch.stoch_signal()

    # CCI
    df["cci"] = ta.trend.CCIIndicator(high, low, close, window=_cfg["cci_period"]).cci()

    # Williams %R
    df["williams_r"] = ta.momentum.WilliamsRIndicator(
        high, low, close, lbp=_cfg["williams_period"]
    ).williams_r()

    return df


def momentum_signal(df: pd.DataFrame) -> tuple[str, float]:
    row = df.iloc[-1]
    scores = []

    # RSI
    rsi = row["rsi"]
    if rsi < _cfg["rsi_oversold"]:
        strength = clamp(((_cfg["rsi_oversold"] - rsi) / _cfg["rsi_oversold"]) * 1.5)
        scores.append(("LONG", strength))
    elif rsi > _cfg["rsi_overbought"]:
        strength = clamp(((rsi - _cfg["rsi_overbought"]) / (100 - _cfg["rsi_overbought"])) * 1.5)
        scores.append(("SHORT", strength))
    else:
        scores.append(("NEUTRAL", 0.0))

    # Stochastic cross
    if row["stoch_k"] > row["stoch_d"] and row["stoch_k"] < 80:
        scores.append(("LONG", 0.6))
    elif row["stoch_k"] < row["stoch_d"] and row["stoch_k"] > 20:
        scores.append(("SHORT", 0.6))
    else:
        scores.append(("NEUTRAL", 0.0))

    # CCI
    cci = row["cci"]
    if cci > 100:
        scores.append(("LONG", clamp((cci - 100) / 100 + 0.3)))
    elif cci < -100:
        scores.append(("SHORT", clamp((abs(cci) - 100) / 100 + 0.3)))
    else:
        scores.append(("NEUTRAL", 0.0))

    # Williams %R
    wr = row["williams_r"]
    if wr < -80:
        scores.append(("LONG", clamp(abs(wr + 80) / 20 * 0.7)))
    elif wr > -20:
        scores.append(("SHORT", clamp((wr + 20) / 20 * 0.7)))
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
