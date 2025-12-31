# 🐢 Turtle Bot - Advanced Turtle Trading System

A sophisticated cryptocurrency trading bot implementing the famous **Turtle Trading Strategy** with modern enhancements, real-time web dashboard, and pyramid position management.

## ✨ Features

### Core Trading System
- **Dual System Implementation**: System 1 (20-day breakout) and System 2 (55-day breakout)
- **Pyramid Position Management**: Scale into positions with up to 4 units
- **Dynamic Stop Loss**: ATR-based stop loss management
- **Risk Management**: Position sizing based on account equity and volatility
- **State Persistence**: Automatic save/load of bot state for resilience

### Web Dashboard
- **Real-Time Updates**: Live portfolio tracking via WebSocket
- **Glassmorphism Design**: Modern, professional UI with animated backgrounds
- **Position Visualization**: See all pyramid units, entry prices, and stop losses
- **Bot Thinking Log**: Watch the bot's decision-making process in real-time
- **Performance Metrics**: Win rate, profit factor, max drawdown, and more
- **Trade History**: Complete record of closed positions

### Technical Features
- **Exchange Integration**: Built-in support for cryptocurrency exchanges
- **JSON State Export**: Export bot state for analysis
- **Diagnostic Reports**: Comprehensive system diagnostics
- **Configuration Management**: Easy-to-modify config.py
- **Blocked Coins List**: Avoid problematic trading pairs

## 🚀 Quick Start

### Installation

1. Clone the repository:
```bash
git clone https://github.com/Rors78/turtle-bot.git
cd turtle-bot
```

2. Install dependencies:
```bash
pip install -r requirements.txt
```

3. Configure your settings in `config.py`:
- Set your exchange API keys
- Adjust risk parameters
- Configure trading systems

### Running the Bot

**Terminal Mode:**
```bash
python main.py
```

**Web Dashboard:**
```bash
./launch_dashboard.sh
```
The dashboard will automatically open at `http://localhost:5001`

## 📊 The Turtle Trading Strategy

The Turtle Trading System is a legendary trend-following strategy developed by Richard Dennis and William Eckhardt in the 1980s. This bot implements:

- **Breakout Entry**: Enter when price breaks above/below N-day high/low
- **Pyramid Scaling**: Add to winning positions at predetermined intervals
- **ATR-based Stops**: Volatility-adjusted stop losses
- **Position Sizing**: Risk-based position calculation using N (ATR)

## 📁 Project Structure

```
turtle-bot/
├── main.py                   # Main bot entry point
├── config.py                 # Configuration settings
├── requirements.txt          # Python dependencies
├── launch_dashboard.sh       # Web dashboard launcher
├── core/
│   ├── position.py          # Position management
│   └── turtle_engine.py     # Core trading logic
├── exchange/
│   └── base.py              # Exchange integration
├── misc/
│   ├── strategies.json      # Strategy configurations
│   └── turtlebot-icon.svg   # Bot icon
├── blocked_coins.json       # Coins to avoid
├── export_state_to_json.py  # State export utility
├── DIAGNOSTIC_REPORT.md     # System diagnostics
├── JSON_STATE_README.md     # State format documentation
└── WEB_DASHBOARD_README.md  # Dashboard documentation
```

## 🎨 Web Dashboard Features

### Real-Time Monitoring
- Live portfolio value and P&L
- Active positions with pyramid visualization
- System 1 and System 2 status
- Connection status indicator

### Performance Analytics
- Win rate with visual progress bar
- Profit factor calculation
- Total trades counter
- Maximum drawdown tracking

### Trading Insights
- Bot decision log with color-coded severity
- Entry/exit reasoning
- Stop loss hits and adjustments
- Error messages and warnings

## ⚙️ Configuration

Key settings in `config.py`:

```python
# Trading Parameters
SYSTEM_1_PERIOD = 20  # Short-term breakout
SYSTEM_2_PERIOD = 55  # Long-term breakout
MAX_PYRAMID_UNITS = 4  # Maximum position size
ATR_MULTIPLIER = 2.0   # Stop loss distance

# Risk Management
RISK_PER_TRADE = 0.01  # 1% risk per trade
MAX_POSITIONS = 5       # Maximum concurrent positions
```

## 📈 Performance Tracking

The bot automatically tracks:
- Total P&L (realized and unrealized)
- Win/Loss ratio
- Profit factor
- Maximum drawdown
- Average trade duration
- System 1 vs System 2 performance

## 🔧 Utilities

### Export State to JSON
```bash
python export_state_to_json.py
```
Converts bot state to human-readable JSON format.

### View Diagnostics
```bash
cat DIAGNOSTIC_REPORT.md
```
Review system health and performance diagnostics.

## 🛡️ Risk Management

Built-in risk controls:
- Position size limits based on account equity
- Maximum concurrent positions
- ATR-based stop losses
- Correlation checks (avoid overexposure)
- Blocked coins list
- Emergency stop functionality

## 📝 Documentation

- [Web Dashboard Guide](WEB_DASHBOARD_README.md) - Complete dashboard documentation
- [JSON State Format](JSON_STATE_README.md) - State file structure
- [Diagnostic Report](DIAGNOSTIC_REPORT.md) - System diagnostics

## 🤝 Contributing

This is a personal trading bot project. Feel free to fork and modify for your own use.

## ⚠️ Disclaimer

This bot is for educational and research purposes. Cryptocurrency trading carries significant risk. Always test thoroughly in paper trading mode before using real funds. Past performance does not guarantee future results.

## 📄 License

This project is provided as-is for personal use and learning.

---

**Built with the legendary Turtle Trading methodology** 🐢
