"""
Download historical OHLCV data from MEXC and save to data/raw/.
Usage:
    python scripts/fetch_history.py --timeframe 15m --days 365
"""
import asyncio
import argparse
import sys
from pathlib import Path
from datetime import datetime, timedelta, timezone

import pandas as pd
import ccxt.async_support as ccxt

sys.path.insert(0, str(Path(__file__).parent.parent))
from config.settings import settings

RAW_DIR = Path(__file__).parent.parent / "data" / "raw"


async def fetch_history(timeframe: str, days: int) -> None:
    RAW_DIR.mkdir(parents=True, exist_ok=True)

    exchange = ccxt.mexc({
        "options": {"defaultType": "swap"},
        "enableRateLimit": True,
    })

    try:
        await exchange.load_markets()
        since = int((datetime.now(timezone.utc) - timedelta(days=days)).timestamp() * 1000)
        symbol = settings.SYMBOL
        all_candles = []

        print(f"Fetching {symbol} {timeframe} — last {days} days...")
        while True:
            batch = await exchange.fetch_ohlcv(symbol, timeframe, since=since, limit=1000)
            if not batch:
                break
            all_candles.extend(batch)
            since = batch[-1][0] + 1
            print(f"  Fetched {len(all_candles)} candles...", end="\r")

            # Stop if we've reached current time
            last_ts = batch[-1][0]
            if last_ts >= int(datetime.now(timezone.utc).timestamp() * 1000) - 60_000:
                break

        df = pd.DataFrame(all_candles, columns=["timestamp", "open", "high", "low", "close", "volume"])
        df["timestamp"] = pd.to_datetime(df["timestamp"], unit="ms", utc=True)
        df.set_index("timestamp", inplace=True)
        df.drop_duplicates(inplace=True)
        df.sort_index(inplace=True)

        sym_safe = settings.SYMBOL.replace("/", "").replace(":", "")
        out_file = RAW_DIR / f"{sym_safe}_{timeframe}_{days}d.csv"
        df.to_csv(out_file)
        print(f"\nSaved {len(df)} candles to {out_file}")

    finally:
        await exchange.close()


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--timeframe", default="15m")
    parser.add_argument("--days", type=int, default=365)
    args = parser.parse_args()
    asyncio.run(fetch_history(args.timeframe, args.days))
