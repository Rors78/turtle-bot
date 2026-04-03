"""
Tests for AuditLog — every order event must be appended as valid JSON Lines.
All tests are self-contained with no network calls.
"""

import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import json
import tempfile
import pytest

from utils.audit import AuditLog


REQUIRED_FIELDS = {
    'timestamp', 'event_type', 'symbol', 'side',
    'quantity', 'price', 'fill_price', 'order_id', 'system',
}


def _log_one(filepath, **kwargs):
    """Helper: create AuditLog and log one order."""
    audit = AuditLog(filepath=filepath)
    defaults = dict(
        event_type='ENTRY',
        symbol='BTC/USDT',
        side='buy',
        quantity=0.01,
        price=50_000.0,
        fill_price=50_050.0,
        order_id='paper_BTC_buy_0.01',
        system=1,
        pnl=None,
        reason='S1 breakout',
    )
    defaults.update(kwargs)
    audit.log_order(**defaults)


# ─── Single order ─────────────────────────────────────────────────────────────

def test_log_order_writes_jsonl(tmp_path):
    """Call log_order(), read the file, verify valid JSON line with all expected fields."""
    filepath = str(tmp_path / 'audit.jsonl')
    _log_one(filepath)

    with open(filepath, 'r') as f:
        lines = f.readlines()

    assert len(lines) == 1, "Expected exactly one line"
    record = json.loads(lines[0])

    for field in REQUIRED_FIELDS:
        assert field in record, f"Missing field: {field}"

    assert record['event_type'] == 'ENTRY'
    assert record['symbol'] == 'BTC/USDT'
    assert record['side'] == 'buy'
    assert abs(record['quantity'] - 0.01) < 1e-9
    assert abs(record['fill_price'] - 50_050.0) < 1e-9
    assert record['system'] == 1


# ─── Multiple orders ──────────────────────────────────────────────────────────

def test_multiple_orders_append(tmp_path):
    """Log 3 orders, verify 3 lines in file, each valid JSON."""
    filepath = str(tmp_path / 'multi_audit.jsonl')

    _log_one(filepath, symbol='BTC/USDT', event_type='ENTRY')
    _log_one(filepath, symbol='ETH/USDT', event_type='PYRAMID')
    _log_one(filepath, symbol='SOL/USDT', event_type='EXIT', pnl=25.0)

    with open(filepath, 'r') as f:
        lines = [l.strip() for l in f if l.strip()]

    assert len(lines) == 3

    records = [json.loads(l) for l in lines]
    symbols = [r['symbol'] for r in records]
    assert 'BTC/USDT' in symbols
    assert 'ETH/USDT' in symbols
    assert 'SOL/USDT' in symbols

    exit_record = next(r for r in records if r['symbol'] == 'SOL/USDT')
    assert exit_record['pnl'] == 25.0
