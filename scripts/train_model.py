"""
Offline ML model training entry point.
Usage:
    python scripts/train_model.py --csv data/raw/XAUUSDT_15m_365d.csv
"""
import sys
import argparse
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

import pandas as pd
from sniper.ml.trainer import train
from sniper.ml.model_registry import promote_model
from sniper.monitoring.logger import setup_logging, get_logger

setup_logging()
logger = get_logger(__name__)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--csv", required=True, help="Path to OHLCV CSV file")
    parser.add_argument("--version", default=None, help="Model version tag")
    args = parser.parse_args()

    csv_path = Path(args.csv)
    if not csv_path.exists():
        logger.error("csv_not_found", path=str(csv_path))
        sys.exit(1)

    df = pd.read_csv(csv_path, index_col=0, parse_dates=True)
    logger.info("data_loaded", rows=len(df), columns=list(df.columns))

    meta = train(df, version=args.version)
    promoted = promote_model(meta["version"], meta)

    print(f"\nTraining complete:")
    print(f"  Version:  {meta['version']}")
    print(f"  Samples:  {meta['num_samples']}")
    print(f"  XGB AUC:  {meta['xgb_auc']:.4f}")
    print(f"  RF AUC:   {meta['rf_auc']:.4f}")
    print(f"  Promoted: {promoted}")


if __name__ == "__main__":
    main()
