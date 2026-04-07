"""
Tests for blocked coins filtering and KrakenDiscovery integration.
All tests are self-contained with no network calls.
"""

import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import json
import tempfile
from unittest.mock import patch, MagicMock
import pytest


class MockConfig:
    SCAN_TOP_COINS = True
    TOP_N_COINS = 50
    FIXED_COINS = ['BTC', 'ETH', 'BRETT', 'SOL', 'AMP']  # BRETT and AMP are blocked
    BATCH_SIZE = 20


def _make_kraken_ticker_result(pairs):
    """Build a fake Kraken Ticker result dict from a list of (wsname, volume, price) tuples."""
    result = {}
    for wsname, vol, price in pairs:
        key = wsname.replace('/', '')
        result[key] = {
            'v': ['0', str(vol)],
            'c': [str(price), '1'],
        }
    return result


def _make_kraken_asset_pairs(wsnames):
    """Build a fake Kraken AssetPairs result from a list of wsnames like 'BTC/USDT'."""
    result = {}
    for wsname in wsnames:
        base, quote = wsname.split('/')
        key = f"{base}{quote}"
        result[key] = {'quote': quote, 'wsname': wsname}
    return result


# ─── KrakenDiscovery tests ────────────────────────────────────────────────────

def test_kraken_discovery_filters_blocked_coins():
    """Mock Kraken API: include a blocked coin, verify it's removed."""
    from utils.kraken_discovery import KrakenDiscovery

    wsnames = ['BTC/USDT', 'ETH/USDT', 'BRETT/USDT', 'SOL/USDT']
    asset_pairs = _make_kraken_asset_pairs(wsnames)
    ticker = _make_kraken_ticker_result([
        ('BTC/USDT', 1000, 80000),
        ('ETH/USDT', 5000, 3000),
        ('BRETT/USDT', 2000, 0.1),
        ('SOL/USDT', 3000, 150),
    ])

    disc = KrakenDiscovery()
    with patch.object(disc, '_get', side_effect=lambda ep: asset_pairs if ep == 'AssetPairs' else ticker):
        result = disc.get_top_pairs_by_volume(limit=50, min_volume_usd=0, blocked_coins={'BRETT'})

    symbols = [p['symbol'] for p in result]
    assert 'BRETT/USDT' not in symbols, "BRETT should be filtered by blocked_coins"
    assert 'BTC/USDT' in symbols
    assert 'ETH/USDT' in symbols
    assert 'SOL/USDT' in symbols


def test_kraken_discovery_filters_stablecoins():
    """Stablecoins (USDT, USDC, DAI) must be excluded from results."""
    from utils.kraken_discovery import KrakenDiscovery

    wsnames = ['BTC/USDT', 'USDC/USDT', 'DAI/USDT', 'ETH/USDT']
    asset_pairs = _make_kraken_asset_pairs(wsnames)
    ticker = _make_kraken_ticker_result([
        ('BTC/USDT', 1000, 80000),
        ('USDC/USDT', 9999, 1.0),
        ('DAI/USDT', 8888, 1.0),
        ('ETH/USDT', 5000, 3000),
    ])

    disc = KrakenDiscovery()
    with patch.object(disc, '_get', side_effect=lambda ep: asset_pairs if ep == 'AssetPairs' else ticker):
        result = disc.get_top_pairs_by_volume(limit=50, min_volume_usd=0)

    symbols = [p['symbol'] for p in result]
    assert 'USDC/USDT' not in symbols
    assert 'DAI/USDT' not in symbols
    assert 'BTC/USDT' in symbols
    assert 'ETH/USDT' in symbols


def test_kraken_discovery_sorts_by_volume():
    """Results must come back volume-descending."""
    from utils.kraken_discovery import KrakenDiscovery

    wsnames = ['BTC/USDT', 'ETH/USDT', 'SOL/USDT']
    asset_pairs = _make_kraken_asset_pairs(wsnames)
    # SOL has highest USD volume, then BTC, then ETH
    ticker = _make_kraken_ticker_result([
        ('BTC/USDT', 100, 80000),      # $8,000,000
        ('ETH/USDT', 50, 3000),        # $150,000
        ('SOL/USDT', 1000, 150),       # $150,000 — same as ETH but listed last
    ])
    # Give SOL the highest to be clear
    ticker['SOLUSDT']['v'] = ['0', '10000']   # $1,500,000

    disc = KrakenDiscovery()
    with patch.object(disc, '_get', side_effect=lambda ep: asset_pairs if ep == 'AssetPairs' else ticker):
        result = disc.get_top_pairs_by_volume(limit=50, min_volume_usd=0)

    assert result[0]['symbol'] == 'BTC/USDT', "BTC should be first by volume"
    volumes = [p['volume_24h'] for p in result]
    assert volumes == sorted(volumes, reverse=True), "Results must be volume-descending"


def test_kraken_discovery_fallback_on_error():
    """API failure must return empty list gracefully, no exception."""
    from utils.kraken_discovery import KrakenDiscovery

    disc = KrakenDiscovery()
    with patch.object(disc, '_get', return_value={}):
        result = disc.get_top_pairs_by_volume(limit=50)

    assert result == [], "Should return empty list on API failure"


# ─── Fixed-coin path tests (unchanged from original) ─────────────────────────

def test_blocked_coins_filtered_fixed_path(tmp_path):
    """
    Set SCAN_TOP_COINS=False, add blocked coins to FIXED_COINS.
    Verify they are filtered out.
    """
    blocked_data = {'blocked_coins': ['BRETT', 'AMP'], 'count': 2}
    blocked_file = tmp_path / 'blocked_coins.json'
    blocked_file.write_text(json.dumps(blocked_data))

    config = MockConfig()
    config.SCAN_TOP_COINS = False

    with patch('main.Path') as mock_path_cls:
        mock_path_instance = MagicMock()
        mock_path_instance.__truediv__ = MagicMock(return_value=blocked_file)
        mock_path_cls.return_value = mock_path_instance

        from main import get_coin_universe
        result = get_coin_universe(config, quote_currency='USDT')

    result_bases = [r.split('/')[0] for r in result]
    assert 'BRETT' not in result_bases, "BRETT should be filtered from fixed coin list"
    assert 'AMP' not in result_bases, "AMP should be filtered from fixed coin list"
    assert 'BTC' in result_bases
    assert 'ETH' in result_bases
    assert 'SOL' in result_bases


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
        result = get_coin_universe(config, quote_currency='USDT')

    assert isinstance(result, list)
    assert len(result) > 0
