"""
Tests for the Flask web dashboard (web/app.py).
All tests use Flask's built-in test client — no real network calls.
"""

import sys
import os
import json
import time
import tempfile

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import pytest

# Patch file paths before importing app so no real files are touched.
import importlib


def _make_app(state_file=None, audit_file=None):
    """
    Import (or re-import) web.app with custom file paths injected.
    Returns the Flask test client.
    """
    # Make sure the web package is importable
    web_dir = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), 'web')
    if web_dir not in sys.path:
        sys.path.insert(0, web_dir)

    # Force re-import so module-level path vars pick up our patches
    if 'web.app' in sys.modules:
        del sys.modules['web.app']
    if 'app' in sys.modules:
        del sys.modules['app']

    import web.app as _wapp

    # Override module-level path vars
    if state_file is not None:
        _wapp.STATE_FILE = state_file
    if audit_file is not None:
        _wapp.AUDIT_FILE = audit_file

    _wapp.app.config['TESTING'] = True
    return _wapp.app.test_client(), _wapp.app


# ── /health ───────────────────────────────────────────────────────────────────

def test_health_endpoint():
    """GET /health must return 200 with status 'ok'."""
    with tempfile.TemporaryDirectory() as tmpdir:
        state_path = os.path.join(tmpdir, 'bot_state.json')
        # Write a minimal state file so mtime exists
        with open(state_path, 'w') as f:
            json.dump({'status': 'ok'}, f)

        client, _ = _make_app(state_file=state_path)
        resp = client.get('/health')
        assert resp.status_code == 200
        data = json.loads(resp.data)
        assert data['status'] == 'ok'
        assert 'state_file_age_seconds' in data


# ── /api/state ────────────────────────────────────────────────────────────────

def test_state_endpoint_no_file():
    """No state file → returns {"status": "no_data"} with 200."""
    with tempfile.TemporaryDirectory() as tmpdir:
        state_path = os.path.join(tmpdir, 'nonexistent_state.json')

        client, _ = _make_app(state_file=state_path)
        resp = client.get('/api/state')
        assert resp.status_code == 200
        data = json.loads(resp.data)
        assert data == {'status': 'no_data'}


def test_state_endpoint_with_file():
    """Valid bot_state.json → /api/state returns its contents."""
    sample = {
        'iteration': 42,
        'current_equity': 1500.0,
        'initial_equity': 1000.0,
        'total_pnl': 500.0,
        'is_paused': False,
    }
    with tempfile.TemporaryDirectory() as tmpdir:
        state_path = os.path.join(tmpdir, 'bot_state.json')
        with open(state_path, 'w') as f:
            json.dump(sample, f)

        client, _ = _make_app(state_file=state_path)
        resp = client.get('/api/state')
        assert resp.status_code == 200
        data = json.loads(resp.data)
        assert data['iteration'] == 42
        assert abs(data['current_equity'] - 1500.0) < 1e-9
        assert abs(data['total_pnl'] - 500.0) < 1e-9


# ── /api/audit ────────────────────────────────────────────────────────────────

def test_audit_endpoint():
    """Write 5 JSONL lines to audit file → /api/audit returns them as array."""
    records = [
        {'event_type': 'ENTRY',  'symbol': 'BTC/USDT', 'side': 'buy',  'quantity': 0.01, 'price': 50000.0},
        {'event_type': 'PYRAMID','symbol': 'BTC/USDT', 'side': 'buy',  'quantity': 0.01, 'price': 51000.0},
        {'event_type': 'EXIT',   'symbol': 'ETH/USDT', 'side': 'sell', 'quantity': 0.1,  'price': 3000.0},
        {'event_type': 'STOP_HIT','symbol': 'SOL/USDT','side': 'sell', 'quantity': 1.0,  'price': 150.0},
        {'event_type': 'ENTRY',  'symbol': 'ADA/USDT', 'side': 'buy',  'quantity': 100.0,'price': 0.5},
    ]
    with tempfile.TemporaryDirectory() as tmpdir:
        audit_path = os.path.join(tmpdir, 'audit.jsonl')
        with open(audit_path, 'w') as f:
            for r in records:
                f.write(json.dumps(r) + '\n')

        client, _ = _make_app(audit_file=audit_path)
        resp = client.get('/api/audit')
        assert resp.status_code == 200
        data = json.loads(resp.data)
        assert isinstance(data, list)
        assert len(data) == 5
        symbols = [r['symbol'] for r in data]
        assert 'BTC/USDT' in symbols
        assert 'ETH/USDT' in symbols


# ── /health stale warning ─────────────────────────────────────────────────────

def test_health_stale_warning():
    """State file mtime > 15 minutes ago → health response includes warning='stale'."""
    with tempfile.TemporaryDirectory() as tmpdir:
        state_path = os.path.join(tmpdir, 'bot_state.json')
        with open(state_path, 'w') as f:
            json.dump({'status': 'ok'}, f)

        # Set mtime to 20 minutes ago
        twenty_min_ago = time.time() - 20 * 60
        os.utime(state_path, (twenty_min_ago, twenty_min_ago))

        client, _ = _make_app(state_file=state_path)
        resp = client.get('/health')
        assert resp.status_code == 200
        data = json.loads(resp.data)
        assert data.get('warning') == 'stale', f"Expected 'stale' warning, got: {data}"
