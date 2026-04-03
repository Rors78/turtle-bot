"""
Tests for the Exchange adapter — paper trading behaviour.
All tests are self-contained with no real network calls.
CCXTAdapter's __init__ calls ccxt.kraken() and load_markets(), so we mock ccxt.
"""

import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from unittest.mock import MagicMock, patch, PropertyMock
import pytest


def _make_mock_ccxt_exchange(ask=1000.0, bid=990.0):
    """Return a fully-mocked ccxt exchange object."""
    ex = MagicMock()
    ex.markets = {}
    ex.load_markets.return_value = {}
    ex.milliseconds.return_value = 1_700_000_000_000
    ex.fetch_ticker.return_value = {
        'last': 1000.0, 'bid': bid, 'ask': ask, 'volume': 500.0
    }
    return ex


def _make_adapter(paper_trading=True, ask=1000.0, bid=990.0, slippage=0.001):
    """Build a CCXTAdapter with a mocked ccxt backend."""
    mock_ex = _make_mock_ccxt_exchange(ask=ask, bid=bid)

    with patch('ccxt.kraken', return_value=mock_ex):
        from exchange.base import CCXTAdapter
        adapter = CCXTAdapter(
            exchange_name='kraken',
            paper_trading=paper_trading,
            slippage=slippage,
        )
    return adapter, mock_ex


# ─── Balance ──────────────────────────────────────────────────────────────────

def test_paper_balance_returns_zero():
    """In paper mode, get_balance() returns 0.0."""
    adapter, _ = _make_adapter(paper_trading=True)
    assert adapter.get_balance() == 0.0


# ─── Paper Order Slippage ────────────────────────────────────────────────────

def test_paper_order_applies_slippage_buy():
    """Paper buy order fills at ask * (1 + slippage)."""
    slippage = 0.001
    ask = 1000.0
    adapter, mock_ex = _make_adapter(paper_trading=True, ask=ask, slippage=slippage)

    # Patch the internal get_ticker to return controlled data
    with patch.object(adapter, 'get_ticker', return_value={
        'symbol': 'BTC/USDT', 'last': 1000.0, 'bid': 990.0, 'ask': ask, 'volume': 500.0
    }):
        order = adapter.create_market_order('BTC/USDT', 'buy', 0.01)

    expected_fill = ask * (1 + slippage)
    assert abs(order['price'] - expected_fill) < 1e-9


def test_paper_order_applies_slippage_sell():
    """Paper sell order fills at bid * (1 - slippage)."""
    slippage = 0.001
    bid = 990.0
    adapter, _ = _make_adapter(paper_trading=True, bid=bid, slippage=slippage)

    with patch.object(adapter, 'get_ticker', return_value={
        'symbol': 'BTC/USDT', 'last': 1000.0, 'bid': bid, 'ask': 1000.0, 'volume': 500.0
    }):
        order = adapter.create_market_order('BTC/USDT', 'sell', 0.01)

    expected_fill = bid * (1 - slippage)
    assert abs(order['price'] - expected_fill) < 1e-9


def test_paper_order_returns_filled():
    """Paper orders return status 'closed' with correct filled quantity."""
    adapter, _ = _make_adapter(paper_trading=True)

    with patch.object(adapter, 'get_ticker', return_value={
        'symbol': 'BTC/USDT', 'last': 1000.0, 'bid': 990.0, 'ask': 1000.0, 'volume': 500.0
    }):
        order = adapter.create_market_order('BTC/USDT', 'buy', 0.05)

    assert order['status'] == 'closed'
    assert order['filled'] == 0.05
    assert order['side'] == 'buy'


# ─── Live mode init ───────────────────────────────────────────────────────────

def test_live_mode_requires_no_credentials_to_init():
    """
    Non-paper mode with no API keys still initializes without error.
    Keys are only needed for private endpoints, not instantiation.
    """
    mock_ex = _make_mock_ccxt_exchange()
    with patch('ccxt.kraken', return_value=mock_ex):
        from exchange.base import CCXTAdapter
        adapter = CCXTAdapter(
            exchange_name='kraken',
            api_key=None,
            api_secret=None,
            paper_trading=False,
        )
    assert adapter is not None
    assert adapter.paper_trading is False


# ─── Symbol normalisation ─────────────────────────────────────────────────────

def test_normalize_symbol_bare_base():
    """'BTC' without a slash gets /USDT appended."""
    adapter, _ = _make_adapter()
    result = adapter.normalize_symbol('BTC')
    assert result == 'BTC/USDT'


def test_normalize_symbol_already_normalised():
    """'ETH/USDT' stays 'ETH/USDT'."""
    adapter, _ = _make_adapter()
    result = adapter.normalize_symbol('ETH/USDT')
    assert result == 'ETH/USDT'


def test_normalize_symbol_lowercase():
    """Lower-case input is uppercased."""
    adapter, _ = _make_adapter()
    result = adapter.normalize_symbol('sol/usdt')
    assert result == 'SOL/USDT'
