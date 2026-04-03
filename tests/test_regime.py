"""
Tests for RegimeDetector (utils/regime.py).
All tests are self-contained with no network calls.
"""

import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import pytest
from utils.regime import RegimeDetector


class MockConfig:
    REGIME_ADX_PERIOD = 14
    REGIME_MIN_ADX = 25.0


def make_detector():
    return RegimeDetector(MockConfig())


# ── OHLC helper ───────────────────────────────────────────────────────────────

def make_trending_ohlc(n=60, start=100.0, step=2.0):
    """
    Generate n candles with a steady uptrend.
    A strong directional move should produce high ADX.
    """
    candles = []
    price = start
    for _ in range(n):
        candles.append({
            'open':  price,
            'high':  price + 1.5,
            'low':   price - 0.5,
            'close': price + step,
        })
        price += step
    return candles


def make_ranging_ohlc(n=60, center=100.0, amplitude=1.0):
    """
    Generate n choppy sideways candles (alternating up/down by amplitude).
    Low directional movement → low ADX.
    """
    import math
    candles = []
    for i in range(n):
        # Oscillate around center
        price = center + amplitude * math.sin(i * 0.8)
        candles.append({
            'open':  price,
            'high':  price + 0.3,
            'low':   price - 0.3,
            'close': price + amplitude * math.sin((i + 1) * 0.8) - price,
        })
    # Use simpler approach: alternating up/down by tiny amounts
    candles = []
    direction = 1
    price = center
    for i in range(n):
        move = amplitude * direction
        high = price + abs(move) + 0.1
        low  = price - abs(move) - 0.1
        close = price + move * 0.1  # very small net move
        candles.append({
            'open':  price,
            'high':  max(price, close) + 0.1,
            'low':   min(price, close) - 0.1,
            'close': close,
        })
        price = close
        direction *= -1  # flip direction every candle
    return candles


# ── test_adx_trending ─────────────────────────────────────────────────────────

def test_adx_trending():
    """
    Feed strong directional OHLC data → ADX > 25, regime = 'trending'.
    """
    det = make_detector()
    ohlc = make_trending_ohlc(n=60, step=3.0)
    adx = det.calculate_adx(ohlc, period=14)

    assert adx is not None, "ADX should not be None for 60 candles"
    assert adx > 25, f"Expected ADX > 25 for trending data, got {adx:.2f}"

    result = det.detect_regime(ohlc)
    assert result['regime'] == 'trending', f"Expected 'trending', got {result['regime']}"
    assert result['adx'] > 25


# ── test_adx_ranging ──────────────────────────────────────────────────────────

def test_adx_ranging():
    """
    Feed choppy sideways OHLC data → ADX < 25, regime = 'ranging' or 'transitional'.
    """
    det = make_detector()
    ohlc = make_ranging_ohlc(n=60, amplitude=0.2)
    adx = det.calculate_adx(ohlc, period=14)

    assert adx is not None, "ADX should not be None for 60 candles"
    assert adx < 25, f"Expected ADX < 25 for ranging data, got {adx:.2f}"

    result = det.detect_regime(ohlc)
    assert result['regime'] in ('ranging', 'transitional'), (
        f"Expected 'ranging' or 'transitional', got {result['regime']}"
    )


# ── test_adx_insufficient_data ────────────────────────────────────────────────

def test_adx_insufficient_data():
    """
    Feed fewer than 15 candles → calculate_adx returns None.
    """
    det = make_detector()
    # ADX period is 14; we need at least 14+1 candles
    short_ohlc = make_trending_ohlc(n=10)
    adx = det.calculate_adx(short_ohlc, period=14)
    assert adx is None, f"Expected None for <15 candles, got {adx}"


# ── test_should_enter_trending ────────────────────────────────────────────────

def test_should_enter_trending():
    """
    ADX above threshold with trending data → should_enter returns (True, ...).
    """
    det = make_detector()
    ohlc = make_trending_ohlc(n=60, step=3.0)
    ok, msg = det.should_enter(ohlc)
    assert ok is True, f"should_enter should return True for trending data, got: {msg}"
    assert 'trending' in msg.lower() or 'ADX' in msg, f"Message should mention regime/ADX: {msg}"


# ── test_should_enter_ranging ─────────────────────────────────────────────────

def test_should_enter_ranging():
    """
    ADX below threshold with ranging data → should_enter returns (False, ...).
    """
    det = make_detector()
    ohlc = make_ranging_ohlc(n=60, amplitude=0.2)
    ok, msg = det.should_enter(ohlc)
    assert ok is False, f"should_enter should return False for ranging data, got: {msg}"
    assert 'skip' in msg.lower() or 'ranging' in msg.lower(), (
        f"Message should mention ranging/skip: {msg}"
    )


# ── test_regime_filter_disabled ───────────────────────────────────────────────

def test_regime_filter_disabled():
    """
    When REGIME_FILTER_ENABLED=False, PortfolioManager should not
    instantiate RegimeDetector (regime_detector is None).
    Entries are NOT filtered by regime in that case.
    """
    from unittest.mock import MagicMock, patch
    from risk.portfolio_manager import PortfolioManager

    class DisabledConfig:
        REGIME_FILTER_ENABLED = False
        TRAILING_STOP_ENABLED = False
        AUDIT_FILE = '/dev/null'

    mock_engine = MagicMock()
    mock_risk   = MagicMock()
    mock_exch   = MagicMock()
    mock_notif  = MagicMock()

    # exchanges dict
    exchanges = {'kraken': mock_exch}

    pm = PortfolioManager(
        config=DisabledConfig(),
        turtle_engine=mock_engine,
        risk_manager=mock_risk,
        exchanges=exchanges,
        notifier=mock_notif,
    )

    assert pm.regime_detector is None, (
        "regime_detector should be None when REGIME_FILTER_ENABLED=False"
    )
