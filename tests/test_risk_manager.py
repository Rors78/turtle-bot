"""
Tests for RiskManager — emergency stop, position gating, Kraken order validation.
All tests are self-contained with no network calls.
"""

import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from unittest.mock import MagicMock
import pytest

from risk.risk_manager import RiskManager
from core.position import TurtlePosition


class MockConfig:
    MAX_TOTAL_RISK = 0.20
    EMERGENCY_STOP_LOSS = 0.30
    RESERVE_CASH_PCT = 0.10
    MAX_COINS = 3
    MAX_CORRELATED_COINS = 2
    MAX_ALLOCATION = 0.50
    COIN_SECTORS = {
        'BTC': 'L1', 'ETH': 'L1', 'SOL': 'L1',
        'UNI': 'DEFI', 'AAVE': 'DEFI',
    }


@pytest.fixture
def rm():
    return RiskManager(MockConfig())


def _make_open_position(symbol, system=1):
    """Create a minimal open TurtlePosition."""
    pos = TurtlePosition(symbol=symbol, exchange='kraken', system=system)
    pos.add_unit(price=100.0, quantity=1.0, current_atr=5.0)
    return pos


# ─── Emergency Stop ───────────────────────────────────────────────────────────

def test_emergency_stop_triggers(rm):
    """Equity dropped ≥30% → check_emergency_stop returns True."""
    initial = 1000.0
    current = 690.0    # 31% drawdown
    assert rm.check_emergency_stop(current, initial) is True


def test_emergency_stop_no_trigger(rm):
    """Equity dropped only 10% → no emergency stop."""
    initial = 1000.0
    current = 900.0    # 10% drawdown
    assert rm.check_emergency_stop(current, initial) is False


# ─── can_open_position ────────────────────────────────────────────────────────

def test_can_open_position_max_positions(rm):
    """Already at MAX_COINS (3) open positions → new position blocked."""
    active = {
        'BTC/USDT': _make_open_position('BTC/USDT'),
        'ETH/USDT': _make_open_position('ETH/USDT'),
        'SOL/USDT': _make_open_position('SOL/USDT'),
    }
    allowed, reason = rm.can_open_position(
        symbol='UNI/USDT',
        notional_usd=50.0,
        account_balance=1000.0,
        active_positions=active,
        system=1,
    )
    assert allowed is False
    assert 'Max positions' in reason


def test_can_open_position_sector_limit(rm):
    """Already have MAX_CORRELATED_COINS=2 L1 coins → third L1 blocked."""
    active = {
        'BTC/USDT': _make_open_position('BTC/USDT'),
        'ETH/USDT': _make_open_position('ETH/USDT'),
    }
    # SOL is also L1 — would be the 3rd L1 (limit is 2)
    allowed, reason = rm.can_open_position(
        symbol='SOL/USDT',
        notional_usd=50.0,
        account_balance=1000.0,
        active_positions=active,
        system=1,
    )
    assert allowed is False
    assert 'Sector' in reason or 'sector' in reason


def test_can_open_position_reserve_cash(rm):
    """Position notional > deployable cash (balance * 0.9) → blocked."""
    active = {}
    # account_balance=100, deployable=90, but we want to spend 95
    allowed, reason = rm.can_open_position(
        symbol='BTC/USDT',
        notional_usd=95.0,
        account_balance=100.0,
        active_positions=active,
        system=1,
    )
    assert allowed is False
    assert 'deployable' in reason.lower() or 'cash' in reason.lower()


def test_can_open_position_allowed(rm):
    """All checks pass → (True, 'OK')."""
    active = {}
    allowed, reason = rm.can_open_position(
        symbol='UNI/USDT',
        notional_usd=50.0,
        account_balance=1000.0,
        active_positions=active,
        system=1,
    )
    assert allowed is True
    assert reason == 'OK'


# ─── Kraken Order Validation ─────────────────────────────────────────────────

def test_validate_kraken_order_below_min(rm):
    """Quantity below min_order → rejected."""
    mock_exchange = MagicMock()
    mock_exchange.get_trading_limits.return_value = {
        'min_order': 0.001,
        'min_notional': 0,
    }
    valid, reason = rm.validate_kraken_order(
        symbol='BTC/USDT',
        quantity=0.0001,    # below 0.001 min
        price=50_000.0,
        exchange=mock_exchange,
    )
    assert valid is False
    assert 'min' in reason.lower() or 'below' in reason.lower()


def test_validate_kraken_order_passes(rm):
    """Quantity and notional above minimums → (True, 'OK')."""
    mock_exchange = MagicMock()
    mock_exchange.get_trading_limits.return_value = {
        'min_order': 0.001,
        'min_notional': 10.0,
    }
    valid, reason = rm.validate_kraken_order(
        symbol='BTC/USDT',
        quantity=0.01,
        price=50_000.0,
        exchange=mock_exchange,
    )
    assert valid is True
    assert reason == 'OK'
