"""
Triple-barrier labeling (inspired by Advances in Financial ML, de Prado).
Produces labels consistent with the live trading SL/TP structure.
"""
import numpy as np
import pandas as pd
import yaml
from pathlib import Path

_risk_cfg = yaml.safe_load(
    open(Path(__file__).parent.parent.parent / "config" / "strategy.yaml")
)["risk"]

SL_MULT = _risk_cfg["sl_atr_multiplier"]
TP_MULT = _risk_cfg["tp_atr_multiplier"]
VERTICAL_BARRIER = 20  # Max candles to wait for a barrier hit


def apply_triple_barrier(df: pd.DataFrame) -> pd.DataFrame:
    """
    Returns df with 'label' column:
      1  = upper barrier hit (LONG wins)
     -1  = lower barrier hit (SHORT wins / LONG stopped)
      0  = vertical barrier (timed out, filtered out during training)

    Requires df to have 'close' and 'atr' columns.
    """
    close = df["close"].values
    atr = df["atr"].values
    labels = np.zeros(len(df), dtype=int)

    for i in range(len(df) - VERTICAL_BARRIER - 1):
        entry = close[i]
        barrier_atr = atr[i]

        upper = entry + TP_MULT * barrier_atr
        lower = entry - SL_MULT * barrier_atr

        label = 0
        for j in range(i + 1, min(i + VERTICAL_BARRIER + 1, len(df))):
            if close[j] >= upper:
                label = 1
                break
            if close[j] <= lower:
                label = -1
                break
        labels[i] = label

    df = df.copy()
    df["label"] = labels
    # Mark last VERTICAL_BARRIER rows as NaN (can't label them)
    df.loc[df.index[-VERTICAL_BARRIER:], "label"] = np.nan
    return df
