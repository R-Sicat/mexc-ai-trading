import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

import pytest
from sniper.signals.aggregator import aggregate_signals


def test_all_agree_long_high_confidence():
    result = aggregate_signals(
        tech=("LONG", 0.8),
        ml=("LONG", 0.75),
        pattern=("LONG", 0.7),
        sentiment=("LONG", 0.65),
    )
    assert result.direction == "LONG"
    assert result.confidence >= 0.72
    assert result.agreeing_sources == 4


def test_only_two_agree_capped():
    result = aggregate_signals(
        tech=("LONG", 0.9),
        ml=("LONG", 0.9),
        pattern=("SHORT", 0.9),
        sentiment=("SHORT", 0.9),
    )
    assert result.confidence <= 0.55


def test_three_agree_passes_threshold():
    result = aggregate_signals(
        tech=("SHORT", 0.85),
        ml=("SHORT", 0.80),
        pattern=("SHORT", 0.75),
        sentiment=("LONG", 0.90),  # Dissenter
    )
    assert result.direction == "SHORT"
    assert result.agreeing_sources == 3


def test_neutral_signals_return_neutral():
    result = aggregate_signals(
        tech=("NEUTRAL", 0.0),
        ml=("NEUTRAL", 0.0),
        pattern=("NEUTRAL", 0.0),
        sentiment=("NEUTRAL", 0.0),
    )
    assert result.direction == "NEUTRAL"
    assert result.confidence == 0.0


def test_full_alignment_bonus_applied():
    all_agree = aggregate_signals(
        tech=("LONG", 0.8),
        ml=("LONG", 0.8),
        pattern=("LONG", 0.8),
        sentiment=("LONG", 0.8),
    )
    three_agree = aggregate_signals(
        tech=("LONG", 0.8),
        ml=("LONG", 0.8),
        pattern=("LONG", 0.8),
        sentiment=("SHORT", 0.8),
    )
    assert all_agree.confidence > three_agree.confidence
