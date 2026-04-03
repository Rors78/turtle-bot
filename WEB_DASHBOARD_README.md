# Turtle Bot - Web Dashboard

## Overview

The web dashboard is an optional Flask + SocketIO interface that displays live bot state while the main bot (`main.py`) runs in the background.

> **Note**: The `web/` directory containing `app.py` is not included in this repository. The dashboard scripts and documentation describe the expected interface for anyone building or restoring that component.

---

## Quick Start

```bash
./launch_dashboard.sh
```

The script will:
1. Start the Flask server (`web/app.py`)
2. Attempt to open the browser automatically at `http://localhost:5001`

### Manual Start

```bash
python web/app.py
# Then open http://localhost:5001 in your browser
```

---

## How It Works

### Backend (Flask + SocketIO)
- Reads bot state from `bot_state.json` (same file `main.py` writes to)
- Pushes updates to the browser via WebSocket every ~5 seconds
- No database required — state file is the single source of truth

### Frontend (HTML + CSS + JavaScript)
- WebSocket client for real-time updates (no page reload required)
- Displays positions, performance metrics, and trade history

### Integration with Main Bot
Run both simultaneously:
```bash
# Terminal 1 — run the bot
python main.py

# Terminal 2 — run the dashboard
./launch_dashboard.sh
```

The dashboard reads `bot_state.json` which the bot writes after every cycle.

---

## Dashboard Sections

### Header
- Current equity
- Total P&L (color-coded green/red)
- Active position count
- Mode badge (PAPER or LIVE)

### Systems Overview
- System 1 (20-day breakout) status and capital allocation
- System 2 (55-day breakout) status and capital allocation
- Active positions per system

### Active Positions
- Per-position card: symbol, system, entry price, stop price, unrealized P&L
- Pyramid unit visualization (shows which of 4 units are filled)

### Bot Thinking Log
- Real-time log stream (color-coded by severity: info/success/warning/error)
- Entry decisions, exit signals, stop hits, errors

### Performance Metrics
- Win rate
- Total trades
- Max drawdown
- Total P&L and return

### Trade History
- Last 10 closed positions
- Entry/exit prices, P&L, exit reason, system number

---

## Configuration

### Change Port
In `web/app.py`, find the `socketio.run(...)` call and change the port:
```python
socketio.run(app, host='0.0.0.0', port=5001, ...)  # change 5001 to your port
```

### Change Refresh Rate
In `web/static/js/dashboard.js`:
```javascript
setInterval(() => {
    socket.emit('request_update');
}, 5000);  // milliseconds
```

---

## Dependencies

The dashboard requires these packages (included in `requirements.txt`):
```
flask>=3.0.0
flask-socketio>=5.3.0
flask-cors>=4.0.0
```

---

## Troubleshooting

### Dashboard won't start
- Confirm `web/app.py` exists
- Check port 5001 is not already in use: `lsof -i :5001` (Linux/macOS) or `netstat -ano | findstr 5001` (Windows)
- Try a different port (see Configuration above)

### No data showing
- Confirm `bot_state.json` exists in the project root
- Run `main.py` once to generate initial state
- Refresh the browser

### Connection lost (red badge)
- Check the Flask server process is still running
- Restart with `./launch_dashboard.sh`

### Browser doesn't auto-open
- Navigate manually to `http://localhost:5001`

---

## Mobile Access

To view the dashboard on a phone or tablet on the same network:

1. Find the host machine's local IP:
   ```bash
   hostname -I      # Linux
   ipconfig         # Windows
   ```
2. On the mobile device, navigate to `http://<HOST-IP>:5001`
