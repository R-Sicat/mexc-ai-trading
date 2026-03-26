"""
Sentiment analyzer using FinBERT (primary) with VADER fallback.
"""
from sniper.monitoring.logger import get_logger

logger = get_logger(__name__)

_finbert_pipeline = None
_vader = None


def _load_finbert():
    global _finbert_pipeline
    if _finbert_pipeline is not None:
        return True
    try:
        from transformers import pipeline
        _finbert_pipeline = pipeline(
            "text-classification",
            model="ProsusAI/finbert",
            device=-1,  # CPU
            truncation=True,
            max_length=128,
        )
        logger.info("finbert_loaded")
        return True
    except Exception as e:
        logger.warning("finbert_load_failed", error=str(e))
        return False


def _load_vader():
    global _vader
    if _vader is not None:
        return True
    try:
        from vaderSentiment.vaderSentiment import SentimentIntensityAnalyzer
        _vader = SentimentIntensityAnalyzer()
        return True
    except Exception as e:
        logger.warning("vader_load_failed", error=str(e))
        return False


def analyze_headlines(headlines: list[str]) -> float:
    """
    Returns average sentiment score in [-1, 1].
    Positive = bullish for gold, Negative = bearish.
    Uses FinBERT if available, falls back to VADER.
    """
    if not headlines:
        return 0.0

    # Try FinBERT
    if _load_finbert() and _finbert_pipeline:
        try:
            results = _finbert_pipeline(headlines[:20])  # Limit to 20 headlines
            scores = []
            for r in results:
                label = r["label"].lower()
                score = r["score"]
                if label == "positive":
                    scores.append(score)
                elif label == "negative":
                    scores.append(-score)
                else:
                    scores.append(0.0)
            return sum(scores) / len(scores) if scores else 0.0
        except Exception as e:
            logger.warning("finbert_inference_failed", error=str(e))

    # VADER fallback
    if _load_vader() and _vader:
        try:
            scores = [_vader.polarity_scores(h)["compound"] for h in headlines[:20]]
            return sum(scores) / len(scores) if scores else 0.0
        except Exception as e:
            logger.warning("vader_inference_failed", error=str(e))

    return 0.0
