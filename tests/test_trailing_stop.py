"""
Tests for trailing stop logic in TurtlePosition.
All tests are self-contained with no network calls.
"""

import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import pytest
from core.position import TurtlePosition


def make_pos(symbol='BTC/USDT', system=1):
    """Fresh empty TurtlePosition."""
    return TurtlePosition(symbol=symbol, exchange='kraken', system=system)


def make_pos_with_entry(price=100.0, atr=5.0, qty=1.0, trailing=True):
    """TurtlePosition with one unit and optional trailing stop enabled."""
    pos = make_pos()
    pos.add_unit(price=price, quantity=qty, current_atr=atr)
    pos.trailing_stop_enabled = trailing
    # Initialise highest_price_since_entry to entry price
    pos.highest_price_since_entry = price
    return pos


# ── test_trailing_stop_moves_up ───────────────────────────────────────────────

def test_trailing_stop_moves_up():
    """
    Entry at 100, ATR=5 → initial stop = 90 (2*5 below entry).
    Price rises to 120 → trailing stop should move to 120 - 2*5 = 110.
    """
    pos = make_pos_with_entry(price=100.0, atr=5.0)
    initial_stop = pos.stop_price   # 90.0

    pos.update_trailing_stop(current_price=120.0, trailing_distance=2.0)

    # Stop should have moved up from 90 to 110
    assert pos.stop_price > initial_stop, (
        f"Stop should have moved up from {initial_stop}, got {pos.stop_price}"
    )
    assert abs(pos.stop_price - 110.0) < 1e-9, (
        f"Expected stop at 110.0, got {pos.stop_price}"
    )
    assert abs(pos.highest_price_since_entry - 120.0) < 1e-9


# ── test_trailing_stop_never_moves_down ───────────────────────────────────────

def test_trailing_stop_never_moves_down():
    """
    Price peaks at 120 → stop at 110.
    Price drops to 110 → stop must stay at 110 (never lower).
    """
    pos = make_pos_with_entry(price=100.0, atr=5.0)

    # Move stop up to 110
    pos.update_trailing_stop(current_price=120.0, trailing_distance=2.0)
    assert abs(pos.stop_price - 110.0) < 1e-9

    # Price drops — stop must NOT move down
    pos.update_trailing_stop(current_price=110.0, trailing_distance=2.0)
    assert abs(pos.stop_price - 110.0) < 1e-9, (
        f"Stop should stay at 110.0 after price drop, got {pos.stop_price}"
    )

    pos.update_trailing_stop(current_price=105.0, trailing_distance=2.0)
    assert abs(pos.stop_price - 110.0) < 1e-9, (
        f"Stop should stay at 110.0 after further drop, got {pos.stop_price}"
    )


# ── test_trailing_stop_disabled ───────────────────────────────────────────────

def test_trailing_stop_disabled():
    """
    trailing_stop_enabled=False → update_trailing_stop is a no-op.
    Stop must not change even when price moves favorably.
    """
    pos = make_pos_with_entry(price=100.0, atr=5.0, trailing=False)
    original_stop = pos.stop_price   # 90.0

    pos.update_trailing_stop(current_price=150.0, trailing_distance=2.0)

    assert pos.stop_price == original_stop, (
        f"Stop should not change when trailing is disabled: "
        f"expected {original_stop}, got {pos.stop_price}"
    )


# ── test_trailing_stop_serialization ─────────────────────────────────────────

def test_trailing_stop_serialization():
    """
    to_dict() / from_dict() must preserve highest_price_since_entry
    and trailing_stop_enabled.
    """
    pos = make_pos_with_entry(price=100.0, atr=5.0, trailing=True)
    pos.update_trailing_stop(current_price=130.0, trailing_distance=2.0)

    d = pos.to_dict()

    # Fields must be in the dict
    assert 'highest_price_since_entry' in d, "highest_price_since_entry missing from to_dict()"
    assert 'trailing_stop_enabled' in d, "trailing_stop_enabled missing from to_dict()"
    assert abs(d['highest_price_since_entry'] - 130.0) < 1e-9
    assert d['trailing_stop_enabled'] is True

    # Roundtrip
    restored = TurtlePosition.from_dict(d)
    assert abs(restored.highest_price_since_entry - 130.0) < 1e-9
    assert restored.trailing_stop_enabled is True
    # Stop was at 130 - 2*5 = 120
    assert abs(restored.stop_price - 120.0) < 1e-9


# ── test_trailing_stop_with_pyramid ──────────────────────────────────────────

def test_trailing_stop_with_pyramid():
    """
    After pyramiding, the trailing stop should track the highest price
    seen across all units correctly.

    Sequence:
      1. Enter at 100, ATR=5 → stop=90
      2. Pyramid at 102.5 (0.5N move) → stop moves to 102.5-10=92.5
      3. Enable trailing stop, price goes to 130
         → trailing stop = 130 - 2*5 = 120
      4. Price drops to 115 → stop stays at 120
    """
    pos = make_pos()
    pos.add_unit(price=100.0, quantity=1.0, current_atr=5.0)   # stop = 90
    pos.add_unit(price=102.5, quantity=1.0)                      # stop = 92.5

    assert abs(pos.stop_price - 92.5) < 1e-9

    # Enable trailing stop
    pos.trailing_stop_enabled = True
    pos.highest_price_since_entry = 102.5  # initialise from last pyramid

    # Price rises to 130
    pos.update_trailing_stop(current_price=130.0, trailing_distance=2.0)
    assert abs(pos.highest_price_since_entry - 130.0) < 1e-9
    # new_stop = 130 - 2*5 = 120 > 92.5, so stop should be 120
    assert abs(pos.stop_price - 120.0) < 1e-9

    # Price drops to 115 — stop stays at 120
    pos.update_trailing_stop(current_price=115.0, trailing_distance=2.0)
    assert abs(pos.stop_price - 120.0) < 1e-9, (
        f"Stop should stay at 120.0 after price drop, got {pos.stop_price}"
    )
