# Turtle Bot - Turtle Trading System for Kraken

## USA Regulatory Compliant

**MADE FOR US TRADERS - FULLY COMPLIANT**

This bot is specifically designed to meet US regulatory requirements:
- **SPOT TRADING ONLY** (no futures, no derivatives)
- **LONG POSITIONS ONLY** (no shorting)
- **NO LEVERAGE** (100% compliant with US regulations)
- **KRAKEN ONLY** (Kraken US spot market, USDT pairs)
- **Regulatory Compliant** for US retail traders

**Why this matters**: Most trading bots use leverage, futures, or shorting — which creates regulatory issues for US traders. This bot is built from the ground up for US compliance.

---

> **API keys are optional.** Paper/read-only mode uses Kraken's public REST API — no account or key required. Keys are only needed for live order execution.

A cryptocurrency trading bot implementing the **Turtle Trading Strategy** with pyramid position management, ATR-based risk sizing, and sector-based correlation filtering.

## Features

### Core Trading System
- **Dual System Implementation**: System 1 (20-day breakout) and System 2 (55-day breakout)
- **Pyramid Position Management**: Scale into positions with up to 4 units at 0.5N intervals
- **ATR-Based Stop Loss**: 2N stop loss, recalculated on each pyramid add
- **Risk-Based Position Sizing**: Each unit risks exactly RISK_PER_TRADE of account equity
- **State Persistence**: Atomic JSON saves (write-to-temp then rename) — safe against crashes
- **Pause/Resume**: Bot can be paused (stops new entries, keeps managing existing positions)

### Exchange & Data
- **Kraken Only**: All OHLC data and order execution goes through Kraken via CCXT
- **CoinGecko (coin discovery only)**: Used to build the trading universe by market cap ranking; no prices from CoinGecko
- **USDT pairs only**: All trading is against USDT
- **Batch fetching**: Symbols are fetched in configurable batches with rate-limit pacing

### Risk Management
- Emergency stop (configurable drawdown threshold closes all positions)
- Max total portfolio risk check before new entries
- Per-sector correlation limits (max N positions per sector)
- Reserve cash buffer (keep a % of balance undeployed)
- Per-position allocation cap
- Kraken minimum order size validation before every order

### Web Dashboard (optional)
- Real-time portfolio tracking via Flask + SocketIO
- Position visualization with pyramid unit display
- Performance metrics: win rate, P&L, max drawdown
- Trade history for closed positions

## Quick Start

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

**Linux/macOS:**
```bash
pip3 install -r requirements.txt
```

3. Configure your settings (copy and edit `.env`):
```bash
cp .env.example .env   # or create .env manually
```

Key `.env` variables:
```
KRAKEN_API_KEY=your_key_here
KRAKEN_API_SECRET=your_secret_here
PAPER_TRADING=True          # Set False only for live trading
ACCOUNT_SIZE=130
```
All other settings have sensible defaults — see `config.py` for the full list.

### Running the Bot

**Windows:**
```powershell
python main.py
```

**Linux/macOS:**
```bash
python3 main.py
```

**Web Dashboard** (requires `web/` directory with Flask app):
```bash
./launch_dashboard.sh
```
The dashboard opens at `http://localhost:5001`

## The Turtle Trading Strategy

The Turtle Trading System is a trend-following strategy developed by Richard Dennis and William Eckhardt. This bot implements:

- **Breakout Entry**: Enter when price breaks above N-day high (20-day for S1, 55-day for S2)
- **Pyramid Scaling**: Add units at 0.5N intervals (max 4 units per position)
- **ATR-Based Stops**: 2N stop loss from most recent entry price
- **Position Sizing**: `Unit USD = (Account × RISK_PER_TRADE) / ATR`
- **Exit Signals**: Close when price breaks below N-day low (10-day for S1, 20-day for S2)

## Project Structure

```
turtle-bot/
├── main.py                   # Main bot entry point
├── config.py                 # All configuration (loads from .env)
├── requirements.txt          # Python dependencies
├── launch_dashboard.sh       # Web dashboard launcher
├── blocked_coins.json        # Coins excluded from trading
├── export_state_to_json.py   # State inspection utility
├── core/
│   ├── position.py           # TurtlePosition and Unit dataclasses
│   └── turtle_engine.py      # ATR calc, signal detection, position sizing
├── exchange/
│   └── base.py               # ExchangeAdapter ABC + CCXTAdapter (Kraken)
├── risk/
│   ├── risk_manager.py       # Risk constraints and validation
│   └── portfolio_manager.py  # Orchestrates stops/exits/pyramids/entries
├── utils/
│   ├── state.py              # BotState: JSON persistence, position tracking
│   ├── notifications.py      # Console output, ANSI colors, alerts
│   ├── multi_exchange.py     # Kraken data fetcher (named for import compat)
│   └── coingecko.py          # CoinGecko API (coin discovery only)
└── misc/
    ├── strategies.json       # Strategy reference configurations
    └── turtlebot-icon.svg    # Bot icon
```

