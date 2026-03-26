"""
Feature engineering pipeline — 85+ features, zero lookahead leakage.
All features are computed from past data only.
"""
import numpy as np
import pandas as pd
from sniper.indicators.signal_scorer import enrich_dataframe
from sniper.utils.time_utils import is_asian_session, is_london_session, is_ny_session


def build_features(df: pd.DataFrame) -> pd.DataFrame:
    """
    Takes raw OHLCV dataframe, returns feature matrix.
    All NaN rows (first ~50 due to rolling windows) are dropped at the end.
    """
    df = enrich_dataframe(df.copy())

    close = df["close"]
    high = df["high"]
    low = df["low"]
    volume = df["volume"]

    # --- Price action features ---
    for n in [1, 3, 5, 10, 20]:
        df[f"log_return_{n}"] = np.log(close / close.shift(n))

    for n in [5, 10, 20]:
        df[f"rolling_vol_{n}"] = df["log_return_1"].rolling(n).std()

    df["hl_range_atr"] = (high - low) / df["atr"].replace(0, np.nan)
    df["body_size"] = abs(close - df["open"]) / close
    df["upper_wick"] = (high - close.combine(df["open"], max)) / close
    df["lower_wick"] = (close.combine(df["open"], min) - low) / close
    df["gap"] = (df["open"] - close.shift(1)) / close.shift(1)

    # --- Indicator features (already added by enrich_dataframe) ---
    # RSI
    df["rsi_change"] = df["rsi"].diff()

    # MACD histogram normalized
    df["macd_hist_norm"] = df["macd_hist"] / close

    # EMA distances already added as ema_fast_dist, ema_slow_dist, ema_trend_dist

    # BB %B and bandwidth already added

    # Volume ratio
    df["vol_ratio"] = volume / volume.rolling(20).mean()

    # --- Time features (sine/cosine encoded to avoid ordinal bias) ---
    if isinstance(df.index, pd.DatetimeIndex):
        hour = df.index.hour
        dow = df.index.dayofweek
        df["hour_sin"] = np.sin(2 * np.pi * hour / 24)
        df["hour_cos"] = np.cos(2 * np.pi * hour / 24)
        df["dow_sin"] = np.sin(2 * np.pi * dow / 7)
        df["dow_cos"] = np.cos(2 * np.pi * dow / 7)
        df["is_asian"] = [int(is_asian_session(ts)) for ts in df.index]
        df["is_london"] = [int(is_london_session(ts)) for ts in df.index]
        df["is_ny"] = [int(is_ny_session(ts)) for ts in df.index]
    else:
        for col in ["hour_sin", "hour_cos", "dow_sin", "dow_cos", "is_asian", "is_london", "is_ny"]:
            df[col] = 0.0

    # --- Lag features ---
    for col in ["rsi", "macd_hist", "log_return_1", "atr_pct", "vol_ratio"]:
        for lag in [1, 2, 3, 5]:
            if col in df.columns:
                df[f"{col}_lag{lag}"] = df[col].shift(lag)

    # --- Cross features ---
    df["ema_cross"] = (df["ema_fast"] - df["ema_slow"]) / close
    df["di_diff"] = df["adx_pos"] - df["adx_neg"]

    # Select only numeric feature columns (drop raw price columns)
    exclude = {"open", "high", "low", "close", "volume",
               "ema_fast", "ema_slow", "ema_trend",
               "bb_upper", "bb_lower", "bb_mid",
               "kc_upper", "kc_lower", "kc_mid",
               "obv", "obv_ema", "vwap", "volume_ma20",
               "macd", "macd_signal"}

    feature_cols = [c for c in df.columns if c not in exclude]
    result = df[feature_cols].copy()
    result = result.replace([np.inf, -np.inf], np.nan)
    result = result.dropna()
    return result


FEATURE_COLUMNS = None  # Set after first fit — enforces consistent ordering


def get_feature_columns(df: pd.DataFrame) -> list[str]:
    """Return the ordered list of feature column names."""
    return list(build_features(df).columns)
