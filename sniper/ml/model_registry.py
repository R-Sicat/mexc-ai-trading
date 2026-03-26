"""
Model registry — tracks which model version is currently active.
"""
import json
from pathlib import Path
from sniper.monitoring.logger import get_logger

logger = get_logger(__name__)

MODEL_DIR = Path(__file__).parent.parent.parent / "data" / "models"
REGISTRY_FILE = MODEL_DIR / "registry.json"


def get_active_model() -> dict | None:
    """Return metadata of the currently active model, or None if none exists."""
    if not REGISTRY_FILE.exists():
        return None
    with open(REGISTRY_FILE) as f:
        registry = json.load(f)
    active_version = registry.get("active")
    if not active_version:
        return None
    meta_path = MODEL_DIR / f"meta_{active_version}.json"
    if not meta_path.exists():
        return None
    with open(meta_path) as f:
        return json.load(f)


def promote_model(version: str, meta: dict) -> bool:
    """
    Promote a new model version to active if it beats the current one.
    Returns True if promoted, False if current model is better.
    """
    current = get_active_model()
    new_auc = (meta["xgb_auc"] + meta["rf_auc"]) / 2

    if current:
        current_auc = (current["xgb_auc"] + current["rf_auc"]) / 2
        if new_auc < current_auc + 0.005:
            logger.info(
                "model_not_promoted",
                new_auc=round(new_auc, 4),
                current_auc=round(current_auc, 4),
            )
            return False

    MODEL_DIR.mkdir(parents=True, exist_ok=True)
    registry = {"active": version}
    with open(REGISTRY_FILE, "w") as f:
        json.dump(registry, f)

    logger.info("model_promoted", version=version, auc=round(new_auc, 4))
    return True