## Configuration

All settings live in `config.py` and are loaded from environment variables (`.env`). Key parameters:

```
# Account
ACCOUNT_SIZE=130              # Starting account size in USD

# Exchange
PAPER_TRADING=True            # True = no real orders placed
KRAKEN_API_KEY=               # Required only for live trading
KRAKEN_API_SECRET=            # Required only for live trading

# Turtle System Parameters
SYSTEM_1_ENABLED=True
SYSTEM_2_ENABLED=True
SYSTEM_SPLIT=0.6              # Fraction of capital allocated to System 1
SYSTEM_1_ENTRY=20             # S1 breakout period (days)
SYSTEM_1_EXIT=10              # S1 exit period (days)
SYSTEM_2_ENTRY=55             # S2 breakout period (days)
SYSTEM_2_EXIT=20              # S2 exit period (days)
ATR_PERIOD=20
RISK_PER_TRADE=0.02           # 2% risk per unit

# Turtle Rules
MAX_UNITS_PER_POSITION=4
PYRAMID_INCREMENT=0.5         # 0.5N price move triggers next unit
STOP_DISTANCE=2.0             # 2N stop loss

# Portfolio
MIN_COINS=2
MAX_COINS=10
MAX_ALLOCATION=0.50           # Max 50% of balance in one position
MAX_CORRELATED_COINS=2        # Max positions per sector

# Risk Limits
MAX_TOTAL_RISK=0.20           # 20% max portfolio risk
EMERGENCY_STOP_LOSS=0.30      # 30% drawdown triggers emergency stop
RESERVE_CASH_PCT=0.10         # Keep 10% cash undeployed

# Data
OHLC_TIMEFRAME=1d
OHLC_LIMIT=60                 # Days of history to fetch
SCAN_TOP_COINS=True           # True = use CoinGecko top-N for universe
TOP_N_COINS=50
BATCH_SIZE=20

# Operations
CHECK_INTERVAL=300            # Seconds between bot cycles (default: 5 min)
STATE_FILE=bot_state.json
LOG_FILE=turtle_signals.log
```

## Trading Loop Priority

Each cycle runs in strict priority order:
1. **Emergency stop check** — if drawdown >= EMERGENCY_STOP_LOSS, close everything
2. **Stop loss hits** — close positions where price <= 2N stop
3. **Exit signals** — close positions on N-day low breakdown
4. **Pyramid opportunities** — add units to winning positions at 0.5N
5. **New entry signals** — open new positions on N-day high breakout

## State Management

Bot state is saved to `bot_state.json` after every cycle using atomic writes (temp file + rename). This prevents corruption if the process dies mid-write.

State includes: equity tracking, all active and closed positions, trade statistics, system symbol lists, and pause status.

To inspect state:
```bash
python export_state_to_json.py   # prints summary and validates state
cat bot_state.json               # raw JSON
```

## Utilities

### Export/Inspect State
**Windows:**
```powershell
python export_state_to_json.py
```

**Linux/macOS:**
```bash
python3 export_state_to_json.py
```

## Risk Management Details

Built-in risk controls (applied in this order):
1. Emergency stop (portfolio-level drawdown)
2. Total portfolio risk cap (MAX_TOTAL_RISK)
3. Max concurrent positions (MAX_COINS)
4. Reserve cash requirement (RESERVE_CASH_PCT)
5. Per-position allocation cap (MAX_ALLOCATION)
6. Sector correlation limit (MAX_CORRELATED_COINS)
7. Kraken minimum order size / notional value

## Documentation

- [Web Dashboard Guide](WEB_DASHBOARD_README.md)
- [JSON State Format](JSON_STATE_README.md)
- [Diagnostic Report](DIAGNOSTIC_REPORT.md)

## Contributing

This is a personal trading bot project. Feel free to fork and modify for your own use.

## Disclaimer

This bot is for educational and research purposes. Cryptocurrency trading carries significant risk. Always test thoroughly in paper trading mode before using real funds. Past performance does not guarantee future results.

## License

MIT — see [LICENSE](LICENSE)

---

**Built with the legendary Turtle Trading methodology.**
