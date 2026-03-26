"""
Event-driven backtester — replays historical OHLCV through the signal pipeline.
Usage:
    python scripts/backtest.py --csv data/raw/XAUUSDT_15m_365d.csv
"""
import sys
import argparse
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

import pandas as pd
import numpy as np
from sniper.indicators.signal_scorer import compute_technical_score, enrich_dataframe
from sniper.patterns.pattern_scorer import compute_pattern_score
from sniper.ml.predictor import compute_ml_score
from sniper.signals.aggregator import aggregate_signals
from sniper.risk.stop_manager import calculate_sl_tp
from sniper.risk.position_sizer import calculate_position
from config.settings import settings


def run_backtest(df: pd.DataFrame, initial_balance: float = 10000.0) -> dict:
    MIN_LOOKBACK = 60  # candles needed before signals are reliable
    MIN_CONFIDENCE = settings.MIN_CONFIDENCE_SCORE

    balance = initial_balance
    trades = []
    open_trade = None

    print(f"Backtesting {len(df)} candles...")

    for i in range(MIN_LOOKBACK, len(df) - 1):
        window = df.iloc[:i + 1]
        next_candle = df.iloc[i + 1]

        # Manage open trade
        if open_trade:
            close = float(next_candle["close"])
            high = float(next_candle["high"])
            low = float(next_candle["low"])

            hit_sl = hit_tp = False
            if open_trade["direction"] == "LONG":
                hit_sl = low <= open_trade["sl"]
                hit_tp = high >= open_trade["tp"]
            else:
                hit_sl = high >= open_trade["sl"]
                hit_tp = low <= open_trade["tp"]

            if hit_tp or hit_sl:
                exit_price = open_trade["tp"] if hit_tp else open_trade["sl"]
                pnl_per_contract = (exit_price - open_trade["entry"]) * (1 if open_trade["direction"] == "LONG" else -1)
                net_pnl = pnl_per_contract * open_trade["contracts"]
                balance += net_pnl
                trades.append({
                    "entry_candle": open_trade["candle_idx"],
                    "exit_candle": i + 1,
                    "direction": open_trade["direction"],
                    "entry": open_trade["entry"],
                    "exit": exit_price,
                    "pnl": net_pnl,
                    "result": "TP" if hit_tp else "SL",
                    "confidence": open_trade["confidence"],
                })
                open_trade = None

        # Skip if already in a trade
        if open_trade:
            continue

        # Generate signals
        try:
            tech = compute_technical_score(window)
            pattern = compute_pattern_score(window)
            ml = compute_ml_score(window)
            signal = aggregate_signals(tech, ml, pattern, ("NEUTRAL", 0.0))

            if signal.confidence < MIN_CONFIDENCE:
                continue

            atr = window["atr"].iloc[-1] if "atr" in window.columns else 0.0
            if atr <= 0:
                continue

            entry_price = float(window["close"].iloc[-1])
            sl, tp = calculate_sl_tp(entry_price, signal.direction, float(atr))
            sizing = calculate_position(balance, entry_price, float(atr))

            if sizing["contracts"] <= 0:
                continue

            open_trade = {
                "direction": signal.direction,
                "entry": entry_price,
                "sl": sl,
                "tp": tp,
                "contracts": sizing["contracts"],
                "confidence": signal.confidence,
                "candle_idx": i,
            }

        except Exception:
            continue

        if (i + 1) % 100 == 0:
            print(f"  Candle {i+1}/{len(df)}, balance=${balance:.2f}, trades={len(trades)}", end="\r")

    # Performance metrics
    if not trades:
        print("No trades executed.")
        return {}

    pnls = [t["pnl"] for t in trades]
    wins = [t for t in trades if t["pnl"] > 0]
    losses = [t for t in trades if t["pnl"] <= 0]

    win_rate = len(wins) / len(trades) * 100
    total_profit = sum(t["pnl"] for t in wins)
    total_loss = abs(sum(t["pnl"] for t in losses))
    profit_factor = total_profit / total_loss if total_loss > 0 else float("inf")

    # Max drawdown
    cumulative = np.cumsum(pnls)
    peak = np.maximum.accumulate(cumulative)
    drawdown = (peak - cumulative) / (peak + initial_balance)
    max_drawdown = float(np.max(drawdown)) * 100

    results = {
        "initial_balance": initial_balance,
        "final_balance": round(balance, 2),
        "total_return_pct": round((balance - initial_balance) / initial_balance * 100, 2),
        "total_trades": len(trades),
        "win_rate_pct": round(win_rate, 1),
        "profit_factor": round(profit_factor, 2),
        "max_drawdown_pct": round(max_drawdown, 2),
        "avg_win": round(total_profit / len(wins), 2) if wins else 0,
        "avg_loss": round(total_loss / len(losses), 2) if losses else 0,
    }

    print(f"\n{'='*50}")
    print(f"BACKTEST RESULTS")
    print(f"{'='*50}")
    for k, v in results.items():
        print(f"  {k}: {v}")

    return results


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--csv", required=True)
    parser.add_argument("--balance", type=float, default=10000.0)
    args = parser.parse_args()

    df_raw = pd.read_csv(args.csv, index_col=0, parse_dates=True)
    df_enriched = enrich_dataframe(df_raw)
    run_backtest(df_enriched, initial_balance=args.balance)
