# Turtle Bot - JSON State Management

## What This Does

The bot now saves state in **two formats**:
- **`bot_state.pkl`** - Binary pickle file (fast, not human-readable)
- **`bot_state.json`** - JSON file (human-readable, editable)

Both files are kept in sync automatically!

## How It Works

### Automatic JSON Export
Every time the bot saves state, it creates **both** files:
```bash
bot_state.pkl      # Binary format
bot_state.json     # JSON format (same data, readable)
```

### Loading Priority
When the bot starts, it checks:
1. **If `bot_state.json` exists** → Load from JSON (allows manual edits)
2. **Otherwise** → Load from `bot_state.pkl`

This means you can edit the JSON file and the bot will use your changes!

## Viewing Current State

### Quick Export (anytime)
```bash
cd "Turtle Bot"
./venv/bin/python export_state_to_json.py
```

This shows you a summary and creates/updates `bot_state.json`.

### View the JSON file
```bash
cat bot_state.json | jq .    # Pretty print (if jq installed)
# OR
nano bot_state.json           # Edit directly
```

## JSON State Structure

```json
{
  "price_history": {},           // OHLC data per symbol
  "active_positions": {},        // Currently open positions
  "closed_positions": [],        // Trade history
  "initial_equity": 130.0,       // Starting balance
  "current_equity": 130.0,       // Current balance
  "system_1_symbols": [],        // Symbols in System 1
  "system_2_symbols": [],        // Symbols in System 2
  "total_trades": 0,             // Total trades executed
  "winning_trades": 0,           // Winning trades count
  "losing_trades": 0,            // Losing trades count
  "total_pnl": 0.0,              // Total profit/loss
  "max_drawdown": 0.0,           // Max drawdown (0-1)
  "peak_equity": 130.0,          // Highest equity reached
  "last_update": "2025-12-06...", // Last save timestamp
  "iteration": 1,                // Bot iteration count
  "bot_started": "2025-12-06..." // When bot started
}
```

## Editing State (Manual Adjustments)

### Example: Adjust Account Balance
```bash
nano bot_state.json
```

Change:
```json
"current_equity": 130.0,
```
To:
```json
"current_equity": 500.0,
```

Save and restart the bot - it will load your new balance!

### Example: Clear Trade History
```json
"closed_positions": [],
"total_trades": 0,
"winning_trades": 0,
"losing_trades": 0,
"total_pnl": 0.0
```

### Example: Reset Drawdown
```json
"max_drawdown": 0.0,
"peak_equity": 130.0
```

## Safety Features

### Automatic Backups
Before saving, the bot creates backups:
```bash
bot_state.pkl.bak   # Backup of pickle
bot_state.json.bak  # Backup of JSON
```

### Validation on Load
If the JSON file is corrupted, the bot will:
1. Log an error
2. Fall back to pickle file
3. Start fresh if both fail

## Use Cases

### 1. Adjust Starting Capital
If you want to simulate trading with a different account size without restarting:
```json
"initial_equity": 500.0,
"current_equity": 500.0,
"peak_equity": 500.0
```

### 2. Reset Performance Stats
Keep positions but reset metrics:
```json
"total_trades": 0,
"winning_trades": 0,
"losing_trades": 0,
"total_pnl": 0.0,
"max_drawdown": 0.0
```

### 3. Clear Everything (Fresh Start)
```bash
rm bot_state.json bot_state.pkl
# Bot will create fresh state on next run
```

### 4. Manual Position Entry (Advanced)
You can manually add positions to the JSON, but make sure the format matches exactly:
```json
"active_positions": {
  "BTC/USD": {
    "symbol": "BTC/USD",
    "exchange": "kraken",
    "system": 1,
    "units": [...],
    "initial_atr": 2100.0,
    ...
  }
}
```

## File Locations

All state files are in the `Turtle Bot/` directory:
```
Turtle Bot/
├── bot_state.pkl         # Binary state
├── bot_state.json        # JSON state (editable!)
├── bot_state.pkl.bak     # Pickle backup
└── bot_state.json.bak    # JSON backup
```

## Tips

- **Always backup before manual edits**: `cp bot_state.json bot_state.json.backup`
- **Validate JSON syntax**: Use `jq . bot_state.json` to check formatting
- **Bot must be stopped** when editing (or it will overwrite your changes)
- **JSON takes priority** - If both exist, JSON is loaded first

## Troubleshooting

### Bot ignores my JSON edits
- Make sure the bot is stopped when you edit
- Check JSON syntax is valid: `python -m json.tool bot_state.json`
- Check file permissions: `ls -l bot_state.json`

### JSON file is corrupted
```bash
# Restore from backup
cp bot_state.json.bak bot_state.json

# OR restore from pickle
./venv/bin/python export_state_to_json.py
```

### Start completely fresh
```bash
rm bot_state.*
# Bot creates new state on next run
```

---

**🎯 Pro Tip**: Run `export_state_to_json.py` regularly to keep a readable snapshot of your bot's performance!
