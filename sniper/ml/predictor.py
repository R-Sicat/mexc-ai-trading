"""
Live ML predictor — loads active model and generates probability signals.
"""
import json
import joblib
import numpy as np
import pandas as pd
import xgboost as xgb
from pathlib import Path

from sniper.ml.model_registry import get_active_model
from sniper.ml.features import build_features
from sniper.monitoring.logger import get_logger
from config.settings import settings

logger = get_logger(__name__)

_xgb_model = None
_rf_model = None
_feature_cols: list[str] = []
_loaded_version: str = ""


def _load_models() -> bool:
    global _xgb_model, _rf_model, _feature_cols, _loaded_version
    meta = get_active_model()
    if not meta:
        logger.warning("no_active_model")
        return False

    if meta["version"] == _loaded_version:
        return True  # Already loaded

    try:
        _xgb_model = xgb.XGBClassifier()
        _xgb_model.load_model(meta["xgb_path"])
        _rf_model = joblib.load(meta["rf_path"])
        _feature_cols = meta["feature_columns"]
        _loaded_version = meta["version"]
        logger.info("models_loaded", version=_loaded_version)
        return True
    except Exception as e:
        logger.error("model_load_failed", error=str(e))
        return False


def compute_ml_score(df: pd.DataFrame) -> tuple[str, float]:
    """
    Returns (direction, strength) from ML ensemble.
    direction: 'LONG', 'SHORT', or 'NEUTRAL'
    strength: probability of the predicted direction [0, 1]
    """
    if not _load_models():
        return "NEUTRAL", 0.0

    try:
        features = build_features(df)
        # Use only the last row (current candle) and align to training feature columns
        row = features.iloc[[-1]]
        missing = [c for c in _feature_cols if c not in row.columns]
        for col in missing:
            row[col] = 0.0
        row = row[_feature_cols]

        X = row.values

        # XGBoost probability
        xgb_prob = _xgb_model.predict_proba(X)[0]  # [P(0), P(1)]
        # RandomForest probability
        rf_prob = _rf_model.predict_proba(X)[0]

        # Ensemble: 60% XGBoost + 40% RF
        p_long = 0.6 * xgb_prob[1] + 0.4 * rf_prob[1]
        p_short = 0.6 * xgb_prob[0] + 0.4 * rf_prob[0]

        # Penalize if models strongly disagree
        disagree = abs(xgb_prob[1] - rf_prob[1])
        ml_cfg = {"model_disagree_threshold": 0.25, "model_disagree_penalty": 0.5}
        if disagree > ml_cfg["model_disagree_threshold"]:
            p_long *= ml_cfg["model_disagree_penalty"]
            p_short *= ml_cfg["model_disagree_penalty"]

        threshold = settings.WEIGHT_ML  # Use as minimum strength filter
        if p_long > p_short and p_long > 0.5:
            return "LONG", float(p_long)
        if p_short > p_long and p_short > 0.5:
            return "SHORT", float(p_short)
        return "NEUTRAL", 0.0

    except Exception as e:
        logger.error("ml_prediction_failed", error=str(e))
        return "NEUTRAL", 0.0
