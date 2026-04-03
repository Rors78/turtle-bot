# Turtle Bot — Web Dashboard

## Overview

The web dashboard is an optional read-only interface for monitoring Turtle Bot while it runs. It is a plain Flask application serving a single HTML page. The page uses vanilla JavaScript to poll the bot state every 30 seconds and re-render — there are no WebSockets, no SocketIO, and no real-time push mechanism.

The dashboard reads two files that the bot writes at runtime:

| File | Written by | Read by dashboard at |
|------|-----------|----------------------|
| `bot_state.json` | `main.py` (after every cycle) | `/api/state` |
| `trade_audit.jsonl` | `utils/audit.py` (on every fill) | `/api/audit` |

---

## Quick Start

```bash
# Recommended — launches Flask and optionally opens the browser:
bash launch_dashboard.sh

# Or start Flask directly:
python web/app.py
```

Then open `http://localhost:5001` in your browser.

### Run Bot and Dashboard Together

```bash
# Terminal 1 — run the bot
python main.py

# Terminal 2 — run the dashboard
bash launch_dashboard.sh
```

The bot writes `bot_state.json` at the end of each cycle (every 5 minutes by default). The dashboard picks up the new state on the next poll (within 30 seconds).

---

## How It Works

### Backend (Flask)

- `web/app.py` starts a Flask server on `DASHBOARD_PORT` (default 5001)
- CORS is enabled via `flask-cors` — no other Flask extensions are required
- Reads `bot_state.json` and `trade_audit.jsonl` on each request — no caching, no database
- Resolves file paths relative to the repo root when relative paths are configured

### Frontend (vanilla JavaScript, no framework)

- A single HTML file (`web/templates/index.html`) is served at `/`
- On page load, the JS immediately calls `poll()` which fetches `/api/state` and `/api/audit` in parallel
- A countdown timer decrements every second; when it reaches 0, `poll()` runs again
- All DOM updates are in-place (no full page reload)
- Chart.js (loaded from CDN) renders the equity curve

---

## API Endpoints

### `GET /`

Serves the single-page dashboard HTML.

---

### `GET /api/state`

Returns the full `bot_state.json` as JSON.

Returns `{"status": "no_data"}` if the file does not exist (bot has not run yet).

Example response (abbreviated):

```json
{
  "iteration": 42,
  "initial_equity": 130.0,
  "current_equity": 134.50,
  "peak_equity": 135.00,
  "cash_balance": 90.00,
  "total_pnl": 4.50,
  "total_return_pct": 3.46,
  "total_trades": 3,
  "winning_trades": 2,
  "losing_trades": 1,
  "win_rate": 0.667,
  "max_drawdown": 0.02,
  "sharpe_ratio": 1.23,
  "sortino_ratio": 1.85,
  "profit_factor": 2.4,
  "expectancy": 1.50,
  "paper_trading": true,
  "is_paused": false,
  "equity_history": [
    {"timestamp": "2026-01-15T10:00:00+00:00", "equity": 130.0},
    {"timestamp": "2026-01-15T10:05:00+00:00", "equity": 131.2}
  ],
  "active_positions": { ... },
  "closed_positions": [ ... ],
  "saved_at": "2026-01-15T10:35:00+00:00"
}
```

Analytics fields (`sharpe_ratio`, `sortino_ratio`, `profit_factor`, `expectancy`) are `"N/A"` until at least 5 closed trades have accumulated.

---

### `GET /api/backtest`

Returns `backtest_results.json` as JSON (written by `python run_backtest.py`).

Returns `{"status": "no_data"}` if no backtest has been run yet.

---

### `GET /api/audit`

Returns the last 100 entries from `trade_audit.jsonl` as a JSON array (oldest first within that window).

Returns `[]` if the audit file does not exist.

Example entry:

