# Turtle Bot - JSON State Management

## Overview

The bot saves all state to a single JSON file (`bot_state.json`) after every cycle. Writes are atomic: the bot writes to a `.tmp` file first, then renames it over the target — so a crash mid-write cannot corrupt the state file.

There is no pickle (`.pkl`) file. JSON is the only persistence format.

---

## State File Location

Default: `bot_state.json` in the project root directory.

Configurable via `.env`:
```
STATE_FILE=bot_state.json
```

---

## JSON State Structure

```json
{
  "iteration": 42,
  "initial_equity": 130.0,
  "current_equity": 134.50,
  "peak_equity": 135.00,
  "cash_balance": 90.00,
  "total_pnl": 4.50,
  "total_trades": 3,
  "winning_trades": 2,
  "losing_trades": 1,
  "max_drawdown": 0.02,
  "system_1_symbols": ["BTC/USDT"],
  "system_2_symbols": [],
  "is_paused": false,
  "paused_at": null,
  "pause_reason": "",
  "active_positions": {
    "BTC/USDT": {
      "symbol": "BTC/USDT",
      "exchange": "kraken",
      "system": 1,
      "units": [
        {
          "entry_price": 60000.0,
          "quantity": 0.00043,
          "entry_time": "2026-01-15T10:30:00+00:00"
        }
      ],
      "initial_atr": 2100.0,
      "initial_n": 2100.0,
      "stop_price": 55800.0,
      "avg_entry_price": 60000.0,
      "total_quantity": 0.00043,
      "unrealized_pnl": 1.30,
      "opened_at": "2026-01-15T10:30:00+00:00",
      "last_pyramid_price": 60000.0
    }
  },
  "closed_positions": [
    {
      "symbol": "ETH/USDT",
      "exchange": "kraken",
      "system": 2,
      "units": [...],
      "initial_atr": 120.0,
      "initial_n": 120.0,
      "stop_price": 0.0,
      "avg_entry_price": 3200.0,
      "total_quantity": 0.012,
      "unrealized_pnl": 0.0,
      "opened_at": "2026-01-10T08:00:00+00:00",
      "last_pyramid_price": 3200.0,
      "exit_price": 3350.0,
      "exit_reason": "EXIT_SIGNAL",
      "exit_time": "2026-01-14T16:00:00+00:00",
      "realized_pnl": 1.80
    }
  ],
  "saved_at": "2026-01-15T10:35:00+00:00"
}
```

### Field Reference

| Field | Type | Description |
|-------|------|-------------|
| `iteration` | int | Bot cycle count since startup |
| `initial_equity` | float | Account size at bot start |
| `current_equity` | float | Current equity (cash + unrealized P&L) |
| `peak_equity` | float | Highest equity ever reached |
| `cash_balance` | float | Realized cash (decremented on buy, incremented on sell) |
| `total_pnl` | float | Sum of all realized P&L |
| `total_trades` | int | Count of closed trades |
| `winning_trades` | int | Trades with P&L >= 0 |
| `losing_trades` | int | Trades with P&L < 0 |
| `max_drawdown` | float | Maximum drawdown as fraction (0.05 = 5%) |
| `system_1_symbols` | list | Symbols with active System 1 positions |
| `system_2_symbols` | list | Symbols with active System 2 positions |
| `is_paused` | bool | True = no new entries (existing positions still managed) |
| `paused_at` | str or null | ISO timestamp of when pause was set |
| `pause_reason` | str | Human-readable reason for pause |
| `active_positions` | object | Open positions keyed by symbol |
| `closed_positions` | list | Trade history (archived closed positions) |
| `saved_at` | str | ISO timestamp of last save |

### Position Fields

| Field | Description |
|-------|-------------|
| `symbol` | Trading pair, e.g. `BTC/USDT` |
| `exchange` | Always `kraken` |
| `system` | 1 (20-day) or 2 (55-day) |
| `units` | List of individual units (max 4 per Turtle rules) |
| `initial_atr` | ATR (N) at first entry — locked for life of position |
| `initial_n` | Same as `initial_atr` (alias for clarity) |
| `stop_price` | Current stop: 2N below most recent entry |
| `avg_entry_price` | Cost-weighted average entry across all units |
| `total_quantity` | Sum of all unit quantities |
| `unrealized_pnl` | Last calculated unrealized P&L |
| `opened_at` | ISO timestamp of first unit entry |
| `last_pyramid_price` | Price of most recent unit (for 0.5N pyramid check) |

### Unit Fields

| Field | Description |
|-------|-------------|
| `entry_price` | Price at which this unit was entered |
| `quantity` | Size of this unit in base currency |
| `entry_time` | ISO timestamp |

### Closed Position Additional Fields

| Field | Description |
|-------|-------------|
| `exit_price` | Fill price at close |
| `exit_reason` | `STOP_HIT`, `EXIT_SIGNAL`, or `EMERGENCY_STOP` |
| `exit_time` | ISO timestamp |
| `realized_pnl` | Actual P&L realized at close |

---

## Viewing State

```bash
# Pretty-print (if jq installed)
cat bot_state.json | jq .

# Python
python -m json.tool bot_state.json

# Summary via export utility
python export_state_to_json.py
```

---

## Manual Edits

Stop the bot before editing — the bot overwrites the state file at the end of every cycle.

### Adjust account equity
```json
"current_equity": 500.0,
"initial_equity": 500.0,
"peak_equity": 500.0,
"cash_balance": 500.0
```

### Pause the bot
```json
"is_paused": true,
"pause_reason": "Manual pause for review",
"paused_at": "2026-01-15T10:00:00+00:00"
```

### Reset performance stats (keep positions)
```json
"total_trades": 0,
"winning_trades": 0,
"losing_trades": 0,
"total_pnl": 0.0,
"max_drawdown": 0.0
```

### Fresh start
```bash
rm bot_state.json
# Bot creates a fresh state on next run
```

---

## Atomic Write Safety

The bot writes state as:
1. Write full state to `bot_state.json.tmp`
2. `os.replace(tmp, target)` — atomic on both POSIX and Windows

If the process dies mid-write, only the `.tmp` file is affected. The previous `bot_state.json` remains intact.

---

## Important Notes

- There are no `.pkl` files — JSON is the only persistence format
- There are no automatic `.bak` backups — if you need a backup, copy the file manually before editing
- If `bot_state.json` does not exist on startup, the bot initializes fresh state from `config.py` defaults
- If `bot_state.json` is corrupt (invalid JSON), the bot logs an error and starts fresh

---

**Pro Tip**: Always validate JSON after manual edits before restarting the bot:
```bash
python -m json.tool bot_state.json > /dev/null && echo "JSON valid"
```
