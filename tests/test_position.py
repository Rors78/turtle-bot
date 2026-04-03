"""
Tests for TurtlePosition — pyramiding, stops, P&L, serialization.
All tests are self-contained with no network calls.
"""

import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import pytest
from core.position import TurtlePosition, Unit


def make_pos(symbol='BTC/USDT', system=1):
    """Fresh empty TurtlePosition."""
    return TurtlePosition(symbol=symbol, exchange='kraken', system=system)


# ─── add_unit / ATR locking ───────────────────────────────────────────────────

def test_add_unit_locks_atr():
    """
    Add first unit with ATR → initial_n is set.
    Add second unit → initial_n unchanged (locked at first entry).
    """
    pos = make_pos()
    pos.add_unit(price=1000.0, quantity=0.1, current_atr=50.0)
    assert abs(pos.initial_n - 50.0) < 1e-9

    # Second unit with different current ATR — should not change initial_n
    pos.add_unit(price=1025.0, quantity=0.1, current_atr=999.0)
    assert abs(pos.initial_n - 50.0) < 1e-9   # unchanged


def test_max_four_units():
    """Adding a 5th unit raises ValueError (Turtle rule)."""
    pos = make_pos()
    for i in range(4):
        pos.add_unit(price=float(1000 + i * 25), quantity=0.1, current_atr=50.0)

    assert pos.unit_count == 4
    with pytest.raises(ValueError, match="4 units"):
        pos.add_unit(price=1200.0, quantity=0.1)


# ─── Pyramiding checks ────────────────────────────────────────────────────────

def test_pyramid_check():
    """
    initial_n=100, last_pyramid_price=1000.
    should_pyramid returns True at 1050 (= 1000 + 0.5*100) and False at 1049.
    """
    pos = make_pos()
    pos.add_unit(price=1000.0, quantity=0.1, current_atr=100.0)
    # last_pyramid_price is set to 1000 after first add_unit

    assert pos.should_pyramid(1050.0) is True     # exactly at threshold
    assert pos.should_pyramid(1060.0) is True     # above threshold
    assert pos.should_pyramid(1049.9) is False    # just below threshold


# ─── Stop movement ────────────────────────────────────────────────────────────

def test_stop_moves_on_pyramid():
    """
    Add unit at $100 with ATR $5 → stop = 100 - 2*5 = $90.
    Add unit at $110 → stop = 110 - 2*5 = $100.
    """
    pos = make_pos()
    pos.add_unit(price=100.0, quantity=1.0, current_atr=5.0)
    assert abs(pos.stop_price - 90.0) < 1e-9

    pos.add_unit(price=110.0, quantity=1.0)   # no new ATR, uses locked initial_n=5
    assert abs(pos.stop_price - 100.0) < 1e-9


# ─── P&L calculation ──────────────────────────────────────────────────────────

def test_pnl_calculation():
    """
    2 units at different prices, verify PnL at a given current price.
    Unit 1: 0.5 BTC at $100 → (150-100)*0.5 = $25
    Unit 2: 0.5 BTC at $120 → (150-120)*0.5 = $15
    Total PnL at $150 = $40
    """
    pos = make_pos()
    pos.add_unit(price=100.0, quantity=0.5, current_atr=5.0)
    pos.add_unit(price=120.0, quantity=0.5)

    pnl = pos.calculate_pnl(current_price=150.0)
    expected = (150.0 - 100.0) * 0.5 + (150.0 - 120.0) * 0.5   # 25 + 15 = 40
    assert abs(pnl - expected) < 1e-9


# ─── Serialization roundtrip ──────────────────────────────────────────────────

def test_serialization_roundtrip():
    """to_dict() then from_dict() — all fields must survive."""
    pos = make_pos(symbol='ETH/USDT', system=2)
    pos.add_unit(price=3000.0, quantity=0.1, current_atr=100.0)
    pos.add_unit(price=3050.0, quantity=0.1)

    d = pos.to_dict()
    restored = TurtlePosition.from_dict(d)

    assert restored.symbol == 'ETH/USDT'
    assert restored.system == 2
    assert restored.unit_count == 2
    assert abs(restored.initial_n - 100.0) < 1e-9
    assert abs(restored.stop_price - pos.stop_price) < 1e-9
    assert abs(restored.avg_entry_price - pos.avg_entry_price) < 1e-9
    assert abs(restored.total_quantity - pos.total_quantity) < 1e-9
    assert abs(restored.last_pyramid_price - 3050.0) < 1e-9
    # Units
    assert abs(restored.units[0].entry_price - 3000.0) < 1e-9
    assert abs(restored.units[1].entry_price - 3050.0) < 1e-9
