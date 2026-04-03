"""
Tests for BotState — state persistence, equity tracking, thread safety.
All tests are self-contained with no network calls.
"""

import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import json
import tempfile
import threading
from unittest.mock import patch
import pytest

from utils.state import BotState
from core.position import TurtlePosition


def make_position(symbol='BTC/USDT', system=1, entry_price=100.0, qty=0.01, atr=5.0):
    """Create a minimal TurtlePosition with one unit."""
    pos = TurtlePosition(symbol=symbol, exchange='kraken', system=system)
    pos.add_unit(price=entry_price, quantity=qty, current_atr=atr)
    return pos


# ─── Save / Load Roundtrip ────────────────────────────────────────────────────

def test_save_load_roundtrip(tmp_path):
    """Create a BotState, save to temp file, load it back, verify fields match."""
    state = BotState(account_size=1000.0)
    state.iteration = 42
    state.total_trades = 5
    state.winning_trades = 3
    state.losing_trades = 2
    state.total_pnl = 150.0
    state.is_paused = True
    state.pause_reason = 'test'

    filepath = str(tmp_path / 'state.json')
    state.save(filepath)

    loaded = BotState.load(filepath, account_size=1000.0)
    assert loaded.iteration == 42
    assert loaded.total_trades == 5
    assert loaded.winning_trades == 3
    assert loaded.losing_trades == 2
    assert abs(loaded.total_pnl - 150.0) < 1e-9
    assert loaded.is_paused is True
    assert loaded.pause_reason == 'test'
    assert abs(loaded.initial_equity - 1000.0) < 1e-9


def test_save_load_with_active_positions(tmp_path):
    """Add TurtlePositions with units, save/load, verify positions survive."""
    state = BotState(account_size=5000.0)
    pos = make_position('ETH/USDT', system=2, entry_price=3000.0, qty=0.1, atr=100.0)
    state.add_position(pos)

    filepath = str(tmp_path / 'state_pos.json')
    state.save(filepath)

    loaded = BotState.load(filepath, account_size=5000.0)
    assert 'ETH/USDT' in loaded.active_positions
    restored = loaded.active_positions['ETH/USDT']
    assert restored.unit_count == 1
    assert abs(restored.units[0].entry_price - 3000.0) < 1e-9
    assert abs(restored.initial_n - 100.0) < 1e-9
    assert restored.system == 2


def test_load_missing_file():
    """Load from nonexistent file — must return a fresh BotState, not crash."""
    state = BotState.load('/nonexistent/path/state.json', account_size=200.0)
    assert isinstance(state, BotState)
    assert abs(state.initial_equity - 200.0) < 1e-9
    assert len(state.active_positions) == 0
    assert state.iteration == 0


def test_load_corrupt_file(tmp_path):
    """Write garbage JSON to file, verify returns fresh state (no crash)."""
    filepath = tmp_path / 'corrupt.json'
    filepath.write_text('this is not json {{{')

    state = BotState.load(str(filepath), account_size=500.0)
    assert isinstance(state, BotState)
    assert abs(state.initial_equity - 500.0) < 1e-9
    assert len(state.active_positions) == 0


def test_atomic_save(tmp_path):
    """Verify os.replace is called with a .tmp path (atomic write pattern)."""
    state = BotState(account_size=100.0)
    filepath = str(tmp_path / 'atomic.json')

    with patch('os.replace') as mock_replace:
        # Need actual file write to work — just spy on replace
        # We patch after the write so the tmp file exists
        import os as _os
        original_replace = _os.replace

        def spy_replace(src, dst):
            assert src.endswith('.tmp'), f"Expected .tmp source, got {src}"
            original_replace(src, dst)
            mock_replace(src, dst)

        with patch('os.replace', side_effect=spy_replace):
            state.save(filepath)

        assert mock_replace.called


# ─── Trade Statistics ─────────────────────────────────────────────────────────

def test_close_position_updates_stats(tmp_path):
    """Close a winning and losing position, verify stats update correctly."""
    state = BotState(account_size=10_000.0)

    # Winning trade: bought 1 BTC at $100, exit at $150 → PnL = $50
    pos_win = make_position('BTC/USDT', entry_price=100.0, qty=1.0, atr=5.0)
    state.add_position(pos_win)
    state.close_position('BTC/USDT', exit_price=150.0, exit_reason='EXIT_SIGNAL')

    assert state.total_trades == 1
    assert state.winning_trades == 1
    assert state.losing_trades == 0
    assert abs(state.total_pnl - 50.0) < 1e-9

    # Losing trade: bought 2 ETH at $200, exit at $180 → PnL = -40
    pos_lose = make_position('ETH/USDT', entry_price=200.0, qty=2.0, atr=10.0)
    state.add_position(pos_lose)
    state.close_position('ETH/USDT', exit_price=180.0, exit_reason='STOP_HIT')

    assert state.total_trades == 2
    assert state.winning_trades == 1
    assert state.losing_trades == 1
    assert abs(state.total_pnl - (50.0 - 40.0)) < 1e-9   # $10 net


# ─── Equity / Drawdown ────────────────────────────────────────────────────────

def test_update_equity_tracks_drawdown():
    """
    Start at $130, go to $150 (new peak), drop to $120.
    max_drawdown should be (150-120)/150 = 0.2.
    """
    state = BotState(account_size=130.0)

    state.update_equity(130.0)   # baseline
    state.update_equity(150.0)   # new peak
    state.update_equity(120.0)   # drawdown from peak

    expected_dd = (150.0 - 120.0) / 150.0   # 0.2
    assert abs(state.max_drawdown - expected_dd) < 1e-9
    assert abs(state.peak_equity - 150.0) < 1e-9


# ─── Thread Safety ────────────────────────────────────────────────────────────

def test_thread_safety():
    """
    Spawn 10 threads each calling add_position() with a unique symbol.
    Verify no data loss and no exceptions.
    """
    state = BotState(account_size=1000.0)
    errors = []

    def add_pos(i):
        try:
            symbol = f'COIN{i}/USDT'
            pos = make_position(symbol=symbol, entry_price=float(100 + i))
            state.add_position(pos)
        except Exception as e:
            errors.append(e)

    threads = [threading.Thread(target=add_pos, args=(i,)) for i in range(10)]
    for t in threads:
        t.start()
    for t in threads:
        t.join()

    assert len(errors) == 0, f"Thread errors: {errors}"
    assert len(state.active_positions) == 10
