"""
ML model training pipeline.
Trains XGBoost + RandomForest with walk-forward cross-validation.
"""
import json
import joblib
import numpy as np
import pandas as pd
from pathlib import Path
from datetime import datetime

from sklearn.model_selection import TimeSeriesSplit
from sklearn.ensemble import RandomForestClassifier
from sklearn.metrics import roc_auc_score, classification_report
from imblearn.over_sampling import SMOTE
import xgboost as xgb

from sniper.ml.features import build_features
from sniper.ml.labels import apply_triple_barrier
from sniper.indicators.signal_scorer import enrich_dataframe
from sniper.monitoring.logger import get_logger

logger = get_logger(__name__)

MODEL_DIR = Path(__file__).parent.parent.parent / "data" / "models"
MODEL_DIR.mkdir(parents=True, exist_ok=True)


def train(df_raw: pd.DataFrame, version: str = None) -> dict:
    """
    Full training pipeline.
    Returns dict with model paths and evaluation metrics.
    """
    version = version or datetime.utcnow().strftime("%Y%m%d_%H%M%S")
    logger.info("training_start", version=version, rows=len(df_raw))

    # 1. Add indicators
    df = enrich_dataframe(df_raw.copy())

    # 2. Triple-barrier labeling
    df = apply_triple_barrier(df)
    df = df.dropna(subset=["label", "atr"])

    # 3. Build features — build from enriched df so index matches exactly
    features = build_features(df)
    # Align: keep only rows present in both features and labeled df
    common_idx = features.index.intersection(df.index)
    features = features.loc[common_idx]
    labels = df.loc[common_idx, "label"].dropna()
    features = features.loc[labels.index]

    # 4. Filter out neutral labels (0) — only train on directional samples
    mask = labels != 0
    X = features[mask].values
    y = ((labels[mask] + 1) / 2).astype(int).values  # -1 → 0, 1 → 1

    if len(X) < 500:
        raise ValueError(f"Not enough labeled samples: {len(X)}. Need at least 500.")

    logger.info("training_samples", total=len(X), pos=y.sum(), neg=(1 - y).sum())

    # 5. Walk-forward cross-validation
    tscv = TimeSeriesSplit(n_splits=5, gap=100)
    xgb_aucs, rf_aucs = [], []

    for fold, (train_idx, val_idx) in enumerate(tscv.split(X)):
        X_tr, X_val = X[train_idx], X[val_idx]
        y_tr, y_val = y[train_idx], y[val_idx]

        # SMOTE if imbalanced
        ratio = y_tr.sum() / len(y_tr)
        if ratio < 0.4 or ratio > 0.6:
            try:
                sm = SMOTE(random_state=42)
                X_tr, y_tr = sm.fit_resample(X_tr, y_tr)
            except Exception:
                pass

        xgb_model = xgb.XGBClassifier(
            n_estimators=300, max_depth=6, learning_rate=0.05,
            subsample=0.8, colsample_bytree=0.8,
            eval_metric="logloss",
            random_state=42, n_jobs=-1,
        )
        xgb_model.fit(X_tr, y_tr, verbose=False)
        xgb_aucs.append(roc_auc_score(y_val, xgb_model.predict_proba(X_val)[:, 1]))

        rf_model = RandomForestClassifier(
            n_estimators=200, max_depth=8, min_samples_leaf=10,
            random_state=42, n_jobs=-1,
        )
        rf_model.fit(X_tr, y_tr)
        rf_aucs.append(roc_auc_score(y_val, rf_model.predict_proba(X_val)[:, 1]))

    mean_xgb_auc = float(np.mean(xgb_aucs))
    mean_rf_auc = float(np.mean(rf_aucs))
    logger.info("cv_results", xgb_auc=round(mean_xgb_auc, 4), rf_auc=round(mean_rf_auc, 4))

    # 6. Final training on all data
    ratio = y.sum() / len(y)
    X_final, y_final = X, y
    if ratio < 0.4 or ratio > 0.6:
        try:
            sm = SMOTE(random_state=42)
            X_final, y_final = sm.fit_resample(X, y)
        except Exception:
            pass

    final_xgb = xgb.XGBClassifier(
        n_estimators=300, max_depth=6, learning_rate=0.05,
        subsample=0.8, colsample_bytree=0.8,
        use_label_encoder=False, eval_metric="logloss",
        random_state=42, n_jobs=-1,
    )
    final_xgb.fit(X_final, y_final, verbose=False)

    final_rf = RandomForestClassifier(
        n_estimators=200, max_depth=8, min_samples_leaf=10,
        random_state=42, n_jobs=-1,
    )
    final_rf.fit(X_final, y_final)

    # 7. Save models
    xgb_path = MODEL_DIR / f"xgb_{version}.ubj"
    rf_path = MODEL_DIR / f"rf_{version}.pkl"
    final_xgb.save_model(str(xgb_path))
    joblib.dump(final_rf, rf_path)

    # 8. Save metadata
    feature_cols = list(features.columns)
    meta = {
        "version": version,
        "trained_at": datetime.utcnow().isoformat(),
        "num_samples": len(X),
        "xgb_auc": mean_xgb_auc,
        "rf_auc": mean_rf_auc,
        "feature_columns": feature_cols,
        "xgb_path": str(xgb_path),
        "rf_path": str(rf_path),
    }
    meta_path = MODEL_DIR / f"meta_{version}.json"
    with open(meta_path, "w") as f:
        json.dump(meta, f, indent=2)

    logger.info("training_complete", version=version, xgb_path=str(xgb_path))
    return meta
