import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

import pytest
from sniper.risk.position_sizer import calculate_position
from sniper.risk.stop_manager import calculate_sl_tp, should_move_to_breakeven


def test_position_size_respects_risk_pct():
    """Risk amount should be approx risk_pct% of balance."""
    sizing = calculate_position(
        balance=10000.0,
        entry_price=2300.0,
        atr=10.0,
        risk_pct_override=1.0,
    )
    expected_risk = 10000.0 * 0.01  # $100
    sl_distance = 10.0 * 1.5  # 15.0
    expected_contracts = expected_risk / sl_distance  # ~6.67
    assert abs(sizing["contracts"] - round(expected_contracts, 2)) < 0.1


def test_position_size_zero_on_zero_atr():
    sizing = calculate_position(balance=10000.0, entry_price=2300.0, atr=0.0)
    assert sizing["contracts"] == 0.0


def test_sl_tp_long_direction():
    sl, tp = calculate_sl_tp(entry_price=2300.0, direction="LONG", atr=10.0)
    assert sl < 2300.0  # SL below entry for LONG
    assert tp > 2300.0  # TP above entry for LONG
    # Check RR ratio
    rr = (tp - 2300.0) / (2300.0 - sl)
    assert abs(rr - 2.0) < 0.1  # Should be 1:2


def test_sl_tp_short_direction():
    sl, tp = calculate_sl_tp(entry_price=2300.0, direction="SHORT", atr=10.0)
    assert sl > 2300.0  # SL above entry for SHORT
    assert tp < 2300.0  # TP below entry for SHORT


def test_breakeven_triggers_correctly():
    # LONG: price must move up by 1x ATR × SL_mult (1.5)
    should, new_sl = should_move_to_breakeven(
        entry_price=2300.0,
        current_price=2315.0,  # 15 above, 1x SL mult * ATR=10 = 15 → triggers
        direction="LONG",
        atr=10.0,
    )
    assert should is True
    assert new_sl > 2300.0  # New SL above entry


def test_breakeven_not_triggered_too_early():
    should, _ = should_move_to_breakeven(
        entry_price=2300.0,
        current_price=2305.0,  # Only 5 above — not enough
        direction="LONG",
        atr=10.0,
    )
    assert should is False
