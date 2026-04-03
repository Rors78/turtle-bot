# Turtle Bot - Diagnostic Report

> **NOTICE: This report was written against the pre-refactor architecture (Phase 0).**
> It describes a multi-exchange setup (Kraken + Binance US + CoinGecko fallback) that no longer exists.
> The current architecture (Phase 1+2) is Kraken-only for data and execution.
> **Run a fresh diagnostic against the current code before relying on this document.**

---

## Current Architecture (Phase 1+2 — Kraken-Only Refactor)

The refactor made the following structural changes:

- **Exchange**: Kraken only. `CCXTAdapter` enforces this — passing any exchange name other than `'kraken'` raises `ValueError`.
- **Market data**: All OHLC and price data fetched from Kraken via CCXT. No Binance US. No CoinGecko price fallback.
- **CoinGecko role**: Coin discovery only (market cap ranking to build trading universe). Uses stdlib `urllib` — no `requests` dependency.
- **State persistence**: JSON only (`bot_state.json`). Atomic writes (temp file + rename). No pickle files.
- **`utils/multi_exchange.py`**: Renamed conceptually to a Kraken-only fetcher. Kept the class name `MultiExchangeFetcher` for import compatibility with `main.py`, but there is no fallback chain.
- **Risk manager**: Added Kraken-specific minimum order/notional validation (`validate_kraken_order`).
- **Portfolio manager**: Directly references `exchanges['kraken']`; no exchange-selection logic.

---

## Configuration Summary (current defaults)

```
Account:        $130.00
Mode:           PAPER TRADING
Exchange:       Kraken (data + execution)
Coin discovery: CoinGecko (market cap ranking only)
Quote:          USDT only

Systems:
  System 1 (20-day breakout): 60% capital
  System 2 (55-day breakout): 40% capital

Turtle Rules:
  ATR Period:   20 days
  Risk/Trade:   2.0%
  Max Units:    4
  Pyramid:      0.5N
  Stop:         2.0N

Risk Limits:
  Max Total:    20%
  Emergency:    30% drawdown
  Reserve:      10% cash

Portfolio:
  Max Positions: 10
  Max Per Sector: 2
  Coin Universe: Top 50 coins from CoinGecko (batches of 20)

Check Interval: 5 minutes
State File:     bot_state.json
Log File:       turtle_signals.log
```

---

## Pre-Refactor Diagnostic (archived — old architecture)

**Date**: December 8, 2025
**Status at that time**: Fixed and operational (pre-refactor)

### Issue Resolved at That Time

**Problem**: `CoinGeckoAPI.__init__()` received unexpected keyword argument `rate_limit`

**Fix applied (pre-refactor)**:
```python
# BEFORE (broken):
self.coingecko = CoinGeckoAPI(rate_limit=3.0)

# AFTER (fixed at the time):
self.coingecko = CoinGeckoAPI(max_requests_per_minute=20)
```

This issue no longer applies — CoinGecko is no longer initialized in `multi_exchange.py`. The `CoinGeckoAPI` class takes no constructor arguments in the current code and is only instantiated inside `main.py`'s `get_coin_universe()` function.

### Tests Performed (pre-refactor, results no longer valid)

The following test results described a **two-exchange setup that no longer exists**:
- Kraken: 1397 markets loaded
- Binance US: 612 markets loaded (Binance US has been removed)
- CoinGecko as price fallback (no longer used for prices)
- `bot_state.pkl` (pickle state files no longer used)

---

## How to Run a Fresh Diagnostic

```bash
# 1. Verify all imports resolve
python -c "from main import run_bot; print('imports OK')"

# 2. Check config loads without error
python -c "from config import load_config; c = load_config(); print('config OK')"

# 3. Run one cycle in paper trading mode
python main.py
# Press Ctrl+C after first cycle completes

# 4. Inspect state
cat bot_state.json

# 5. Check logs
tail -50 turtle_signals.log
```

---

## Pause / Resume Control

The bot respects `is_paused` in `bot_state.json`. When paused:
- New entry signals are skipped
- Existing positions continue to be managed (stops, exits, pyramids still run)

To pause manually, stop the bot, edit `bot_state.json`:
```json
{
  "is_paused": true,
  "pause_reason": "Manual pause",
  "paused_at": "2026-01-01T12:00:00+00:00"
}
```
Then restart.

---

## Log Files

- **Bot log**: `turtle_signals.log` (rotating, appended each run)
- **State file**: `bot_state.json`
- **Temp state** (during save): `bot_state.json.tmp` (deleted automatically)