```json
{
  "timestamp": "2026-01-15T10:30:00+00:00",
  "event_type": "ENTRY",
  "symbol": "BTC/USDT",
  "side": "buy",
  "fill_price": 60000.0,
  "quantity": 0.00043,
  "pnl": null
}
```

Event types: `ENTRY`, `PYRAMID`, `EXIT`, `STOP_HIT`, `EMERGENCY_STOP`.

---

### `GET /health`

Health check endpoint. Returns the age of `bot_state.json` and a stale warning if it is older than 15 minutes (2× the default 5-minute check interval).

```json
{
  "status": "ok",
  "state_file_age_seconds": 47.3
}
```

When the state file is stale (bot may not be running):

```json
{
  "status": "ok",
  "state_file_age_seconds": 1823.0,
  "warning": "stale"
}
```

When no state file exists yet:

```json
{
  "status": "ok",
  "state_file_age_seconds": null
}
```

---

## Dashboard Sections

### Header

- **Mode badge**: PAPER (grey) or LIVE (red) based on `paper_trading` field
- **Connection dot**: green when the last poll succeeded, red on network/server error
- **Last updated**: timestamp of the most recent successful poll
- **Next poll countdown**: seconds until the next automatic refresh (resets to 30 on each poll)

### Equity Card

Displays: Current Equity, Initial Equity, Total Return (%), Total P&L, Peak Equity, Max Drawdown.

### Performance Card

Displays: Win Rate, Total Trades, Wins / Losses, Sharpe Ratio, Sortino Ratio, Profit Factor, Expectancy.

All ratio fields show `Insuff. data` until 5+ closed trades have accumulated.

### Equity Curve

Chart.js line chart plotting `equity_history` snapshots (one per bot cycle). Shows the equity line against a dashed reference line at initial equity. Hidden and replaced with a placeholder message if `equity_history` is empty.

### Active Positions Table

Columns: Symbol, System (S1 / S2), Units, Avg Entry, Current Price (shown as `—` — not in state), P&L ($), P&L (%), Stop Price. Sorted by unrealized P&L descending.

### Recent Closed Trades

Last 20 closed positions (most recent first). Columns: Symbol, System, Entry Price, Exit Price, P&L ($), P&L (%), Exit Reason, Hold Time.

### Audit Log

Last 20 entries from `/api/audit` (most recent first). Columns: Timestamp, Event, Symbol, Side, Price, Qty, P&L. Event types are colour-coded badges.

### Bot Status

Displays: State (Running / PAUSED), Pause Reason, Iteration count, Cash Balance, Last Save timestamp.

---

## Configuration

All dashboard configuration is set via environment variables (or `.env`):

| Variable | Default | Description |
|----------|---------|-------------|
| `DASHBOARD_PORT` | `5001` | TCP port Flask listens on |
| `STATE_FILE_PATH` | `bot_state.json` | Path to the bot state file (relative to repo root or absolute) |
| `AUDIT_FILE_PATH` | `trade_audit.jsonl` | Path to the JSONL audit file |

---

## Troubleshooting

### Dashboard won't start

- Confirm `web/app.py` exists in the project
- Check port 5001 is not already in use:
  - Linux/macOS: `lsof -i :5001`
  - Windows: `netstat -ano | findstr 5001`
- Try a different port: set `DASHBOARD_PORT=5002` in `.env`

### No data showing

- Confirm `bot_state.json` exists in the project root
- Run `python main.py` once to generate initial state
- Refresh the browser or wait for the next 30-second poll

### Dashboard shows stale data

- Check the bot process (`python main.py`) is still running
- The `/health` endpoint reports `"warning": "stale"` when `bot_state.json` is older than 15 minutes

### Browser doesn't auto-open

- Navigate manually to `http://localhost:5001`

### Mobile access (same network)

1. Find the host machine's local IP:
   ```bash
   hostname -I      # Linux
   ipconfig         # Windows
   ```
2. On the mobile device, navigate to `http://<HOST-IP>:5001`
