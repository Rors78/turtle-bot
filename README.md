# Turtle Bot — Turtle Trading System for Kraken

[![Turtle Bot CI](https://github.com/Rors78/turtle-bot/actions/workflows/ci.yml/badge.svg)](https://github.com/Rors78/turtle-bot/actions/workflows/ci.yml)

## USA Regulatory Compliant

**MADE FOR US TRADERS — FULLY COMPLIANT**

This bot is specifically designed to meet US regulatory requirements:

- **SPOT TRADING ONLY** — no futures, no derivatives
- **LONG POSITIONS ONLY** — no shorting
- **NO LEVERAGE** — 100% compliant with US regulations
- **KRAKEN ONLY** — Kraken US spot market, USDT pairs
- **Regulatory Compliant** for US retail traders

**Why this matters**: Most trading bots use leverage, futures, or shorting — which creates regulatory issues for US traders. This bot is built from the ground up for US compliance.

---

> **API keys are optional.** Paper/read-only mode uses Kraken's public REST API — no account or key required. Keys are only needed for live order execution.

---

## What Is Turtle Bot?

A cryptocurrency trading bot implementing the classic **Turtle Trading Strategy** for Kraken's US spot market. The bot runs a fully automated trend-following system: it scans the top coins by 24h volume on Kraken, detects breakouts using Turtle rules, sizes positions by ATR-based risk, pyramids into winning trades, and exits on breakdown signals or stops. Everything is long-only, unleveraged, and USDT-paired.

---

## Features

### Core Trading System

- **Dual System (S1 + S2)**: System 1 on 20-day breakouts (60% capital), System 2 on 55-day breakouts (40% capital) — both configurable
- **ATR-Based Position Sizing**: each unit risks exactly `RISK_PER_TRADE` of account equity using the initial N (ATR) locked at entry
- **Pyramiding**: scale into winners at 0.5N intervals, up to 4 units per position (classic Turtle rule)
- **Breakout Entry / Breakdown Exit**: enter on N-day high, exit on N-day low (10-day for S1, 20-day for S2)
- **2N Stop Loss**: hard stop 2 × ATR below the most recent unit entry — updated on each pyramid add
- **Pause / Resume**: bot can be paused mid-run; stops new entries while continuing to manage existing positions

### Exchange and Data

- **Kraken only**: all OHLC data and order execution via CCXT — no Binance, no fallback exchanges
- **Kraken REST API for coin discovery by 24h volume**: builds the trading universe from Kraken's own public `/Ticker` endpoint — no third-party dependency, no rate limit concerns
- **USDT pairs only**: all trading is quoted in USDT
- **Retry with exponential back-off**: Kraken API calls are automatically retried on transient failures
- **Minimum order validation**: Kraken minimum order size and notional value are checked before every order

### Risk Management

- Emergency stop (configurable drawdown threshold closes all positions)
- Max total portfolio risk check before new entries
- Per-sector correlation limits (max N positions per sector: L1, DeFi, Infra, Meme, etc.)
- Reserve cash buffer (keep a configurable % of balance undeployed)
- Per-position allocation cap
- Kraken minimum order size validation before every order

### Backtester

- Walk-forward simulation on a fixed coin universe using Kraken OHLC data
- Full analytics: Sharpe ratio, Sortino ratio, Calmar ratio, profit factor, expectancy, win rate, max drawdown
- Results written to `backtest_results.json` (read by the dashboard's `/api/backtest` endpoint)
- Configurable via CLI flags: `--days`, `--account-size`, `--system`, `--risk`

### Web Dashboard

- Plain Flask server + vanilla JavaScript — no WebSockets, no SocketIO
- Browser polls `/api/state` every 30 seconds and re-renders in-place
- Equity curve (Chart.js), active positions table, closed trades, audit log, bot status card
- Five API endpoints: `/`, `/api/state`, `/api/backtest`, `/api/audit`, `/health`

### Observability

- **Order audit trail**: every fill written to `trade_audit.jsonl` (append-only JSONL)
- **Structured JSON logging**: file handler emits JSON Lines; console uses human-readable text
- **Thread-safe state**: `BotState` uses a `threading.Lock` around all mutations and saves

### Opt-In Features

- **Trailing stops** (off by default): ATR-based stop ratchets up as price rises, never down
- **Regime detection** (off by default): ADX filter blocks new entries in choppy markets (ADX < 25)
- **Discord notifications** (off by default): webhook alerts on entry, exit, stop hit, error

### Testing

- **114+ tests** across 17 test files covering all major modules
- **GitHub Actions CI**: runs the full test suite on every push and pull request

---

## Project Structure

```
turtle-bot/
├── main.py                      # Bot entry point — main trading loop
├── config.py                    # All configuration (reads from .env)
├── requirements.txt             # Python dependencies
├── run_backtest.py              # Backtester CLI
├── launch_dashboard.sh          # Dashboard launcher script
├── export_state_to_json.py      # State inspection utility
├── blocked_coins.json           # Coins permanently excluded from trading
├── .env.example                 # All config vars with defaults and comments
├── core/
│   ├── position.py              # TurtlePosition and Unit dataclasses
│   ├── turtle_engine.py         # ATR calc, breakout signals, position sizing
│   └── backtester.py            # Walk-forward backtester and analytics
├── exchange/
│   └── base.py                  # ExchangeAdapter ABC + CCXTAdapter (Kraken)
├── risk/
│   ├── risk_manager.py          # Risk constraints and Kraken order validation
│   └── portfolio_manager.py     # Orchestrates stops, exits, pyramids, entries
├── utils/
│   ├── state.py                 # BotState: thread-safe JSON persistence
│   ├── analytics.py             # Sharpe, Sortino, profit factor, expectancy
│   ├── audit.py                 # JSONL order audit trail writer
│   ├── notifications.py         # Console output, ANSI colors, Discord alerts
│   ├── logging_config.py        # Structured JSON logging setup
│   ├── regime.py                # ADX-based regime/trend filter
│   ├── retry.py                 # Retry decorator with exponential back-off
│   ├── multi_exchange.py        # Kraken OHLC fetcher (named for import compat)
│   └── kraken_discovery.py      # Kraken REST API (coin discovery by 24h volume)
├── web/
│   ├── app.py                   # Flask dashboard server
│   └── templates/
│       └── index.html           # Single-page dashboard (polling, no WebSockets)
├── tests/                       # 17 test files, 114+ tests
│   ├── test_position.py
│   ├── test_state.py
│   ├── test_turtle_engine.py
│   ├── test_risk_manager.py
│   ├── test_portfolio_manager.py  (via test_exchange.py)
│   ├── test_backtester.py
│   ├── test_backtester_sizing.py
│   ├── test_analytics.py
│   ├── test_audit.py
│   ├── test_config.py
│   ├── test_dashboard.py
│   ├── test_exchange.py
│   ├── test_notifications.py
│   ├── test_regime.py
│   ├── test_regime_backtest.py
│   ├── test_trailing_stop.py
│   └── test_blocked_coins.py
├── .github/
│   └── workflows/
│       └── ci.yml               # GitHub Actions CI pipeline
└── misc/
    ├── strategies.json          # Strategy reference configurations
    └── turtlebot-icon.svg       # Bot icon
```

---

## Quick Start

### Prerequisites

- Python 3.10+
- A Kraken account (optional — only required for live trading)

### Installation

1. Clone the repository:

```bash
git clone https://github.com/Rors78/turtle-bot.git
cd turtle-bot
```

2. Install dependencies:

**Windows:**
```powershell
pip install -r requirements.txt
```

**Linux / macOS:**
```bash
pip3 install -r requirements.txt
```

3. Configure your environment:

```bash
cp .env.example .env
# Then open .env in your editor and fill in any values you want to change.
# All settings have sensible defaults — the minimum needed for paper trading is nothing.
```

The minimum `.env` for paper trading (all defaults):

```
PAPER_TRADING=True
ACCOUNT_SIZE=130
```

For live trading, add your Kraken credentials:

```
PAPER_TRADING=False
KRAKEN_API_KEY=your_key_here
KRAKEN_API_SECRET=your_secret_here
```

---

## Running ULTRA (Recommended)

The ULTRA engine is a self-contained single-file trading system with built-in dashboard:

```bash
python turtlebot.py
```

Or use the launcher:

```bash
python run_ultra.py
```

The dashboard auto-starts at http://localhost:5001

ULTRA uses Kraken's public REST API directly — no ccxt, no API keys needed for paper trading.

### Legacy Runner

The original modular bot is still available:

```bash
python main.py
```

---

## Running the Bot (Legacy)

**Paper trading (safe default):**

```bash
python main.py
```

**Live trading** (only after thorough paper testing):

```bash
# Set PAPER_TRADING=False in .env, then:
python main.py
```

The bot runs in a continuous loop, cycling every `CHECK_INTERVAL` seconds (default: 5 minutes). Each cycle:

1. Emergency stop check — if drawdown >= `EMERGENCY_STOP_LOSS`, close everything
2. Stop loss hits — close positions where current price <= 2N stop
3. Exit signals — close positions on N-day low breakdown
4. Pyramid opportunities — add units to winning positions at 0.5N
5. New entry signals — open new positions on N-day high breakout

Press `Ctrl+C` to stop gracefully.

---

## Backtester

Run a historical simulation using Kraken OHLC data:

```bash
python run_backtest.py --days 180 --account-size 130
```

Available flags:

| Flag | Default | Description |
|------|---------|-------------|
| `--days` | 180 | Number of days of history to back-test |
| `--account-size` | 130 | Starting account size in USD |
| `--system` | both | Which system to run: `1`, `2`, or `both` |
| `--risk` | 0.02 | Risk per trade as a decimal (0.02 = 2%) |

Results are written to `backtest_results.json` and printed to the console.

**Note**: when `SCAN_TOP_COINS=False`, the backtester uses the fixed coin universe defined in `config.py` (`FIXED_COINS`). This keeps backtest results reproducible.

---

## Web Dashboard

The dashboard is an optional read-only view of bot state. It reads `bot_state.json` (written by the bot) and renders it in the browser.

### Start the Dashboard

```bash
# Recommended (launches Flask and optionally opens the browser):
bash launch_dashboard.sh

# Or directly:
python web/app.py
```

Then open `http://localhost:5001` in your browser.

Run both the bot and dashboard simultaneously:

```bash
# Terminal 1
python main.py

# Terminal 2
bash launch_dashboard.sh
```

### How It Works

The dashboard is a plain Flask application serving a single HTML page. The page uses vanilla JavaScript to poll `/api/state` every 30 seconds and re-render — no WebSockets, no SocketIO required.

### API Endpoints

| Endpoint | Description |
|----------|-------------|
| `GET /` | Serves the single-page dashboard HTML |
| `GET /api/state` | Returns `bot_state.json` as JSON (or `{"status":"no_data"}`) |
| `GET /api/backtest` | Returns `backtest_results.json` as JSON (or `{"status":"no_data"}`) |
| `GET /api/audit` | Returns the last 100 entries from `trade_audit.jsonl` as a JSON array |
| `GET /health` | Returns state file age and a `"warning":"stale"` flag if older than 15 minutes |

### Dashboard Sections

- **Header**: paper/live mode badge, connection dot, last-updated time, next-poll countdown
- **Equity card**: current equity, initial equity, total return, total P&L, peak equity, max drawdown
- **Performance card**: win rate, total trades, wins/losses, Sharpe, Sortino, profit factor, expectancy
- **Equity curve**: Chart.js line chart of `equity_history` with initial equity reference line
- **Active positions**: symbol, system, units, avg entry, unrealized P&L, stop price
- **Recent closed trades**: last 20 closed positions with entry/exit prices, P&L, hold time, exit reason
- **Audit log**: last 20 JSONL audit entries with event type, symbol, side, fill price, quantity, P&L
- **Bot status**: running/paused state, pause reason, iteration count, cash balance, last save time

---

## Opt-In Features

### Trailing Stops

Disabled by default. When enabled, the stop is ratcheted up as price rises (never down), replacing the classic fixed-stop behaviour after the highest price tracked exceeds the initial entry.

```
TRAILING_STOP_ENABLED=True
TRAILING_STOP_METHOD=atr
TRAILING_STOP_DISTANCE=2.0
```

### Regime Detection (ADX Filter)

Disabled by default. When enabled, new entries are only taken when the ADX reading indicates a trending market (>= `REGIME_MIN_ADX`). Existing positions are always managed.

```
REGIME_FILTER_ENABLED=True
REGIME_ADX_PERIOD=14
REGIME_MIN_ADX=25.0
```

### Discord Notifications

Disabled by default. Set a webhook URL and enable to receive alerts on entry, exit, stop hit, and errors.

```
ALERT_ON_DISCORD=True
DISCORD_WEBHOOK_URL=https://discord.com/api/webhooks/...
ALERT_ON_ENTRY=True
ALERT_ON_EXIT=True
ALERT_ON_STOP=True
ALERT_ON_ERROR=True
```

---

## Configuration Reference

All settings are loaded from `.env` (see `.env.example` for every variable with comments). Key parameters:

| Variable | Default | Description |
|----------|---------|-------------|
| `ACCOUNT_SIZE` | `130` | Starting account size in USD |
| `PAPER_TRADING` | `True` | Simulate trades; no real orders placed |
| `KRAKEN_API_KEY` | _(empty)_ | Required for live trading only |
| `KRAKEN_API_SECRET` | _(empty)_ | Required for live trading only |
| `SYSTEM_1_ENABLED` | `True` | Enable 20-day breakout system |
| `SYSTEM_2_ENABLED` | `True` | Enable 55-day breakout system |
| `SYSTEM_SPLIT` | `0.6` | Fraction of capital to System 1 |
| `ATR_PERIOD` | `20` | ATR look-back period |
| `RISK_PER_TRADE` | `0.02` | Risk per unit (2% of equity) |
| `MAX_UNITS_PER_POSITION` | `4` | Max pyramid units (Turtle rule) |
| `STOP_DISTANCE` | `2.0` | Stop distance in N multiples |
| `MAX_COINS` | `10` | Max concurrent open positions |
| `MAX_CORRELATED_COINS` | `2` | Max positions per sector |
| `MAX_TOTAL_RISK` | `0.20` | Max total portfolio risk (20%) |
| `EMERGENCY_STOP_LOSS` | `0.30` | Drawdown to trigger emergency close (30%) |
| `SCAN_TOP_COINS` | `True` | Scan Kraken pairs by 24h volume for coin universe |
| `TOP_N_COINS` | `50` | How many top coins to consider |
| `CHECK_INTERVAL` | `300` | Seconds between bot cycles (5 min) |
| `DASHBOARD_PORT` | `5001` | Flask dashboard TCP port |
| `TRAILING_STOP_ENABLED` | `False` | Enable ATR trailing stops (opt-in) |
| `REGIME_FILTER_ENABLED` | `False` | Enable ADX regime filter (opt-in) |
| `ALERT_ON_DISCORD` | `False` | Send Discord notifications (opt-in) |

---

## State Inspection

```bash
# Pretty-print current state
python -m json.tool bot_state.json

# Summary via utility script
python export_state_to_json.py
```

State is saved atomically (write to `.tmp` then rename) after every cycle — safe against crashes mid-write. See [JSON State README](JSON_STATE_README.md) for the full field reference.

---

## Testing

```bash
pytest
```

The test suite covers positions, state, turtle engine, risk manager, portfolio manager, backtester, analytics, audit trail, dashboard endpoints, exchange adapter, notifications, regime filter, trailing stops, blocked coins, and config validation.

---

## Documentation

- [Web Dashboard Guide](WEB_DASHBOARD_README.md)
- [JSON State Format](JSON_STATE_README.md)
- [Diagnostic Report](DIAGNOSTIC_REPORT.md)

---

## Contributing

This is a personal trading bot project. Feel free to fork and modify for your own use.

## Disclaimer

This bot is for educational and research purposes. Cryptocurrency trading carries significant risk. Always test thoroughly in paper trading mode before using real funds. Past performance does not guarantee future results.

## License

MIT — see [LICENSE](LICENSE)

---

Built with the legendary Turtle Trading methodology.
