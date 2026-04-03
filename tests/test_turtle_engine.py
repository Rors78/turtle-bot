"""
Tests for TurtleEngine — core math that handles real money.
All tests are self-contained with no network calls.
"""

import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import pytest
from core.turtle_engine import TurtleEngine


class MockConfig:
    ATR_PERIOD = 20
    RISK_PER_TRADE = 0.02
    SYSTEM_1_ENTRY = 20
    SYSTEM_1_EXIT = 10
    SYSTEM_2_ENTRY = 55
    SYSTEM_2_EXIT = 20


def make_candle(open_p, high, low, close, prev_close=None):
    """Helper to make a single valid OHLC candle dict."""
    return {'open': open_p, 'high': high, 'low': low, 'close': close}


def make_candles(n, base_price=100.0, step=1.0):
    """
    Generate n candles of predictable, valid OHLC data.
    Each candle: O=base, H=base+2, L=base-2, C=base (so TR is always 4
    for the first candle and then depends on prev_close drift).
    """
    candles = []
    price = base_price
    for i in range(n):
        candles.append({
            'open': price,
            'high': price + 2.0,
            'low': price - 2.0,
            'close': price,
        })
        price += step
    return candles


@pytest.fixture
def engine():
    return TurtleEngine(MockConfig())


# ─── ATR Tests ────────────────────────────────────────────────────────────────

def test_calculate_atr_basic(engine):
    """
    Feed 25 known OHLC candles, verify ATR matches hand-calculated value.

    Each candle: O=100, H=102, L=98, C=100 — identical and flat so TR
    for every bar i≥1 is max(4, |102-100|, |98-100|) = max(4,2,2) = 4.
    ATR (last 20 TRs) = 4.0.
    """
    candles = make_candles(25, base_price=100.0, step=0.0)  # all same price
    atr = engine.calculate_atr(candles)
    assert atr is not None
    assert abs(atr - 4.0) < 1e-9


def test_calculate_atr_insufficient_data(engine):
    """Feed < 21 candles, verify returns None (need period+1 = 21)."""
    candles = make_candles(20)          # exactly ATR_PERIOD, not ATR_PERIOD+1
    assert engine.calculate_atr(candles) is None

    candles_10 = make_candles(10)
    assert engine.calculate_atr(candles_10) is None


def test_calculate_atr_skips_invalid_candles(engine):
    """
    Include candles with 0 or negative values. Verify they are skipped
    and ATR still calculates from the valid ones.
    """
    # 30 good candles + 5 bad ones spliced in at random positions
    good = make_candles(30, base_price=100.0, step=0.0)

    # Insert invalid candles (zero price) — they should be skipped
    bad1 = {'open': 0, 'high': 0, 'low': 0, 'close': 0}
    bad2 = {'open': 100, 'high': 100, 'low': -5, 'close': 100}
    invalid_candles = good[:5] + [bad1, bad2] + good[5:]

    atr = engine.calculate_atr(invalid_candles)
    # Should still return a valid ATR from the valid candles
    assert atr is not None
    assert atr > 0


def test_position_size_correct_formula(engine):
    """
    Regression test for Bug 1 — position size formula.

    Account=$130, ATR=$2000, price=$84000.
    Correct formula: qty = (130 * 0.02) / 2000 = 0.0013
    Old broken formula would divide by price again:
        (130 * 0.02) / 2000 / 84000  ≈ 1.547e-8  (wrong)
    """
    qty, notional = engine.calculate_position_size(
        account_size=130.0,
        atr=2000.0,
        current_price=84000.0,
    )
    expected_qty = (130.0 * 0.02) / 2000.0   # 0.0013
    assert abs(qty - expected_qty) < 1e-10, (
        f"Got qty={qty:.10f}, expected {expected_qty:.10f}. "
        "This is the Bug 1 regression — formula must be (account*risk)/atr, NOT /atr/price."
    )
    expected_notional = expected_qty * 84000.0
    assert abs(notional - expected_notional) < 1e-6


def test_position_size_zero_atr(engine):
    """ATR of 0 must return (0.0, 0.0) — not divide by zero."""
    qty, notional = engine.calculate_position_size(
        account_size=10_000.0,
        atr=0.0,
        current_price=100.0,
    )
    assert qty == 0.0
    assert notional == 0.0


def test_position_size_respects_exchange_limits(engine):
    """Pass min_order and min_notional limits, verify they're enforced."""
    # min_order clamp: natural qty=0.0001, min_order=0.001
    qty, notional = engine.calculate_position_size(
        account_size=1.0,          # small account
        atr=200.0,
        current_price=10_000.0,
        exchange_limits={'min_order': 0.001, 'max_order': float('inf'), 'min_notional': 0},
    )
    assert qty == 0.001            # clamped to min_order

    # min_notional reject: natural notional is tiny
    qty2, notional2 = engine.calculate_position_size(
        account_size=1.0,
        atr=5000.0,
        current_price=50_000.0,
        exchange_limits={'min_order': 0, 'max_order': float('inf'), 'min_notional': 50.0},
    )
    # natural notional = (1*0.02/5000)*50000 = 0.2 USD — below 50 USD min
    assert qty2 == 0.0
    assert notional2 == 0.0


def test_entry_signal_breakout(engine):
    """
    Feed OHLC with a clear 20-day high breakout. Verify signal is generated.
    """
    # 20 candles with high=105, then current price=110 > 105
    candles = make_candles(20, base_price=100.0, step=0.0)   # all H=102
    # Replace highs to be exactly 105
    for c in candles:
        c['high'] = 105.0

    signal = engine.generate_entry_signal(candles, current_price=110.0, system=1)
    assert signal is not None
    assert signal['signal'] == 'ENTRY'
    assert signal['breakout_level'] == 105.0
    assert signal['current_price'] == 110.0


def test_entry_signal_no_breakout(engine):
    """Price at or below 20-day high — no signal."""
    candles = make_candles(20, base_price=100.0, step=0.0)
    for c in candles:
        c['high'] = 105.0

    # Price exactly at high — not above, so no breakout
    assert engine.generate_entry_signal(candles, current_price=105.0, system=1) is None
    # Price below high
    assert engine.generate_entry_signal(candles, current_price=100.0, system=1) is None


def test_exit_signal_breakdown(engine):
    """Price below 10-day low triggers exit signal."""
    # 10 candles, all with low=90
    candles = make_candles(10, base_price=100.0, step=0.0)
    for c in candles:
        c['low'] = 90.0

    signal = engine.generate_exit_signal(candles, current_price=85.0, system=1)
    assert signal is not None
    assert signal['signal'] == 'EXIT'
    assert signal['breakdown_level'] == 90.0


def test_stop_price_calculation(engine):
    """Entry $100, ATR $5, stop = entry - 2*ATR = $90."""
    stop = engine.calculate_stop_price(entry_price=100.0, atr=5.0)
    assert stop == 90.0


def test_donchian_channels(engine):
    """Verify entry_high and exit_low match expected values from known data."""
    # 55 candles: highs all 110, lows all 90 — except last 10 which have low=80
    candles = []
    for i in range(55):
        low = 80.0 if i >= 45 else 90.0
        candles.append({'open': 100.0, 'high': 110.0, 'low': low, 'close': 100.0})

    channels = engine.get_donchian_channels(candles, entry_period=20, exit_period=10)
    assert channels['entry_high'] == 110.0   # max high of last 20 candles
    assert channels['exit_low'] == 80.0      # min low of last 10 candles (all 80)
