# Turtle Bot — Diagnostic Report

## Current Architecture

This document describes the current codebase. All pre-refactor content (multi-exchange setup, Binance US, pickle state files, SocketIO dashboard) has been removed.

### Core Design Decisions

| Concern | Decision |
|---------|----------|
| Exchange | **Kraken only** — `CCXTAdapter` raises `ValueError` if any other exchange name is passed |
| Market data | **Kraken OHLC via CCXT** — no Binance US, no CoinGecko price fallback |
| Coin discovery | **CoinGecko** (market cap ranking only) — uses stdlib `urllib`, no `requests` dependency |
| State persistence | **JSON only** (`bot_state.json`) — atomic writes (temp file + rename), no pickle files |
| Dashboard | **Plain Flask + polling** — vanilla JS polls `/api/state` every 30 seconds; no WebSockets, no SocketIO |
| Opt-in features | **Trailing stops**, **regime detection**, **Discord alerts** — all `False` by default |

---

## Configuration Defaults

All values are loaded from `.env` via `config.py`. This table shows the factory defaults:

```
Account:          $130.00
Mode:             PAPER TRADING
Exchange:         Kraken (data + execution)
Quote currency:   USDT only
Coin discovery:   CoinGecko top-50 by market cap (batches of 20)

Systems:
  System 1 (20-day breakout):  60% capital  (SYSTEM_SPLIT=0.6)
  System 2 (55-day breakout):  40% capital

Turtle Rules:
  ATR Period:        20 days
  Risk per trade:    2.0%
  Max units:         4
  Pyramid increment: 0.5N
  Stop distance:     2.0N

Portfolio:
  Min positions:     2
  Max positions:     10
  Min allocation:    10% per position
  Max allocation:    50% per position
  Max per sector:    2

Risk Limits:
  Max total risk:    20%
  Emergency stop:    30% drawdown
  Reserve cash:      10%
  Min balance:       $100.00

Operational:
  Check interval:    300 seconds (5 minutes)
  State file:        bot_state.json
  Log file:          turtle_signals.log
  Audit file:        trade_audit.jsonl
  Log format:        json (structured JSON Lines)
  Paper slippage:    0.1%

Dashboard:
  Port:              5001
  Stale threshold:   15 minutes (2x check interval)

Opt-in features (all disabled by default):
  Trailing stops:    TRAILING_STOP_ENABLED=False  (method: atr, distance: 2.0N)
  Regime filter:     REGIME_FILTER_ENABLED=False  (ADX period: 14, min ADX: 25.0)
  Discord alerts:    ALERT_ON_DISCORD=False
```

---

## Known Limitations

### Small Account ($130)

The Turtle formula sizes positions by risk, not capital:

```
Unit size = (Account × RISK_PER_TRADE) / ATR
           = (130 × 0.02) / ATR
           = $2.60 / ATR
```

Most Kraken USDT pairs require a minimum order of $10–$25 notional value. At $130 with 2% risk, the bot will frequently calculate a unit size below the exchange minimum and skip the trade. This is expected behaviour — the bot logs these skips rather than override the minimum. Options:

- Increase `RISK_PER_TRADE` (e.g. `0.05` = 5%) to size larger units — departs from standard Turtle rules
- Wait for the account to grow through winning trades
- Add capital to the account

### Backtester Coin Universe

The backtester (`run_backtest.py`) uses the fixed coin list in `config.py` (`FIXED_COINS`), not the live CoinGecko top-N scan. This is intentional — backtests must be reproducible and cannot depend on a changing universe. Current fixed coins: BTC, ETH, XRP, SOL, LINK, TRX, ADA, HYPE, XLM.

### CoinGecko Rate Limits

The CoinGecko free tier limits requests to approximately 30 per minute. When a `429 Too Many Requests` response is received, the bot sleeps for 60 seconds before retrying. If you run `SCAN_TOP_COINS=True` with a very small `BATCH_SIZE` and many cycles in quick succession, you may encounter back-offs. Increase `BATCH_SIZE` or reduce `TOP_N_COINS` to mitigate.

### Regime Filter and Backtester

The regime filter (ADX) can be applied during backtesting via `test_regime_backtest.py` but is not wired into the `run_backtest.py` CLI by default. Enable it by setting `REGIME_FILTER_ENABLED=True` in `.env` before running the backtester.

---

## Diagnostic Commands

Run these commands to verify the installation is working correctly:

```bash
# 1. Verify all imports resolve
python -c "from main import run_bot; print('imports OK')"

# 2. Check config loads and validates without error
python -c "from config import load_config; c = load_config(); print('config OK')"

# 3. Confirm flask-socketio is not imported (expected: no output)
grep -r "socketio\|SocketIO" --include="*.py" .

# 4. Run the full test suite
pytest

# 5. Run one cycle in paper trading mode, then Ctrl+C
python main.py

# 6. Inspect the generated state file
python -m json.tool bot_state.json

# 7. Run a backtest
python run_backtest.py --days 90 --account-size 130

# 8. Start the dashboard and verify endpoints
python web/app.py &
curl http://localhost:5001/health
curl http://localhost:5001/api/state | python -m json.tool
```

---

## Pause / Resume Control

The bot respects `is_paused` in `bot_state.json`. When paused:

- New entry signals are skipped
- Existing positions continue to be managed (stops, exits, and pyramids still run)

To pause manually, stop the bot, edit `bot_state.json`:

```json
{
  "is_paused": true,
  "pause_reason": "Manual pause for review",
  "paused_at": "2026-01-01T12:00:00+00:00"
}
```

Then restart. Resume by setting `is_paused` back to `false`.

---

## Log Files

| File | Format | Description |
|------|--------|-------------|
| `turtle_signals.log` | JSON Lines (file) / plain text (console) | Main bot log, rotating |
| `bot_state.json` | JSON | Full bot state, written after every cycle |
| `bot_state.json.tmp` | JSON | Temporary write target (deleted on successful rename) |
| `trade_audit.jsonl` | JSON Lines | Append-only fill audit trail |

---

## Build History

| Phase | Changes |
|-------|---------|
| Phase 0 (3 fixes) | Fixed `CoinGeckoAPI` constructor bug; fixed pickle state corruption; fixed Kraken pair formatting |
| Phase 1 (8 upgrades) | Kraken-only refactor (removed Binance US); JSON-only state; atomic writes; retry/back-off; structured logging; audit trail; sector correlation filter; Kraken minimum order validation |
| Phase 2 (101 tests + CI) | 17 test files covering all modules; GitHub Actions CI pipeline; pytest configuration |
| Phase 3A (backtester + analytics + Discord) | Walk-forward backtester (`run_backtest.py`); Sharpe/Sortino/Calmar/profit factor analytics module; Discord webhook notifications |
| Phase 3B (dashboard + trailing stops + regime) | Flask polling dashboard replacing SocketIO stub; trailing stop implementation (`update_trailing_stop`); ADX regime filter; equity history tracking in BotState |
| Analytics fix | Fixed Sharpe/Sortino calculations to use daily return series from `equity_history` rather than raw P&L values |
| Backtester sizing fix | Fixed position size calculation in backtester to apply `RESERVE_CASH_PCT` and Kraken minimum order checks — matches live bot behaviour |
