import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

import pytest
import pandas as pd
import numpy as np
from sniper.indicators.signal_scorer import compute_technical_score, enrich_dataframe


def make_df(n=200, trend="up"):
    np.random.seed(42)
    if trend == "up":
        close = 2200 + np.arange(n) * 0.5 + np.random.randn(n) * 2
    elif trend == "down":
        close = 2400 - np.arange(n) * 0.5 + np.random.randn(n) * 2
    else:
        close = 2300 + np.random.randn(n) * 5
    return pd.DataFrame({
        "open": close + np.random.randn(n) * 0.5,
        "high": close + abs(np.random.randn(n)) * 3,
        "low": close - abs(np.random.randn(n)) * 3,
        "close": close,
        "volume": abs(np.random.randn(n)) * 1000 + 5000,
    })


def test_technical_score_returns_valid_direction():
    df = make_df(200, "up")
    direction, strength = compute_technical_score(df)
    assert direction in ("LONG", "SHORT", "NEUTRAL")
    assert 0.0 <= strength <= 1.0


def test_technical_score_uptrend_leans_long():
    df = make_df(200, "up")
    direction, strength = compute_technical_score(df)
    assert direction == "LONG"


def test_technical_score_downtrend_leans_short():
    df = make_df(200, "down")
    direction, strength = compute_technical_score(df)
    assert direction == "SHORT"


def test_enrich_dataframe_adds_indicator_columns():
    df = make_df(200)
    enriched = enrich_dataframe(df)
    for col in ["rsi", "macd_hist", "atr", "bb_pct_b", "obv"]:
        assert col in enriched.columns, f"Missing column: {col}"


def test_technical_score_minimum_rows():
    df = make_df(60)  # Near minimum viable
    direction, strength = compute_technical_score(df)
    assert direction in ("LONG", "SHORT", "NEUTRAL")
