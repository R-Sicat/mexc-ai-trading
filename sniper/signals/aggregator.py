"""
Weighted confidence aggregation from all 4 signal sources.
Only counts signal strength if that source agrees on direction.
"""
from dataclasses import dataclass
from config.settings import settings
from sniper.utils.math_utils import clamp
from sniper.monitoring.logger import get_logger

logger = get_logger(__name__)

FULL_ALIGNMENT_BONUS = 0.05
MIN_AGREEING_SOURCES = 2  # NEUTRAL sources abstain; require 2 active agreeing sources


@dataclass
class SignalResult:
    direction: str   # LONG, SHORT, NEUTRAL
    strength: float  # 0.0 to 1.0
    confidence: float
    tech_direction: str
    tech_strength: float
    ml_direction: str
    ml_strength: float
    pattern_direction: str
    pattern_strength: float
    sentiment_direction: str
    sentiment_strength: float
    agreeing_sources: int
    details: dict


def aggregate_signals(
    tech: tuple[str, float],
    ml: tuple[str, float],
    pattern: tuple[str, float],
    sentiment: tuple[str, float],
) -> SignalResult:
    """
    Combine all 4 signal sources into a final confidence score.

    Args:
        tech: (direction, strength) from technical indicators
        ml: (direction, strength) from ML model
        pattern: (direction, strength) from candlestick patterns
        sentiment: (direction, strength) from sentiment analysis

    Returns:
        SignalResult with final direction and confidence score
    """
    t_dir, t_str = tech
    m_dir, m_str = ml
    p_dir, p_str = pattern
    s_dir, s_str = sentiment

    sources = [
        ("technical", t_dir, t_str, settings.WEIGHT_TECHNICAL),
        ("ml", m_dir, m_str, settings.WEIGHT_ML),
        ("pattern", p_dir, p_str, settings.WEIGHT_PATTERNS),
        ("sentiment", s_dir, s_str, settings.WEIGHT_SENTIMENT),
    ]

    # NEUTRAL sources abstain — only count active (LONG/SHORT) votes
    active_sources = [(n, d, s, w) for n, d, s, w in sources if d != "NEUTRAL"]
    long_votes = sum(1 for _, d, _, _ in active_sources if d == "LONG")
    short_votes = sum(1 for _, d, _, _ in active_sources if d == "SHORT")
    total_active = len(active_sources)

    # Determine consensus direction from active sources only
    if long_votes > short_votes:
        consensus = "LONG"
        agreeing = long_votes
    elif short_votes > long_votes:
        consensus = "SHORT"
        agreeing = short_votes
    else:
        return SignalResult(
            direction="NEUTRAL", strength=0.0, confidence=0.0,
            tech_direction=t_dir, tech_strength=t_str,
            ml_direction=m_dir, ml_strength=m_str,
            pattern_direction=p_dir, pattern_strength=p_str,
            sentiment_direction=s_dir, sentiment_strength=s_str,
            agreeing_sources=0,
            details={"reason": "no_consensus", "long_votes": long_votes, "short_votes": short_votes},
        )

    # Compute weighted confidence normalized by active source weights
    agreeing_weight = sum(w for _, d, _, w in sources if d == consensus)
    total_weight = sum(w for _, d, _, w in sources if d != "NEUTRAL")

    raw_confidence = 0.0
    for name, direction, strength, weight in sources:
        if direction == consensus:
            raw_confidence += strength * weight

    # Normalize so NEUTRAL abstentions don't suppress confidence
    if total_weight > 0:
        confidence = raw_confidence / total_weight
    else:
        confidence = 0.0

    # Apply opposing penalty: reduce confidence proportionally to opposing signal weight×strength
    opposing_weight_sum = sum(s * w for _, d, s, w in sources if d not in (consensus, "NEUTRAL"))
    if opposing_weight_sum > 0:
        confidence *= max(0.5, 1.0 - opposing_weight_sum)

    # Require at least MIN_AGREEING_SOURCES active sources agreeing
    if agreeing < MIN_AGREEING_SOURCES:
        confidence = min(confidence, 0.50)

    # Full alignment bonus (all active sources agree)
    if total_active >= 2 and agreeing == total_active:
        confidence += FULL_ALIGNMENT_BONUS

    confidence = clamp(confidence)

    logger.debug(
        "signal_aggregated",
        direction=consensus,
        confidence=round(confidence, 4),
        tech=f"{t_dir}/{t_str:.2f}",
        ml=f"{m_dir}/{m_str:.2f}",
        pattern=f"{p_dir}/{p_str:.2f}",
        sentiment=f"{s_dir}/{s_str:.2f}",
        agreeing=agreeing,
    )

    return SignalResult(
        direction=consensus,
        strength=max(t_str, m_str, p_str, s_str),
        confidence=confidence,
        tech_direction=t_dir, tech_strength=t_str,
        ml_direction=m_dir, ml_strength=m_str,
        pattern_direction=p_dir, pattern_strength=p_str,
        sentiment_direction=s_dir, sentiment_strength=s_str,
        agreeing_sources=agreeing,
        details={
            "long_votes": long_votes,
            "short_votes": short_votes,
            "total_active": total_active,
            "full_alignment": (total_active >= 2 and agreeing == total_active),
        },
    )
