"""
Turtle Bot Web Dashboard
Flask backend serving the single-page dashboard and JSON API endpoints.
"""

import json
import os
import sys
import time
import logging
from pathlib import Path

from flask import Flask, jsonify, render_template
from flask_cors import CORS

# Allow importing config/utils from the repo root regardless of where the
# script is launched from.
_repo_root = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(_repo_root))

try:
    from config import Config
    _cfg = Config()
    _STATE_FILE = getattr(_cfg, 'STATE_FILE_PATH', 'bot_state.json')
    _AUDIT_FILE = getattr(_cfg, 'AUDIT_FILE_PATH', 'trade_audit.jsonl')
    _PORT = getattr(_cfg, 'DASHBOARD_PORT', 5001)
except Exception:
    _STATE_FILE = os.getenv('STATE_FILE_PATH', 'bot_state.json')
    _AUDIT_FILE = os.getenv('AUDIT_FILE_PATH', 'trade_audit.jsonl')
    _PORT = int(os.getenv('DASHBOARD_PORT', '5001'))

# Resolve paths relative to repo root when they are relative
def _abs(path: str) -> str:
    p = Path(path)
    if not p.is_absolute():
        return str(_repo_root / p)
    return str(p)


STATE_FILE = _abs(_STATE_FILE)
AUDIT_FILE = _abs(_AUDIT_FILE)
BACKTEST_FILE = str(_repo_root / 'backtest_results.json')
PORT = _PORT

# Stale threshold: 2x the default check interval (5 min * 2 = 15 min)
STALE_THRESHOLD_SECONDS = 15 * 60

app = Flask(__name__, template_folder='templates')
CORS(app)

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


# ── Helpers ──────────────────────────────────────────────────────────────────

def _read_json_file(path: str):
    """Read and parse a JSON file.  Returns None on any error."""
    try:
        with open(path, 'r', encoding='utf-8') as fh:
            return json.load(fh)
    except (FileNotFoundError, json.JSONDecodeError):
        return None


def _read_jsonl_tail(path: str, n: int = 100):
    """Return the last *n* lines of a JSON Lines file as a list of dicts."""
    try:
        with open(path, 'r', encoding='utf-8') as fh:
            lines = fh.readlines()
    except FileNotFoundError:
        return []

    tail = lines[-n:] if len(lines) > n else lines
    records = []
    for line in tail:
        line = line.strip()
        if not line:
            continue
        try:
            records.append(json.loads(line))
        except json.JSONDecodeError:
            pass
    return records


# ── Routes ────────────────────────────────────────────────────────────────────

@app.route('/')
def index():
    """Serve the single-page dashboard."""
    return render_template('index.html')


@app.route('/api/state')
def api_state():
    """
    Return the current bot state as JSON.
    If bot_state.json does not exist, return {"status": "no_data"}.
    """
    data = _read_json_file(STATE_FILE)
    if data is None:
        return jsonify({'status': 'no_data'})
    return jsonify(data)


@app.route('/api/backtest')
def api_backtest():
    """
    Return backtest results if available.
    """
    data = _read_json_file(BACKTEST_FILE)
    if data is None:
        return jsonify({'status': 'no_data'})
    return jsonify(data)


@app.route('/api/audit')
def api_audit():
    """
    Return the last 100 audit log entries as a JSON array.
    """
    records = _read_jsonl_tail(AUDIT_FILE, n=100)
    return jsonify(records)


@app.route('/health')
def health():
    """
    Health check endpoint.
    Returns state file age and a 'stale' warning if older than 15 minutes.
    """
    resp = {'status': 'ok'}

    try:
        age = time.time() - os.path.getmtime(STATE_FILE)
        resp['state_file_age_seconds'] = round(age, 1)
        if age > STALE_THRESHOLD_SECONDS:
            resp['warning'] = 'stale'
    except FileNotFoundError:
        resp['state_file_age_seconds'] = None

    return jsonify(resp)


# ── Entry point ───────────────────────────────────────────────────────────────

if __name__ == '__main__':
    print(f"Starting Turtle Bot Dashboard on http://localhost:{PORT}")
    print(f"  State file : {STATE_FILE}")
    print(f"  Audit file : {AUDIT_FILE}")
    app.run(host='0.0.0.0', port=PORT, debug=False)
