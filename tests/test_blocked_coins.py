"""
Regression tests for Bug 2 — blocked coins must be filtered out of the
trading universe whether we're using CoinGecko or the fixed-coin path.
All tests are self-contained with no network calls.
"""

import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import json
import tempfile
import types
from unittest.mock import patch, MagicMock
import pytest


class MockConfig:
    SCAN_TOP_COINS = True
    TOP_N_COINS = 50
    FIXED_COINS = {
        'BTC': 'bitcoin',
        'ETH': 'ethereum',
        'BRETT': 'brett',      # blocked
        'SOL': 'solana',
        'AMP': 'amp-token',    # blocked
    }
    BATCH_SIZE = 20


def _make_get_coin_universe():
    """
    Import get_coin_universe lazily so we can control imports around it.
    Returns the function from main.py.
    """
    import importlib
    # We need to import main carefully — it has top-level side-effect imports
    # so we load the function directly by executing the module with mocked deps.
    import main as _main
    return _main.get_coin_universe


# ─── Test 1: CoinGecko path filters blocked coins ─────────────────────────────

def test_blocked_coins_filtered_coingecko_path(tmp_path):
    """
    Mock CoinGecko to return a list including blocked coins.
    Verify they are removed from the result.
    """
    # Write a real blocked_coins.json to a temp dir, then patch the path used
    # inside get_coin_universe so it reads our temp file.
    blocked_data = {'blocked_coins': ['BRETT', 'AMP', 'OKB'], 'count': 3}
    blocked_file = tmp_path / 'blocked_coins.json'
    blocked_file.write_text(json.dumps(blocked_data))

    # CoinGecko returns BTC, ETH, BRETT, SOL, AMP
    mock_coins = [
        {'symbol': 'BTC'},
        {'symbol': 'ETH'},
        {'symbol': 'BRETT'},   # should be filtered
        {'symbol': 'SOL'},
        {'symbol': 'AMP'},     # should be filtered
    ]

    config = MockConfig()
    config.SCAN_TOP_COINS = True

    mock_coingecko_instance = MagicMock()
    mock_coingecko_instance.get_top_coins.return_value = mock_coins

    with patch('main.Path') as mock_path_cls, \
         patch('utils.coingecko.CoinGeckoAPI', return_value=mock_coingecko_instance):

        # Make Path(__file__).parent / 'blocked_coins.json' return our temp file
        mock_path_instance = MagicMock()
        mock_path_instance.__truediv__ = MagicMock(return_value=blocked_file)
        mock_path_cls.return_value = mock_path_instance

        from main import get_coin_universe
        result = get_coin_universe(config, quote_currency='USDT')

    assert 'BRETT' not in result, "BRETT should be filtered by blocked_coins"
    assert 'AMP' not in result, "AMP should be filtered by blocked_coins"
    assert 'BTC' in result
    assert 'ETH' in result
    assert 'SOL' in result


# ─── Test 2: Fixed-coin path filters blocked coins ────────────────────────────

def test_blocked_coins_filtered_fixed_path(tmp_path):
    """
    Set SCAN_TOP_COINS=False, add blocked coins to FIXED_COINS.
    Verify they are filtered out.
    """
    blocked_data = {'blocked_coins': ['BRETT', 'AMP'], 'count': 2}
    blocked_file = tmp_path / 'blocked_coins.json'
    blocked_file.write_text(json.dumps(blocked_data))

    config = MockConfig()
    config.SCAN_TOP_COINS = False  # Use fixed path

    with patch('main.Path') as mock_path_cls:
        mock_path_instance = MagicMock()
        mock_path_instance.__truediv__ = MagicMock(return_value=blocked_file)
        mock_path_cls.return_value = mock_path_instance

        from main import get_coin_universe
        result = get_coin_universe(config, quote_currency='USDT')

    # Fixed path returns "SYMBOL/USDT" strings
    result_bases = [r.split('/')[0] for r in result]
    assert 'BRETT' not in result_bases, "BRETT should be filtered from fixed coin list"
    assert 'AMP' not in result_bases, "AMP should be filtered from fixed coin list"
    assert 'BTC' in result_bases
    assert 'ETH' in result_bases
    assert 'SOL' in result_bases


# ─── Test 3: Missing blocked_coins.json falls back gracefully ────────────────

def test_blocked_coins_file_missing():
    """
    Point blocked_coins.json at a nonexistent path.
    Verify the function falls back with an empty block set (no crash).
    """
    import pathlib

    config = MockConfig()
    config.SCAN_TOP_COINS = False

    nonexistent = pathlib.Path('/nonexistent/path/blocked_coins.json')

    with patch('main.Path') as mock_path_cls:
        mock_path_instance = MagicMock()
        mock_path_instance.__truediv__ = MagicMock(return_value=nonexistent)
        mock_path_cls.return_value = mock_path_instance

        from main import get_coin_universe
        # Must not raise, must return a list
        result = get_coin_universe(config, quote_currency='USDT')

    assert isinstance(result, list)
    assert len(result) > 0   # fixed coin list comes through unfiltered
