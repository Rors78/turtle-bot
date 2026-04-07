#!/usr/bin/env python3
"""
╔══════════════════════════════════════════════════════════════════════════════╗
║  ████████╗██╗   ██╗██████╗ ████████╗██╗     ███████╗██████╗  ██████╗ ████████╗  ║
║  ╚══██╔══╝██║   ██║██╔══██╗╚══██╔══╝██║     ██╔════╝██╔══██╗██╔═══██╗╚══██╔══╝ ║
║     ██║   ██║   ██║██████╔╝   ██║   ██║     █████╗  ██████╔╝██║   ██║   ██║    ║
║     ██║   ██║   ██║██╔══██╗   ██║   ██║     ██╔══╝  ██╔══██╗██║   ██║   ██║    ║
║     ██║   ╚██████╔╝██║  ██║   ██║   ███████╗███████╗██████╔╝╚██████╔╝   ██║    ║
║     ╚═╝    ╚═════╝ ╚═╝  ╚═╝   ╚═╝   ╚══════╝╚══════╝╚═════╝  ╚═════╝    ╚═╝   ║
║                                                                                  ║
║         ULTRA  ──  The Original 1983 Rules, Rebuilt for Crypto                   ║
║         ══════════════════════════════════════════════════════                    ║
║         "We are going to grow traders just like they grow                        ║
║          turtles in Singapore."  ── Richard Dennis, 1983                         ║
║                                                                                  ║
║   System 1: 20-day breakout entry │ 10-day contrary breakout exit                ║
║   System 2: 55-day breakout entry │ 20-day contrary breakout exit                ║
║   Position Sizing: Volatility-normalized units (1% equity per N)                 ║
║   Pyramiding: Up to 4 units at ½N intervals                                     ║
║   Stops: 2N from entry, raised ½N per add                                       ║
║   Risk Limits: 4/market, 6/correlated, 10/loose, 12/direction                   ║
║   Drawdown: -20% notional per -10% equity loss                                  ║
║                                                                                  ║
║   Paper Trading Engine │ Kraken OHLC Data │ Pydroid3 Compatible                  ║
╚══════════════════════════════════════════════════════════════════════════════╝

Author : Claude × Jeremy
Version: 1.0.0 ULTRA
License: MIT
"""

import json
import logging
import time
import os
import sys
import threading
from datetime import datetime, timezone, timedelta
from typing import Dict, List, Optional, Tuple
try:
    import urllib.request as urlreq
    import urllib.error as urlerr
except ImportError:
    import urllib2 as urlreq
    urlerr = urlreq

# Fleet bus listener
from pathlib import Path as _Path
sys.path.insert(0, str(_Path(__file__).resolve().parent.parent / "CommandCenter"))
try:
    from bus_listener import BusListener as _BusListener
except ImportError:
    _BusListener = None
try:
    from event_publisher import EventPublisher as _EventPublisher
except ImportError:
    _EventPublisher = None
try:
    from expectancy import ExpectancyTracker
    _expectancy = ExpectancyTracker()
except Exception:
    _expectancy = None
try:
    from fleet_config import is_blacklisted as _is_blacklisted
except ImportError:
    _is_blacklisted = lambda pair: False
try:
    from portfolio_client import PortfolioClient
except ImportError:
    PortfolioClient = None

# ═══════════════════════════════════════════════════════════════
# ANSI ESCAPE CODES (Pydroid3 compatible)
# ═══════════════════════════════════════════════════════════════
ESC       = "\033["
RESET     = f"{ESC}0m"
BOLD      = f"{ESC}1m"
DIM       = f"{ESC}2m"
ITALIC    = f"{ESC}3m"
ULINE     = f"{ESC}4m"
# Foreground
BLACK     = f"{ESC}30m"
RED       = f"{ESC}31m"
GREEN     = f"{ESC}32m"
YELLOW    = f"{ESC}33m"
BLUE      = f"{ESC}34m"
MAGENTA   = f"{ESC}35m"
CYAN      = f"{ESC}36m"
WHITE     = f"{ESC}37m"
# Bright foreground
BRED      = f"{ESC}91m"
BGREEN    = f"{ESC}92m"
BYELLOW   = f"{ESC}93m"
BBLUE     = f"{ESC}94m"
BMAGENTA  = f"{ESC}95m"
BCYAN     = f"{ESC}96m"
BWHITE    = f"{ESC}97m"
# Background
BG_BLACK  = f"{ESC}40m"
BG_RED    = f"{ESC}41m"
BG_GREEN  = f"{ESC}42m"
BG_YELLOW = f"{ESC}43m"
BG_BLUE   = f"{ESC}44m"
BG_DGRAY  = f"{ESC}100m"
CLEAR     = f"{ESC}2J{ESC}H"

# ═══════════════════════════════════════════════════════════════
# CONFIGURATION
# ═══════════════════════════════════════════════════════════════

CONFIG = {
    # ── Account ──
    "starting_equity": 130.00,       # Paper trading starting balance
    "risk_per_unit_pct": 1.0,       # 1% of equity per unit (original rule)
    "max_risk_per_trade_pct": 2.0,  # 2% max risk per trade (2N stop)

    # ── N (ATR) Calculation ──
    "n_period": 20,                 # 20-day EMA for N (original rule)

    # ── Entry Rules ──
    "s1_entry_days": 20,            # System 1: 20-day breakout
    "s2_entry_days": 55,            # System 2: 55-day breakout
    "s1_failsafe_days": 55,         # System 1 failsafe breakout

    # ── Exit Rules ──
    "s1_exit_days": 10,             # System 1: 10-day contrary breakout
    "s2_exit_days": 20,             # System 2: 20-day contrary breakout

    # ── Pyramiding ──
    "add_interval_n": 0.5,          # Add at ½N intervals (original rule)
    "max_units_per_market": 4,      # Max 4 units per market (original rule)

    # ── Stop Loss ──
    "stop_n_multiplier": 2.0,       # 2N stop (original rule)
    "stop_tighten_n": 0.5,          # Raise stops ½N per add (original rule)

    # ── Portfolio Risk Limits (original rules) ──
    "max_units_single_market": 4,
    "max_units_closely_correlated": 6,
    "max_units_loosely_correlated": 10,
    "max_units_single_direction": 12,

    # ── Drawdown Adjustment (original rule) ──
    "drawdown_threshold_pct": 10.0, # Reduce notional at -10%
    "drawdown_reduce_pct": 20.0,    # Reduce by 20%

    # ── System Allocation ──
    "system_mode": "BOTH",          # "S1", "S2", or "BOTH" (50/50 split)

    # ── Data ──
    "ohlc_interval": 1440,          # Daily candles (1440 min)
    "lookback_days": 120,           # Enough for 55-day channels + N calc
    "refresh_seconds": 300,         # Poll every 5 minutes

    # ── Display ──
    "terminal_width": 78,

    # ── Dashboard ──
    "dashboard_port": 5001,

    # ── Central Portfolio (Command Center shared capital pool) ──
    "use_central_portfolio": False,   # Fleet capital pool via Command Center
    "command_center_url": "http://127.0.0.1:9000",
}

# ── Markets to Trade ──
# Kraken pairs: [ticker, display_name, correlation_group]
# Correlation groups: BTC, ETH, DEFI, L1, MEME, STABLE
MARKETS = [
    ("XXBTZUSD",  "BTC/USD",   "BTC"),
    ("XETHZUSD",  "ETH/USD",   "ETH"),
    ("SOLUSD",    "SOL/USD",   "L1"),
    ("XLTCZUSD",  "LTC/USD",   "BTC"),
    ("LINKUSD",   "LINK/USD",  "DEFI"),
    ("XXLMZUSD",  "XLM/USD",   "L1"),
    ("XXRPZUSD",  "XRP/USD",   "L1"),
    ("DOTUSD",    "DOT/USD",   "L1"),
    ("AAVEUSD",   "AAVE/USD",  "DEFI"),
    ("UNIUSD",    "UNI/USD",   "DEFI"),
]
# Fleet blacklist filter — remove pairs with 0% WR across fleet
MARKETS = [m for m in MARKETS if not _is_blacklisted(m[0])]

# Correlation map for risk limits
CORRELATION_MAP = {
    "closely": [
        ("BTC", "LTC"),   # Both PoW store-of-value
        ("ETH", "DEFI"),  # ETH ecosystem
    ],
    "loosely": [
        ("BTC", "ETH"),
        ("BTC", "L1"),
        ("ETH", "L1"),
        ("DEFI", "L1"),
    ],
}


# ═══════════════════════════════════════════════════════════════
# DATA LAYER: Kraken OHLC
# ═══════════════════════════════════════════════════════════════

class KrakenData:
    """Fetches and manages OHLC data from Kraken public API."""

    BASE_URL = "https://api.kraken.com/0/public"
    RATE_LIMIT = 1.0  # seconds between calls (Kraken public API ~1 req/s)

    def __init__(self):
        self.cache: Dict[str, List[dict]] = {}
        self._last_call = 0.0

    def _throttle(self):
        elapsed = time.time() - self._last_call
        if elapsed < self.RATE_LIMIT:
            time.sleep(self.RATE_LIMIT - elapsed)
        self._last_call = time.time()

    def _fetch_json(self, endpoint: str, params: dict) -> dict:
        self._throttle()
        qs = "&".join(f"{k}={v}" for k, v in params.items())
        url = f"{self.BASE_URL}/{endpoint}?{qs}"
        try:
            req = urlreq.Request(url, headers={"User-Agent": "TurtleBotULTRA/1.0"})
            with urlreq.urlopen(req, timeout=15) as resp:
                return json.loads(resp.read().decode())
        except Exception as e:
            return {"error": [str(e)]}

    def fetch_ohlc(self, pair: str, interval: int = 1440,
                   since: Optional[int] = None) -> List[dict]:
        """Fetch OHLC candles. Returns list of dicts with
        time, open, high, low, close, volume, vwap, count."""
        params = {"pair": pair, "interval": interval}
        if since:
            params["since"] = since

        data = self._fetch_json("OHLC", params)
        if data.get("error") and len(data["error"]) > 0:
            return []

        result = data.get("result", {})
        # Kraken returns data under the pair key (varies)
        candles = []
        for key in result:
            if key == "last":
                continue
            raw = result[key]
            for c in raw:
                candles.append({
                    "time":   int(c[0]),
                    "open":   float(c[1]),
                    "high":   float(c[2]),
                    "low":    float(c[3]),
                    "close":  float(c[4]),
                    "vwap":   float(c[5]),
                    "volume": float(c[6]),
                    "count":  int(c[7]),
                })
            break
        candles.sort(key=lambda x: x["time"])
        self.cache[pair] = candles
        return candles

    def fetch_ticker(self, pair: str) -> Optional[dict]:
        """Fetch current ticker data."""
        data = self._fetch_json("Ticker", {"pair": pair})
        if data.get("error") and len(data["error"]) > 0:
            return None
        result = data.get("result", {})
        for key in result:
            t = result[key]
            return {
                "ask":    float(t["a"][0]),
                "bid":    float(t["b"][0]),
                "last":   float(t["c"][0]),
                "volume": float(t["v"][1]),  # 24h volume
                "vwap":   float(t["p"][1]),
                "high":   float(t["h"][1]),
                "low":    float(t["l"][1]),
            }
        return None

    def fetch_all_tickers(self, pairs: List[str]) -> Dict[str, dict]:
        """Fetch tickers for all pairs in a single API call."""
        if not pairs:
            return {}
        self._throttle()
        pair_str = ",".join(pairs)
        data = self._fetch_json("Ticker", {"pair": pair_str})
        if data.get("error") and len(data.get("error", [])) > 0:
            logging.warning(f"Ticker batch error: {data['error']}")
            return {}
        result_data = data.get("result", {})
        result = {}
        for key, t in result_data.items():
            for p in pairs:
                if p in key or key in p:
                    result[p] = {
                        "ask":    float(t["a"][0]),
                        "bid":    float(t["b"][0]),
                        "last":   float(t["c"][0]),
                        "volume": float(t["v"][1]),
                        "vwap":   float(t["p"][1]),
                        "high":   float(t["h"][1]),
                        "low":    float(t["l"][1]),
                    }
                    break
        return result

    def get_all_ohlc(self, markets: list, interval: int = 1440,
                     lookback_days: int = 120) -> Dict[str, List[dict]]:
        """Fetch OHLC for all markets."""
        since = int((datetime.now(timezone.utc) -
                     timedelta(days=lookback_days)).timestamp())
        result = {}
        for pair, name, group in markets:
            candles = self.fetch_ohlc(pair, interval, since)
            if candles:
                result[pair] = candles
        return result


# ═══════════════════════════════════════════════════════════════
# TURTLE MATH ENGINE
# ═══════════════════════════════════════════════════════════════

class TurtleMath:
    """Pure calculation functions for the Turtle system."""

    @staticmethod
    def true_range(high: float, low: float, prev_close: float) -> float:
        """True Range = max(H-L, |H-PDC|, |PDC-L|)"""
        return max(high - low, abs(high - prev_close), abs(prev_close - low))

    @staticmethod
    def compute_n(candles: List[dict], period: int = 20) -> Optional[float]:
        """Compute N = 20-day EMA of True Range (the original ATR).
        Uses simple average for initial seed, then EMA formula:
        N = (19 * PDN + TR) / 20
        """
        if len(candles) < period + 1:
            return None

        # Initial N: simple average of first `period` true ranges
        trs = []
        for i in range(1, period + 1):
            tr = TurtleMath.true_range(
                candles[i]["high"], candles[i]["low"], candles[i-1]["close"]
            )
            trs.append(tr)
        n = sum(trs) / len(trs)

        # EMA continuation
        for i in range(period + 1, len(candles)):
            tr = TurtleMath.true_range(
                candles[i]["high"], candles[i]["low"], candles[i-1]["close"]
            )
            n = (19 * n + tr) / 20  # Original formula from the document

        return n

    @staticmethod
    def compute_n_series(candles: List[dict], period: int = 20) -> List[Optional[float]]:
        """Compute N for every candle (None for insufficient data)."""
        n_series = [None] * len(candles)
        if len(candles) < period + 1:
            return n_series

        # Seed
        trs = []
        for i in range(1, period + 1):
            tr = TurtleMath.true_range(
                candles[i]["high"], candles[i]["low"], candles[i-1]["close"]
            )
            trs.append(tr)
        n = sum(trs) / len(trs)
        n_series[period] = n

        for i in range(period + 1, len(candles)):
            tr = TurtleMath.true_range(
                candles[i]["high"], candles[i]["low"], candles[i-1]["close"]
            )
            n = (19 * n + tr) / 20
            n_series[i] = n

        return n_series

    @staticmethod
    def donchian_channel(candles: List[dict], period: int,
                         end_idx: int = -1) -> Tuple[float, float]:
        """Compute Donchian Channel (highest high, lowest low) over `period` days.
        end_idx is the last candle to consider (exclusive of current for entries)."""
        if end_idx == -1:
            end_idx = len(candles) - 1
        start = max(0, end_idx - period)
        subset = candles[start:end_idx]
        if not subset:
            return (0.0, 0.0)
        high = max(c["high"] for c in subset)
        low = min(c["low"] for c in subset)
        return (high, low)

    @staticmethod
    def unit_size(equity: float, n: float, risk_pct: float = 1.0) -> float:
        """Calculate unit size in USD notional.
        Unit = (risk_pct% of Equity) / N
        For crypto spot, Dollars per Point = 1.
        Returns number of coins/tokens for 1 unit."""
        if n <= 0:
            return 0.0
        dollar_risk = equity * (risk_pct / 100.0)
        return dollar_risk / n

    @staticmethod
    def market_strength(candles: List[dict], n: float,
                        lookback: int = 60) -> float:
        """Strength score: (price_now - price_N_days_ago) / N
        Higher = stronger uptrend. Used for buy strength / sell weakness."""
        if len(candles) < lookback + 1 or n <= 0:
            return 0.0
        current = candles[-1]["close"]
        past = candles[-(lookback + 1)]["close"]
        return (current - past) / n


# ═══════════════════════════════════════════════════════════════
# POSITION & TRADE TRACKING
# ═══════════════════════════════════════════════════════════════

class Unit:
    """A single unit within a position (for pyramiding)."""
    def __init__(self, entry_price: float, size: float, stop: float,
                 timestamp: int, unit_num: int, n: float = 0.0):
        self.entry_price = entry_price
        self.size = size          # Quantity of asset
        self.stop = stop
        self.timestamp = timestamp
        self.unit_num = unit_num   # 1-4
        self.n = n                 # N (ATR) at time of entry (for persistence)


class Position:
    """A full position in a market, consisting of up to 4 units."""
    def __init__(self, pair: str, direction: str, system: int):
        self.pair = pair
        self.direction = direction  # "LONG" or "SHORT"
        self.system = system        # 1 or 2
        self.units: List[Unit] = []
        self.entry_n: float = 0.0   # N at time of initial entry
        self.opened_at: int = 0
        self.reservation_ids: List[str] = []  # Central portfolio reservation IDs

    @property
    def num_units(self) -> int:
        return len(self.units)

    @property
    def total_size(self) -> float:
        return sum(u.size for u in self.units)

    @property
    def avg_entry(self) -> float:
        if not self.units:
            return 0.0
        total_cost = sum(u.entry_price * u.size for u in self.units)
        total_sz = self.total_size
        return total_cost / total_sz if total_sz > 0 else 0.0

    @property
    def current_stop(self) -> float:
        """All units share the tightest stop (2N from most recent add)."""
        if not self.units:
            return 0.0
        return self.units[-1].stop

    def unrealized_pnl(self, current_price: float) -> float:
        if self.direction == "LONG":
            return sum(u.size * (current_price - u.entry_price) for u in self.units)
        else:
            return sum(u.size * (u.entry_price - current_price) for u in self.units)

    def add_unit(self, entry_price: float, size: float, n: float, timestamp: int):
        """Add a unit and update all stops per original rules."""
        unit_num = len(self.units) + 1
        if self.direction == "LONG":
            stop = entry_price - CONFIG["stop_n_multiplier"] * n
        else:
            stop = entry_price + CONFIG["stop_n_multiplier"] * n
        new_unit = Unit(entry_price, size, stop, timestamp, unit_num, n=n)
        self.units.append(new_unit)

        # Original rule: raise all stops to 2N from most recent unit
        for u in self.units:
            u.stop = stop

    def check_stop(self, current_price: float) -> bool:
        """Returns True if stop is hit."""
        if not self.units:
            return False
        stop = self.current_stop
        if self.direction == "LONG":
            return current_price <= stop
        else:
            return current_price >= stop


class TradeLog:
    """Records completed trades for performance analysis."""
    def __init__(self):
        self.trades: List[dict] = []

    def record(self, pair: str, direction: str, system: int,
               entry_price: float, exit_price: float, size: float,
               n_at_entry: float, pnl: float, entry_time: int,
               exit_time: int, exit_reason: str):
        self.trades.append({
            "pair": pair,
            "direction": direction,
            "system": system,
            "entry": entry_price,
            "exit": exit_price,
            "size": size,
            "n": n_at_entry,
            "pnl": pnl,
            "pnl_in_n": pnl / (n_at_entry * size) if n_at_entry * size > 0 else 0,
            "entry_time": entry_time,
            "exit_time": exit_time,
            "exit_reason": exit_reason,
        })
        if len(self.trades) > 1000:
            self.trades = self.trades[-1000:]

    @property
    def total_pnl(self) -> float:
        return sum(t["pnl"] for t in self.trades)

    @property
    def win_rate(self) -> float:
        if not self.trades:
            return 0.0
        wins = sum(1 for t in self.trades if t["pnl"] > 0)
        return wins / len(self.trades) * 100

    @property
    def avg_win(self) -> float:
        wins = [t["pnl"] for t in self.trades if t["pnl"] > 0]
        return sum(wins) / len(wins) if wins else 0.0

    @property
    def avg_loss(self) -> float:
        losses = [t["pnl"] for t in self.trades if t["pnl"] <= 0]
        return sum(losses) / len(losses) if losses else 0.0

    @property
    def profit_factor(self) -> float:
        gross_profit = sum(t["pnl"] for t in self.trades if t["pnl"] > 0)
        gross_loss = abs(sum(t["pnl"] for t in self.trades if t["pnl"] < 0))
        return gross_profit / gross_loss if gross_loss > 0 else 0.0

    @property
    def expectancy_r(self) -> float:
        """Expectancy in R-multiples (N units)."""
        if not self.trades:
            return 0.0
        return sum(t["pnl_in_n"] for t in self.trades) / len(self.trades)

    def last_breakout_result(self, pair: str) -> Optional[str]:
        """Return 'WIN' or 'LOSS' for the last breakout trade on this pair.
        Used for System 1 filter rule."""
        for t in reversed(self.trades):
            if t["pair"] == pair:
                return "WIN" if t["pnl"] > 0 else "LOSS"
        return None


# ═══════════════════════════════════════════════════════════════
# THE TURTLE ENGINE
# ═══════════════════════════════════════════════════════════════

class TurtleEngine:
    """Core trading engine implementing ALL original Turtle rules."""

    def __init__(self):
        self.equity = CONFIG["starting_equity"]
        self.starting_equity = CONFIG["starting_equity"]
        self.notional_equity = CONFIG["starting_equity"]  # For drawdown adj
        self.peak_equity = CONFIG["starting_equity"]
        self.positions: Dict[str, Position] = {}
        self.trade_log = TradeLog()
        self.data = KrakenData()
        self.market_data: Dict[str, List[dict]] = {}
        self.n_values: Dict[str, float] = {}
        self.tickers: Dict[str, dict] = {}
        self.signals: List[dict] = []
        self.all_signals: List[dict] = []  # Full history for dashboard
        self.last_scan_time = 0
        self.scan_count = 0
        self.errors: List[str] = []
        self.strength_rank: List[Tuple[str, float]] = []
        self.equity_curve: List[dict] = []  # For dashboard charts

        # Breakout tracking for System 1 filter
        self.last_breakout_outcome: Dict[str, str] = {}

        # Snapshot cache — rebuilt only after each scan, not on every 2s poll
        self._snapshot_cache = None
        self._snapshot_dirty = True

        # Central portfolio client (init before position persistence so reconcile works)
        self._portfolio_client = None
        if CONFIG["use_central_portfolio"]:
            self._portfolio_client = PortfolioClient(CONFIG["command_center_url"], "turtlesue")

        # Position persistence for crash recovery
        self._positions_file = os.path.join(os.path.dirname(os.path.abspath(__file__)), "turtle_positions.json")
        self._load_positions()
        self._load_state()
        self._reconcile_positions()

        # Fleet bus listener + publisher
        self._bus = _BusListener() if _BusListener else None
        self._event_pub = _EventPublisher(CONFIG["command_center_url"], "turtlesue") if _EventPublisher else None

    # ── Position Persistence ──
    def _load_positions(self):
        """Load positions from disk on startup."""
        if not os.path.exists(self._positions_file):
            return
        try:
            with open(self._positions_file, "r") as f:
                data = json.load(f)
            loaded = 0
            for pair, pdata in data.get("positions", {}).items():
                pos = Position(pdata.get("pair"), pdata.get("direction"), pdata.get("system"))
                pos.entry_n = pdata.get("entry_n", 0)
                pos.opened_at = pdata.get("opened_at", 0)
                pos.reservation_ids = pdata.get("reservation_ids", [])
                for udata in pdata.get("units", []):
                    pos.add_unit(udata["entry_price"], udata["size"], udata["n"], udata["timestamp"])
                self.positions[pair] = pos
                loaded += 1
            if loaded > 0:
                logging.info(f"Restored {loaded} position(s) from {self._positions_file}")
        except Exception as e:
            logging.warning(f"Failed to load positions from {self._positions_file}: {e}")

    def _save_positions(self):
        """Atomic save of positions to disk."""
        try:
            data = {"positions": {}, "saved_at": time.time()}
            for pair, pos in self.positions.items():
                data["positions"][pair] = {
                    "pair": pos.pair,
                    "direction": pos.direction,
                    "system": pos.system,
                    "entry_n": pos.entry_n,
                    "opened_at": pos.opened_at,
                    "reservation_ids": pos.reservation_ids,
                    "units": [{"entry_price": u.entry_price, "size": u.size, "n": u.n, "timestamp": u.timestamp} for u in pos.units],
                }
            tmp = self._positions_file + ".tmp"
            with open(tmp, "w") as f:
                json.dump(data, f)
            os.replace(tmp, self._positions_file)
        except Exception as e:
            logging.warning(f"Failed to save positions: {e}")

    def _save_state(self):
        """Save full engine state for crash recovery (equity, trades, signals)."""
        try:
            state = {
                "equity": self.equity,
                "starting_equity": self.starting_equity,
                "peak_equity": self.peak_equity,
                "notional_equity": self.notional_equity,
                "scan_count": self.scan_count,
                "last_scan_time": self.last_scan_time,
                "last_breakout_outcome": self.last_breakout_outcome,
                "equity_curve": self.equity_curve[-500:],
                "all_signals": self.all_signals[-200:],
                "trades": self.trade_log.trades[-1000:],
                "saved_at": time.time(),
            }
            state_file = self._positions_file.replace("_positions.json", "_state.json")
            tmp = state_file + ".tmp"
            with open(tmp, "w") as f:
                json.dump(state, f)
            os.replace(tmp, state_file)
        except Exception as e:
            logging.warning(f"Failed to save state: {e}")

    def _load_state(self):
        """Load full engine state on startup (equity, trades, signals)."""
        state_file = self._positions_file.replace("_positions.json", "_state.json")
        if not os.path.exists(state_file):
            return
        try:
            with open(state_file, "r") as f:
                data = json.load(f)
            self.equity = data.get("equity", self.starting_equity)
            self.peak_equity = data.get("peak_equity", self.equity)
            self.notional_equity = data.get("notional_equity", self.equity)
            self.scan_count = data.get("scan_count", 0)
            self.last_scan_time = data.get("last_scan_time", 0)
            self.last_breakout_outcome = data.get("last_breakout_outcome", {})
            self.equity_curve = data.get("equity_curve", [])
            self.all_signals = data.get("all_signals", [])
            self.trade_log.trades = data.get("trades", [])
            logging.info(f"State restored: equity=${self.equity:.2f}, {len(self.trade_log.trades)} trades")
        except Exception as e:
            logging.warning(f"Failed to load state: {e}")

    # ── Portfolio Reconciliation ──
    def _reconcile_positions(self):
        """On startup, verify reservations are still valid. Try to re-reserve if stale."""
        if not self._portfolio_client:
            return

        reservations = self._portfolio_client.get_reservations()
        if not reservations:
            return

        for pair, pos in list(self.positions.items()):
            stale_rids = [rid for rid in pos.reservation_ids if rid not in reservations]
            if not stale_rids:
                continue

            # Try to re-reserve
            amount = pos.total_size * pos.avg_entry
            ok, new_rid = self._portfolio_client.reserve(pair, pos.direction, amount)
            if ok:
                pos.reservation_ids = [new_rid]
                self._save_positions()
                logging.info(f"Re-reserved {pair}: {new_rid}")
            else:
                # Close position - no capital; use current price if available
                logging.warning(f"Stale reservation for {pair}, re-reserve failed: {new_rid} - closing")
                ticker = self.data.fetch_ticker(pair)
                exit_price = ticker["last"] if ticker else pos.avg_entry
                self._execute_exit(pair, {"type": "stale_reservation", "price": exit_price})

    # ── Drawdown Adjustment (Original Rule) ──
    def _adjusted_equity(self) -> float:
        """Reduce notional equity by 20% for each 10% drawdown."""
        drawdown_pct = 0.0
        if self.starting_equity > 0:
            drawdown_pct = (self.starting_equity - self.equity) / self.starting_equity * 100

        reductions = int(drawdown_pct / CONFIG["drawdown_threshold_pct"])
        if reductions <= 0:
            return self.equity

        reduction_factor = (1 - CONFIG["drawdown_reduce_pct"] / 100) ** reductions
        return self.equity * reduction_factor

    # ── Risk Limit Checks (Original Rules) ──
    def _count_units_for_market(self, pair: str) -> int:
        pos = self.positions.get(pair)
        return pos.num_units if pos else 0

    def _count_units_correlated(self, group: str, direction: str,
                                correlation_type: str) -> int:
        """Count units in correlated markets for a given direction."""
        count = 0
        related_groups = set()
        related_groups.add(group)

        corr_pairs = CORRELATION_MAP.get(correlation_type, [])
        for g1, g2 in corr_pairs:
            if g1 == group:
                related_groups.add(g2)
            elif g2 == group:
                related_groups.add(g1)

        for pair, pos in self.positions.items():
            if pos.direction != direction:
                continue
            mkt = next((m for m in MARKETS if m[0] == pair), None)
            if mkt and mkt[2] in related_groups:
                count += pos.num_units
        return count

    def _count_units_direction(self, direction: str) -> int:
        return sum(p.num_units for p in self.positions.values()
                   if p.direction == direction)

    def _can_add_unit(self, pair: str, direction: str, group: str) -> bool:
        """Check ALL risk limit levels before adding a unit."""
        if self._count_units_for_market(pair) >= CONFIG["max_units_single_market"]:
            return False
        closely = self._count_units_correlated(group, direction, "closely")
        if closely >= CONFIG["max_units_closely_correlated"]:
            return False
        loosely = self._count_units_correlated(group, direction, "loosely")
        if loosely >= CONFIG["max_units_loosely_correlated"]:
            return False
        if self._count_units_direction(direction) >= CONFIG["max_units_single_direction"]:
            return False
        return True

    # ── Signal Detection ──
    def _check_system1_entry(self, pair: str, candles: List[dict],
                             n: float, current_price: float,
                             group: str) -> Optional[dict]:
        """System 1: 20-day breakout with winner filter."""
        if len(candles) < CONFIG["s1_entry_days"] + 1:
            return None

        hi, lo = TurtleMath.donchian_channel(
            candles, CONFIG["s1_entry_days"], len(candles))

        signal = None
        if current_price > hi:
            signal = {"direction": "LONG", "breakout_price": hi}
        elif current_price < lo:
            signal = {"direction": "SHORT", "breakout_price": lo}

        if not signal:
            return None

        # ── System 1 Filter: Skip if last breakout was a winner ──
        last_result = self.trade_log.last_breakout_result(pair)
        if last_result == "WIN":
            if len(candles) >= CONFIG["s1_failsafe_days"] + 1:
                hi55, lo55 = TurtleMath.donchian_channel(
                    candles, CONFIG["s1_failsafe_days"], len(candles))
                if signal["direction"] == "LONG" and current_price > hi55:
                    return {
                        "pair": pair, "system": 1, "type": "FAILSAFE",
                        "direction": "LONG", "price": current_price,
                        "breakout": hi55, "n": n, "group": group,
                    }
                elif signal["direction"] == "SHORT" and current_price < lo55:
                    return {
                        "pair": pair, "system": 1, "type": "FAILSAFE",
                        "direction": "SHORT", "price": current_price,
                        "breakout": lo55, "n": n, "group": group,
                    }
            return None

        return {
            "pair": pair, "system": 1, "type": "BREAKOUT",
            "direction": signal["direction"], "price": current_price,
            "breakout": signal["breakout_price"], "n": n, "group": group,
        }

    def _check_system2_entry(self, pair: str, candles: List[dict],
                             n: float, current_price: float,
                             group: str) -> Optional[dict]:
        """System 2: 55-day breakout, take ALL signals."""
        if len(candles) < CONFIG["s2_entry_days"] + 1:
            return None

        hi, lo = TurtleMath.donchian_channel(
            candles, CONFIG["s2_entry_days"], len(candles))

        if current_price > hi:
            return {
                "pair": pair, "system": 2, "type": "BREAKOUT",
                "direction": "LONG", "price": current_price,
                "breakout": hi, "n": n, "group": group,
            }
        elif current_price < lo:
            return {
                "pair": pair, "system": 2, "type": "BREAKOUT",
                "direction": "SHORT", "price": current_price,
                "breakout": lo, "n": n, "group": group,
            }
        return None

    def _check_pyramid(self, pair: str, pos: Position, n: float,
                       current_price: float, group: str) -> Optional[dict]:
        """Check if we should add a unit (half-N from last entry)."""
        if pos.num_units >= CONFIG["max_units_per_market"]:
            return None

        last_entry = pos.units[-1].entry_price
        interval = CONFIG["add_interval_n"] * n

        if pos.direction == "LONG":
            target = last_entry + interval
            if current_price >= target:
                return {
                    "pair": pair, "system": pos.system, "type": "PYRAMID",
                    "direction": "LONG", "price": current_price,
                    "unit_num": pos.num_units + 1, "n": n, "group": group,
                }
        else:
            target = last_entry - interval
            if current_price <= target:
                return {
                    "pair": pair, "system": pos.system, "type": "PYRAMID",
                    "direction": "SHORT", "price": current_price,
                    "unit_num": pos.num_units + 1, "n": n, "group": group,
                }
        return None

    def _check_exit(self, pair: str, pos: Position,
                    candles: List[dict], current_price: float) -> Optional[dict]:
        """Check exit conditions: Donchian contrary breakout or stop hit."""
        # ── Stop Loss Check ──
        if pos.check_stop(current_price):
            return {
                "pair": pair, "type": "STOP_LOSS", "direction": pos.direction,
                "price": current_price, "stop": pos.current_stop,
            }

        # ── Donchian Exit ──
        exit_days = (CONFIG["s1_exit_days"] if pos.system == 1
                     else CONFIG["s2_exit_days"])
        if len(candles) < exit_days + 1:
            return None

        hi, lo = TurtleMath.donchian_channel(
            candles, exit_days, len(candles))

        if pos.direction == "LONG" and current_price <= lo:
            return {
                "pair": pair, "type": "EXIT", "direction": "LONG",
                "price": current_price, "channel": lo,
                "exit_days": exit_days,
            }
        elif pos.direction == "SHORT" and current_price >= hi:
            return {
                "pair": pair, "type": "EXIT", "direction": "SHORT",
                "price": current_price, "channel": hi,
                "exit_days": exit_days,
            }
        return None

    # ── Order Execution ──
    def _execute_entry(self, signal: dict):
        """Execute a new position entry."""
        pair = signal["pair"]
        direction = signal["direction"]
        n = signal["n"]
        price = signal["price"]
        group = signal["group"]
        system = signal["system"]

        if not self._can_add_unit(pair, direction, group):
            return

        # Bus intelligence — fleet context for breakout entries
        _bus_mult = 1.0
        if self._bus:
            try:
                if self._bus.emergency_active(max_age=300):
                    self.errors.append(f"BUS SKIP {pair}: emergency active")
                    return
                # ΦTEX CRITICAL + aligned direction = this breakout is real
                if self._bus.phitex_critical(pair, max_age=120):
                    _pt = self._bus.phitex_status(pair)
                    _pt_dir = (_pt.get("fleet_direction", "") or "").upper() if _pt else ""
                    if _pt_dir == direction.upper():
                        _bus_mult *= 1.3
                # AEGIS DEPLOY = aggressive breakouts
                _a = self._bus.aegis_regime()
                if _a == "DEPLOY":
                    _bus_mult *= 1.2
                elif _a == "DEFENSIVE":
                    _bus_mult *= 0.7
                # Whale EXTREME on this pair
                _wt = self._bus.whale_tier(pair, max_age=300)
                if _wt == "EXTREME":
                    _bus_mult *= 1.3
                # NEWTON: Force alignment
                _newton = self._bus.newton_force(pair, max_age=120)
                if _newton:
                    if (_newton["direction"] == "BULL" and direction.upper() == "LONG") or \
                       (_newton["direction"] == "BEAR" and direction.upper() == "SHORT"):
                        _bus_mult *= 1 + min(0.3, _newton["inertia"] * 0.4)
                    elif _newton["direction"] != "NEUTRAL":
                        _bus_mult *= 0.7
                # EUCLID: Support/resistance awareness
                _euclid = self._bus.euclid_levels(pair, max_age=120)
                for _le in _euclid:
                    _ld = _le.get("data", {})
                    if _ld.get("type") == "RESISTANCE_APPROACHING" and direction.upper() == "LONG":
                        _bus_mult *= 0.7
                        break
                    elif _ld.get("type") == "SUPPORT_APPROACHING" and direction.upper() == "SHORT":
                        _bus_mult *= 0.7
                        break
                _bus_mult = max(0.3, min(2.0, _bus_mult))
            except Exception:
                _bus_mult = 1.0

        adj_equity = self._adjusted_equity()
        unit_coins = TurtleMath.unit_size(adj_equity, n, CONFIG["risk_per_unit_pct"])
        unit_coins *= _bus_mult
        cost = unit_coins * price

        # Minimum trade size check - reject trades too small to be viable after fees
        if cost < 50:
            self.errors.append(f"Trade too small: ${cost:.2f} < $50 minimum")
            return

        if cost > self.equity * 0.95:
            unit_coins = (self.equity * 0.25) / price
            if unit_coins <= 0:
                return

        # Central portfolio: reserve capital before opening
        reservation_id = None
        if self._portfolio_client:
            stop_pct = (CONFIG["stop_n_multiplier"] * n / price * 100) if price > 0 else 2.0
            ok, result = self._portfolio_client.reserve(pair, direction, cost, stop_loss_pct=stop_pct)
            if not ok:
                self.errors.append(f"Portfolio denied {pair}: {result}")
                return
            reservation_id = result

        pos = Position(pair, direction, system)
        pos.entry_n = n
        pos.opened_at = int(time.time())
        if reservation_id:
            pos.reservation_ids.append(reservation_id)
        pos.add_unit(price, unit_coins, n, int(time.time()))
        self.positions[pair] = pos
        self._save_positions()

        if self._event_pub:
            try:
                self._event_pub.emit("TRADE_OPEN", {
                    "pair": pair, "direction": direction.upper(),
                    "entry": round(price, 4), "size": round(cost, 2),
                    "sl": round(price - n * CONFIG["stop_n_multiplier"], 4) if direction == "long" else round(price + n * CONFIG["stop_n_multiplier"], 4),
                    "system": system,
                })
            except Exception:
                pass

    def _execute_pyramid(self, signal: dict):
        """Add a unit to existing position."""
        pair = signal["pair"]
        group = signal["group"]
        pos = self.positions.get(pair)
        if not pos:
            return

        if not self._can_add_unit(pair, pos.direction, group):
            return

        n = signal["n"]
        price = signal["price"]
        adj_equity = self._adjusted_equity()
        unit_coins = TurtleMath.unit_size(adj_equity, n, CONFIG["risk_per_unit_pct"])
        cost = unit_coins * price

        if cost > self.equity * 0.25:
            unit_coins = (self.equity * 0.10) / price
            if unit_coins <= 0:
                return

        # Central portfolio: reserve capital for pyramid unit
        if self._portfolio_client:
            ok, result = self._portfolio_client.reserve(pair, pos.direction, cost)
            if not ok:
                self.errors.append(f"Portfolio denied pyramid {pair}: {result}")
                return
            pos.reservation_ids.append(result)

        pos.add_unit(price, unit_coins, n, int(time.time()))
        self._save_positions()

    def _execute_exit(self, pair: str, exit_info: dict):
        """Close entire position and log the trade."""
        pos = self.positions.get(pair)
        if not pos:
            return

        exit_price = exit_info["price"]
        pnl = pos.unrealized_pnl(exit_price)
        self.equity += pnl

        if self.equity > self.peak_equity:
            self.peak_equity = self.equity

        # Central portfolio: release all reservations for this position
        if self._portfolio_client and pos.reservation_ids:
            # Report outcome to signal aggregator for learning
            try:
                import urllib.request as urlreq
                url = f"{CONFIG['command_center_url']}/api/signals/outcome"
                fees = pos.total_size * 0.0026 * 2  # Approx round-trip fees
                data = json.dumps({
                    "bot_id": "turtlesue",
                    "pair": pair,
                    "direction": pos.direction,
                    "won": pnl > 0,
                    "pnl": float(pnl),
                    "fees": float(fees)
                }).encode("utf-8")
                req = urlreq.Request(url, data=data, headers={"Content-Type": "application/json"})
                urlreq.urlopen(req, timeout=3)
            except Exception:
                pass
            
            # Split PnL across first reservation, release rest with 0
            for i, rid in enumerate(pos.reservation_ids):
                rid_pnl = pnl if i == 0 else 0.0
                self._portfolio_client.release(rid, pnl=rid_pnl)

        self.trade_log.record(
            pair=pair,
            direction=pos.direction,
            system=pos.system,
            entry_price=pos.avg_entry,
            exit_price=exit_price,
            size=pos.total_size,
            n_at_entry=pos.entry_n,
            pnl=pnl,
            entry_time=pos.opened_at,
            exit_time=int(time.time()),
            exit_reason=exit_info["type"],
        )

        if _expectancy:
            try:
                _expectancy.record_trade(
                    bot_id='turtlesue',
                    pair=pair,
                    direction=pos.direction,
                    entry_price=pos.avg_entry,
                    exit_price=exit_price,
                    size_usd=pos.total_size * pos.avg_entry,
                    duration=int(time.time()) - pos.opened_at,
                )
            except Exception:
                pass

        if self._event_pub:
            try:
                _risk_usd = pos.entry_n * CONFIG["stop_n_multiplier"] * pos.total_size if pos.entry_n > 0 else 0
                _r = round(pnl / _risk_usd, 2) if _risk_usd > 0 else 0
                self._event_pub.emit("TRADE_CLOSE", {
                    "pair": pair, "direction": pos.direction.upper(),
                    "exit_price": round(exit_price, 4),
                    "pnl": round(pnl, 2), "exit_reason": exit_info["type"],
                    "r": _r,
                    "duration_s": int(time.time()) - pos.opened_at,
                    "system": pos.system, "units": pos.num_units,
                })
            except Exception:
                pass

        del self.positions[pair]
        self._save_positions()
        self._save_state()

    # ── JSON Snapshot for Dashboard ──
    def snapshot(self) -> dict:
        """Return full engine state as JSON-serializable dict.
        Cached between scans — only rebuilt when _snapshot_dirty is True."""
        if self._snapshot_cache is not None and not self._snapshot_dirty:
            # Update only the time-sensitive fields without full rebuild
            self._snapshot_cache["last_scan_time"] = self.last_scan_time
            return self._snapshot_cache

        positions = {}
        for pair, pos in self.positions.items():
            name = next((m[1] for m in MARKETS if m[0] == pair), pair)
            ticker = self.tickers.get(pair, {})
            current = ticker.get("last", pos.avg_entry)
            upnl = pos.unrealized_pnl(current)
            positions[pair] = {
                "name": name,
                "direction": pos.direction,
                "system": pos.system,
                "num_units": pos.num_units,
                "avg_entry": round(pos.avg_entry, 2),
                "current_stop": round(pos.current_stop, 2),
                "total_size": pos.total_size,
                "unrealized_pnl": round(upnl, 2),
                "entry_n": round(pos.entry_n, 4),
                "opened_at": pos.opened_at,
                "units": [
                    {
                        "unit_num": u.unit_num,
                        "entry_price": round(u.entry_price, 2),
                        "size": u.size,
                        "stop": round(u.stop, 2),
                    }
                    for u in pos.units
                ],
            }

        markets = []
        for pair, mname, group in MARKETS:
            candles = self.market_data.get(pair)
            n = self.n_values.get(pair)
            ticker = self.tickers.get(pair)
            if not candles or not n or not ticker:
                markets.append({
                    "pair": pair, "name": mname, "group": group,
                    "price": 0, "n": 0, "hi20": 0, "lo20": 0,
                    "hi55": 0, "lo55": 0, "strength": 0,
                    "unit_usd": 0, "in_position": pair in self.positions,
                    "volume_24h": 0,
                })
                continue

            price = ticker["last"]
            hi20, lo20 = TurtleMath.donchian_channel(
                candles, CONFIG["s1_entry_days"], len(candles))
            hi55, lo55 = TurtleMath.donchian_channel(
                candles, CONFIG["s2_entry_days"], len(candles))
            strength = TurtleMath.market_strength(candles, n, 60)
            adj_eq = self._adjusted_equity()
            unit_coins = TurtleMath.unit_size(adj_eq, n, CONFIG["risk_per_unit_pct"])
            unit_usd = unit_coins * price

            # Build mini sparkline data (last 20 closes)
            spark = [c["close"] for c in candles[-20:]] if len(candles) >= 20 else []

            markets.append({
                "pair": pair, "name": mname, "group": group,
                "price": round(price, 2),
                "n": round(n, 4),
                "hi20": round(hi20, 2),
                "lo20": round(lo20, 2),
                "hi55": round(hi55, 2),
                "lo55": round(lo55, 2),
                "strength": round(strength, 2),
                "unit_usd": round(unit_usd, 2),
                "in_position": pair in self.positions,
                "volume_24h": round(ticker.get("volume", 0), 2),
                "sparkline": spark,
            })

        # Donchian channel data for chart (last 60 candles per market)
        channel_data = {}
        for pair, mname, group in MARKETS:
            candles = self.market_data.get(pair)
            if not candles or len(candles) < 21:
                continue
            cd = []
            for i in range(max(20, len(candles) - 60), len(candles)):
                hi20, lo20 = TurtleMath.donchian_channel(candles, 20, i)
                hi55, lo55 = (0, 0)
                if i >= 55:
                    hi55, lo55 = TurtleMath.donchian_channel(candles, 55, i)
                cd.append({
                    "time": candles[i]["time"],
                    "close": candles[i]["close"],
                    "high": candles[i]["high"],
                    "low": candles[i]["low"],
                    "hi20": hi20, "lo20": lo20,
                    "hi55": hi55, "lo55": lo55,
                })
            channel_data[pair] = cd

        dd_from_peak = ((self.peak_equity - self.equity) / self.peak_equity * 100
                        if self.peak_equity > 0 else 0)

        result = {
            "equity": round(self.equity, 2),
            "starting_equity": self.starting_equity,
            "peak_equity": round(self.peak_equity, 2),
            "adjusted_equity": round(self._adjusted_equity(), 2),
            "pnl": round(self.equity - self.starting_equity, 2),
            "pnl_pct": round((self.equity - self.starting_equity) / self.starting_equity * 100, 2),
            "drawdown_pct": round(dd_from_peak, 2),
            "scan_count": self.scan_count,
            "last_scan_time": self.last_scan_time,
            "system_mode": CONFIG["system_mode"],
            "positions": positions,
            "markets": markets,
            "channel_data": channel_data,
            "signals": self.all_signals[-50:],
            "trades": self.trade_log.trades[-50:],
            "trade_stats": {
                "total": len(self.trade_log.trades),
                "win_rate": round(self.trade_log.win_rate, 1),
                "profit_factor": round(self.trade_log.profit_factor, 2),
                "expectancy_r": round(self.trade_log.expectancy_r, 2),
                "avg_win": round(self.trade_log.avg_win, 2),
                "avg_loss": round(self.trade_log.avg_loss, 2),
                "total_pnl": round(self.trade_log.total_pnl, 2),
            },
            "strength_rank": [
                {"pair": p, "name": next((m[1] for m in MARKETS if m[0] == p), p),
                 "strength": round(s, 2)}
                for p, s in self.strength_rank
            ],
            "risk_limits": {
                "long_units": self._count_units_direction("LONG"),
                "short_units": self._count_units_direction("SHORT"),
                "max_direction": CONFIG["max_units_single_direction"],
            },
            "equity_curve": self.equity_curve[-200:],
            "config": {
                "s1_entry": CONFIG["s1_entry_days"],
                "s2_entry": CONFIG["s2_entry_days"],
                "s1_exit": CONFIG["s1_exit_days"],
                "s2_exit": CONFIG["s2_exit_days"],
                "risk_pct": CONFIG["risk_per_unit_pct"],
                "stop_n": CONFIG["stop_n_multiplier"],
                "refresh": CONFIG["refresh_seconds"],
            },
            "errors": self.errors[-10:],
        }
        if _expectancy:
            result["expectancy"] = _expectancy.bot_snapshot_fields('turtlesue')
        self._snapshot_cache = result
        self._snapshot_dirty = False
        return result

    # ── Main Scan Loop ──
    def scan(self):
        """Full market scan: fetch data, check signals, execute trades."""
        self.signals = []
        self.errors = []
        self.scan_count += 1

        try:
            self.market_data = self.data.get_all_ohlc(
                MARKETS, CONFIG["ohlc_interval"], CONFIG["lookback_days"])
        except Exception as e:
            self.errors.append(f"Data fetch error: {e}")
            return

        # Batch fetch all tickers in one API call
        active_pairs = [m[0] for m in MARKETS if m[0] in self.market_data]
        batch_tickers = self.data.fetch_all_tickers(active_pairs)
        self.tickers.update(batch_tickers)

        strength_scores = {}
        for pair, name, group in MARKETS:
            candles = self.market_data.get(pair)
            if not candles or len(candles) < CONFIG["s2_entry_days"] + 2:
                continue

            n = TurtleMath.compute_n(candles, CONFIG["n_period"])
            if n is None or n <= 0:
                continue
            self.n_values[pair] = n

            ticker = self.tickers.get(pair)
            if not ticker:
                continue
            current_price = ticker["last"]

            strength = TurtleMath.market_strength(candles, n, 60)
            strength_scores[pair] = strength

            # ── Check Exits First (always) ──
            if pair in self.positions:
                pos = self.positions[pair]
                exit_info = self._check_exit(pair, pos, candles, current_price)
                if exit_info:
                    sig = {"action": "EXIT", **exit_info, "name": name,
                           "time": int(time.time())}
                    self.signals.append(sig)
                    self.all_signals.append(sig)
                    self._execute_exit(pair, exit_info)
                    continue

                pyramid = self._check_pyramid(pair, pos, n, current_price, group)
                if pyramid:
                    sig = {"action": "PYRAMID", **pyramid, "name": name,
                           "time": int(time.time())}
                    self.signals.append(sig)
                    self.all_signals.append(sig)
                    self._execute_pyramid(pyramid)
                continue

            # ── Check Entries ──
            mode = CONFIG["system_mode"]

            if mode in ("S1", "BOTH"):
                s1 = self._check_system1_entry(
                    pair, candles, n, current_price, group)
                if s1:
                    sig = {"action": "ENTRY", **s1, "name": name,
                           "time": int(time.time())}
                    self.signals.append(sig)
                    self.all_signals.append(sig)
                    self._execute_entry(s1)
                    continue

            if mode in ("S2", "BOTH"):
                s2 = self._check_system2_entry(
                    pair, candles, n, current_price, group)
                if s2:
                    sig = {"action": "ENTRY", **s2, "name": name,
                           "time": int(time.time())}
                    self.signals.append(sig)
                    self.all_signals.append(sig)
                    self._execute_entry(s2)

        self.strength_rank = sorted(
            strength_scores.items(), key=lambda x: x[1], reverse=True)

        # Record equity curve point
        self.equity_curve.append({
            "time": int(time.time()),
            "equity": round(self.equity, 2),
            "positions": len(self.positions),
        })
        # Cap unbounded lists to prevent memory growth
        if len(self.equity_curve) > 500:
            self.equity_curve = self.equity_curve[-500:]
        if len(self.all_signals) > 200:
            self.all_signals = self.all_signals[-200:]

        self.last_scan_time = int(time.time())
        self._snapshot_dirty = True
        self._save_state()


# ═══════════════════════════════════════════════════════════════
# TERMINAL DISPLAY ENGINE
# ═══════════════════════════════════════════════════════════════

class Display:
    """ANSI terminal display for Pydroid3."""

    W = CONFIG["terminal_width"]

    @staticmethod
    def clear():
        print(CLEAR, end="")

    @staticmethod
    def hline(char="=", color=DIM):
        print(f"{color}{char * Display.W}{RESET}")

    @staticmethod
    def dline(char="-", color=DIM):
        print(f"{color}{char * Display.W}{RESET}")

    @staticmethod
    def banner():
        print(f"""
{BCYAN}{BOLD}+{'-' * (Display.W - 2)}+{RESET}
{BCYAN}|{RESET}{BG_DGRAY}{BWHITE}{BOLD}{"TURTLEBOT ULTRA":^{Display.W - 2}}{RESET}{BCYAN}|{RESET}
{BCYAN}|{RESET}{CYAN}{"The Original 1983 Rules x Crypto":^{Display.W - 2}}{RESET}{BCYAN}|{RESET}
{BCYAN}|{RESET}{DIM}{"Richard Dennis & William Eckhardt":^{Display.W - 2}}{RESET}{BCYAN}|{RESET}
{BCYAN}+{'-' * (Display.W - 2)}+{RESET}""")

    @staticmethod
    def account_panel(engine: TurtleEngine):
        eq = engine.equity
        start = engine.starting_equity
        pnl = eq - start
        pnl_pct = (pnl / start * 100) if start > 0 else 0
        adj_eq = engine._adjusted_equity()
        dd_from_peak = ((engine.peak_equity - eq) / engine.peak_equity * 100
                        if engine.peak_equity > 0 else 0)
        color = BGREEN if pnl >= 0 else BRED
        dd_color = BRED if dd_from_peak > 5 else YELLOW if dd_from_peak > 0 else GREEN

        print(f"\n{BOLD}{BWHITE} ACCOUNT{RESET}")
        Display.dline()
        print(f"  {'Equity:':<20}{BOLD}{BWHITE}${eq:>12,.2f}{RESET}"
              f"    {'P&L:':<6}{color}${pnl:>+10,.2f} ({pnl_pct:+.1f}%){RESET}")
        print(f"  {'Notional (adj):':<20}{CYAN}${adj_eq:>12,.2f}{RESET}"
              f"    {'DD:':<6}{dd_color}{dd_from_peak:>10.1f}%{RESET}")
        print(f"  {'Peak Equity:':<20}{DIM}${engine.peak_equity:>12,.2f}{RESET}"
              f"    {'Scan:':<6}{DIM}#{engine.scan_count:>9}{RESET}")

    @staticmethod
    def positions_panel(engine: TurtleEngine):
        print(f"\n{BOLD}{BWHITE} OPEN POSITIONS{RESET}", end="")
        total_units = sum(p.num_units for p in engine.positions.values())
        dir_long = engine._count_units_direction("LONG")
        dir_short = engine._count_units_direction("SHORT")
        print(f"  {DIM}[{total_units} units | L:{dir_long} S:{dir_short} | "
              f"max {CONFIG['max_units_single_direction']}/dir]{RESET}")
        Display.dline()

        if not engine.positions:
            print(f"  {DIM}No open positions -- waiting for breakouts...{RESET}")
            return

        print(f"  {DIM}{'Market':<10}{'Dir':>5}{'S#':>3}{'Units':>6}"
              f"{'Entry':>10}{'Last':>10}{'Stop':>10}{'uPnL':>10}{'N':>8}{RESET}")

        for pair, pos in engine.positions.items():
            name = next((m[1] for m in MARKETS if m[0] == pair), pair)
            short_name = name.replace("/USD", "")
            ticker = engine.tickers.get(pair, {})
            current = ticker.get("last", pos.avg_entry)
            upnl = pos.unrealized_pnl(current)
            pnl_c = BGREEN if upnl >= 0 else BRED
            dir_c = GREEN if pos.direction == "LONG" else RED
            n = engine.n_values.get(pair, 0)

            print(f"  {BWHITE}{short_name:<10}{RESET}"
                  f"{dir_c}{pos.direction:>5}{RESET}"
                  f"{CYAN}{'S'+str(pos.system):>3}{RESET}"
                  f"{BYELLOW}{pos.num_units:>4}/4{RESET}"
                  f"  {pos.avg_entry:>8.2f}"
                  f"  {current:>8.2f}"
                  f"  {pos.current_stop:>8.2f}"
                  f"{pnl_c}{upnl:>+10.2f}{RESET}"
                  f"  {DIM}{n:>6.2f}{RESET}")

            for u in pos.units:
                u_pnl = (current - u.entry_price) * u.size if pos.direction == "LONG" \
                    else (u.entry_price - current) * u.size
                u_c = GREEN if u_pnl >= 0 else RED
                print(f"  {DIM}  -- U{u.unit_num}: "
                      f"entry={u.entry_price:.2f} "
                      f"qty={u.size:.6f} "
                      f"stop={u.stop:.2f} "
                      f"{u_c}pnl={u_pnl:+.2f}{RESET}")

    @staticmethod
    def market_panel(engine: TurtleEngine):
        print(f"\n{BOLD}{BWHITE} MARKET MONITOR{RESET}")
        Display.dline()
        print(f"  {DIM}{'Market':<10}{'Price':>10}{'N (ATR)':>10}"
              f"{'20d-Hi':>10}{'20d-Lo':>10}{'Str':>8}{'Unit$':>10}{RESET}")

        for pair, name, group in MARKETS:
            candles = engine.market_data.get(pair)
            n = engine.n_values.get(pair)
            ticker = engine.tickers.get(pair)
            if not candles or not n or not ticker:
                continue

            short_name = name.replace("/USD", "")
            price = ticker["last"]
            hi20, lo20 = TurtleMath.donchian_channel(
                candles, CONFIG["s1_entry_days"], len(candles))
            strength = TurtleMath.market_strength(candles, n, 60)
            adj_eq = engine._adjusted_equity()
            unit_coins = TurtleMath.unit_size(adj_eq, n, CONFIG["risk_per_unit_pct"])
            unit_usd = unit_coins * price

            p_color = RESET
            if price >= hi20 * 0.995:
                p_color = BGREEN
            elif price <= lo20 * 1.005:
                p_color = BRED
            str_c = GREEN if strength > 0 else RED

            in_pos = "*" if pair in engine.positions else " "
            pos_c = BYELLOW if pair in engine.positions else DIM

            print(f"  {pos_c}{in_pos}{RESET}"
                  f"{BWHITE}{short_name:<9}{RESET}"
                  f"{p_color}{price:>10.2f}{RESET}"
                  f"  {CYAN}{n:>8.2f}{RESET}"
                  f"  {GREEN}{hi20:>8.2f}{RESET}"
                  f"  {RED}{lo20:>8.2f}{RESET}"
                  f"  {str_c}{strength:>6.1f}{RESET}"
                  f"  {DIM}${unit_usd:>8.2f}{RESET}")

    @staticmethod
    def strength_panel(engine: TurtleEngine):
        if not engine.strength_rank:
            return
        print(f"\n{BOLD}{BWHITE} STRENGTH RANKING{RESET}"
              f"  {DIM}(Buy strongest, sell weakest){RESET}")
        Display.dline()
        rank = engine.strength_rank
        top3 = rank[:3]
        bot3 = rank[-3:]

        print(f"  {GREEN}STRONGEST:{RESET}", end="")
        for pair, s in top3:
            name = next((m[1] for m in MARKETS if m[0] == pair), pair)
            print(f"  {BGREEN}{name.replace('/USD','')}{RESET}"
                  f"({s:+.1f})", end="")
        print()
        print(f"  {RED}WEAKEST: {RESET}", end="")
        for pair, s in bot3:
            name = next((m[1] for m in MARKETS if m[0] == pair), pair)
            print(f"  {BRED}{name.replace('/USD','')}{RESET}"
                  f"({s:+.1f})", end="")
        print()

    @staticmethod
    def signals_panel(engine: TurtleEngine):
        print(f"\n{BOLD}{BWHITE} SIGNALS & ACTIONS{RESET}")
        Display.dline()
        if not engine.signals:
            print(f"  {DIM}No signals this scan{RESET}")
        else:
            for sig in engine.signals[-8:]:
                action = sig.get("action", "?")
                name = sig.get("name", sig.get("pair", "?"))
                direction = sig.get("direction", "")
                price = sig.get("price", 0)
                sig_type = sig.get("type", "")

                if action == "ENTRY":
                    icon = ">"
                    ac = BGREEN if direction == "LONG" else BRED
                    sys_str = f"S{sig.get('system', '?')}"
                    extra = f" [{sig_type}]" if sig_type == "FAILSAFE" else ""
                    print(f"  {ac}{icon} {action} {direction} {name} "
                          f"@ ${price:.2f} ({sys_str}{extra}){RESET}")
                elif action == "PYRAMID":
                    icon = "^"
                    ac = BYELLOW
                    unit = sig.get("unit_num", "?")
                    print(f"  {ac}{icon} ADD Unit #{unit} {name} "
                          f"@ ${price:.2f}{RESET}")
                elif action == "EXIT":
                    icon = "X"
                    etype = sig.get("type", "")
                    ac = BMAGENTA if etype == "EXIT" else BRED
                    print(f"  {ac}{icon} {etype} {direction} {name} "
                          f"@ ${price:.2f}{RESET}")

    @staticmethod
    def performance_panel(engine: TurtleEngine):
        tl = engine.trade_log
        print(f"\n{BOLD}{BWHITE} PERFORMANCE{RESET}")
        Display.dline()
        if not tl.trades:
            print(f"  {DIM}No completed trades yet{RESET}")
            return

        total = len(tl.trades)
        wins = sum(1 for t in tl.trades if t["pnl"] > 0)
        losses = total - wins
        pf = tl.profit_factor
        exp = tl.expectancy_r

        print(f"  {'Trades:':<16}{BWHITE}{total:>6}{RESET}"
              f"    {'Win Rate:':<12}{BWHITE}{tl.win_rate:>6.1f}%{RESET}"
              f"    {'Profit Factor:':<16}{BWHITE}{pf:>6.2f}{RESET}")
        print(f"  {'Wins:':<16}{GREEN}{wins:>6}{RESET}"
              f"    {'Avg Win:':<12}{GREEN}${tl.avg_win:>8.2f}{RESET}"
              f"    {'Expectancy(R):':<16}"
              f"{'%s%.2f%s' % (GREEN if exp > 0 else RED, exp, RESET):>6}")
        print(f"  {'Losses:':<16}{RED}{losses:>6}{RESET}"
              f"    {'Avg Loss:':<12}{RED}${tl.avg_loss:>8.2f}{RESET}"
              f"    {'Total P&L:':<16}"
              f"{'%s$%.2f%s' % (GREEN if tl.total_pnl > 0 else RED, tl.total_pnl, RESET):>6}")

        if tl.trades:
            print(f"\n  {DIM}Last Trades{'-' * (Display.W - 16)}{RESET}")
            for t in tl.trades[-5:]:
                name = next((m[1] for m in MARKETS if m[0] == t["pair"]),
                            t["pair"])
                tc = GREEN if t["pnl"] > 0 else RED
                ts = datetime.fromtimestamp(t["exit_time"]).strftime("%m/%d %H:%M")
                print(f"  {DIM}{ts}{RESET} "
                      f"{tc}{t['direction'][:1]} {name:<10}"
                      f"S{t['system']} "
                      f"${t['entry']:.2f}->${t['exit']:.2f} "
                      f"pnl={t['pnl']:+.2f} "
                      f"({t['exit_reason']}){RESET}")

    @staticmethod
    def rules_reminder():
        print(f"\n{DIM}{'-' * Display.W}")
        print(f"  TURTLE RULES ACTIVE:")
        print(f"  S1: 20d breakout entry | 10d contrary exit | skip after winner")
        print(f"  S2: 55d breakout entry | 20d contrary exit | take all signals")
        print(f"  Stops: 2N from entry | raised per unit add")
        print(f"  Units: 1% equity/N | pyramid 1/2N intervals | max 4/market")
        print(f"  Limits: 4/mkt, 6/close-corr, 10/loose-corr, 12/direction")
        print(f"  DD adj: -20% notional per -10% equity drawdown")
        print(f"{'-' * Display.W}{RESET}")

    @staticmethod
    def status_bar(engine: TurtleEngine):
        now = datetime.now().strftime("%H:%M:%S")
        next_scan = CONFIG["refresh_seconds"]
        mode = CONFIG["system_mode"]
        n_mkts = len(engine.market_data)
        n_pos = len(engine.positions)
        errs = len(engine.errors)
        port = CONFIG["dashboard_port"]

        err_str = f" {BRED}| {errs} errors{RESET}" if errs else ""

        print(f"\n{BG_DGRAY}{BWHITE} {now} | Mode: {mode} | "
              f"Markets: {n_mkts}/{len(MARKETS)} | "
              f"Positions: {n_pos} | "
              f"Next: {next_scan}s | "
              f"Web: :{port}"
              f"{err_str} {RESET}")

    @staticmethod
    def render_full(engine: TurtleEngine):
        Display.clear()
        Display.banner()
        Display.account_panel(engine)
        Display.positions_panel(engine)
        Display.market_panel(engine)
        Display.strength_panel(engine)
        Display.signals_panel(engine)
        Display.performance_panel(engine)
        Display.rules_reminder()
        Display.status_bar(engine)

        if engine.errors:
            print(f"\n{BRED}Errors:{RESET}")
            for e in engine.errors[-3:]:
                print(f"  {RED}* {e}{RESET}")


# ═══════════════════════════════════════════════════════════════
# WEB DASHBOARD (HTTP Server)
# ═══════════════════════════════════════════════════════════════

class DashboardServer:
    """Lightweight HTTP server serving the HTML dashboard + JSON API."""

    def __init__(self, engine: TurtleEngine, port: int = 8050):
        self.engine = engine
        self.port = port
        self._html = self._load_html()

    def _load_html(self) -> str:
        """Load dashboard.html from same directory."""
        here = os.path.dirname(os.path.abspath(__file__))
        html_path = os.path.join(here, "dashboard.html")
        try:
            with open(html_path, "r", encoding="utf-8") as f:
                return f.read()
        except FileNotFoundError:
            return "<html><body><h1>dashboard.html not found</h1></body></html>"

    def start(self):
        """Start dashboard in a daemon thread."""
        from http.server import HTTPServer, BaseHTTPRequestHandler
        engine = self.engine
        html = self._html

        class Handler(BaseHTTPRequestHandler):
            def log_message(self, format, *args):
                pass  # Suppress log spam

            def do_GET(self):
                if self.path == "/" or self.path == "/index.html":
                    self.send_response(200)
                    self.send_header("Content-Type", "text/html; charset=utf-8")
                    self.end_headers()
                    self.wfile.write(html.encode("utf-8"))
                elif self.path == "/api/snapshot":
                    self.send_response(200)
                    self.send_header("Content-Type", "application/json")
                    self.send_header("Access-Control-Allow-Origin", "*")
                    self.end_headers()
                    data = json.dumps(engine.snapshot())
                    self.wfile.write(data.encode("utf-8"))
                elif self.path == "/api/config":
                    self.send_response(200)
                    self.send_header("Content-Type", "application/json")
                    self.end_headers()
                    self.wfile.write(json.dumps(CONFIG).encode("utf-8"))
                else:
                    self.send_response(404)
                    self.end_headers()

        server = HTTPServer(("0.0.0.0", self.port), Handler)
        t = threading.Thread(target=server.serve_forever, daemon=True)
        t.start()


# ═══════════════════════════════════════════════════════════════
# CONFIGURATION MENU
# ═══════════════════════════════════════════════════════════════

def config_menu():
    """Interactive configuration before starting."""
    print(CLEAR, end="")
    print(f"""
{BCYAN}{BOLD}+{'-' * 56}+
|{'TURTLEBOT ULTRA -- CONFIGURATION':^56}|
+{'-' * 56}+{RESET}

{BWHITE}Starting Equity:{RESET}   ${CONFIG['starting_equity']:,.2f}
{BWHITE}System Mode:{RESET}       {CONFIG['system_mode']} (S1=20d, S2=55d, BOTH=50/50)
{BWHITE}Markets:{RESET}           {len(MARKETS)} crypto pairs
{BWHITE}Refresh:{RESET}           Every {CONFIG['refresh_seconds']}s
{BWHITE}Risk per Unit:{RESET}     {CONFIG['risk_per_unit_pct']}% of equity
{BWHITE}Dashboard:{RESET}         http://localhost:{CONFIG['dashboard_port']}

{YELLOW}Commands:{RESET}
  {CYAN}[1]{RESET} Change starting equity
  {CYAN}[2]{RESET} Change system mode (S1/S2/BOTH)
  {CYAN}[3]{RESET} Change refresh interval
  {CYAN}[4]{RESET} Change risk per unit %
  {CYAN}[5]{RESET} View all markets
  {CYAN}[6]{RESET} View complete Turtle rules reference
  {CYAN}[ENTER]{RESET} Start trading with current settings
""")
    choice = input(f"{BWHITE}> {RESET}").strip()

    if choice == "1":
        try:
            val = float(input(f"  Starting equity ($): "))
            CONFIG["starting_equity"] = val
            print(f"  {GREEN}Set to ${val:,.2f}{RESET}")
        except ValueError:
            print(f"  {RED}Invalid number{RESET}")
        time.sleep(1)
        return config_menu()

    elif choice == "2":
        mode = input(f"  System mode (S1/S2/BOTH): ").strip().upper()
        if mode in ("S1", "S2", "BOTH"):
            CONFIG["system_mode"] = mode
            print(f"  {GREEN}Mode set to {mode}{RESET}")
        else:
            print(f"  {RED}Invalid mode{RESET}")
        time.sleep(1)
        return config_menu()

    elif choice == "3":
        try:
            val = int(input(f"  Refresh seconds (60-3600): "))
            CONFIG["refresh_seconds"] = max(60, min(3600, val))
            print(f"  {GREEN}Set to {CONFIG['refresh_seconds']}s{RESET}")
        except ValueError:
            print(f"  {RED}Invalid number{RESET}")
        time.sleep(1)
        return config_menu()

    elif choice == "4":
        try:
            val = float(input(f"  Risk per unit % (0.5-2.0): "))
            CONFIG["risk_per_unit_pct"] = max(0.5, min(2.0, val))
            print(f"  {GREEN}Set to {CONFIG['risk_per_unit_pct']}%{RESET}")
        except ValueError:
            print(f"  {RED}Invalid number{RESET}")
        time.sleep(1)
        return config_menu()

    elif choice == "5":
        print(f"\n  {BWHITE}{'Pair':<14}{'Kraken Ticker':<16}{'Correlation'}{RESET}")
        for pair, name, grp in MARKETS:
            print(f"  {CYAN}{name:<14}{RESET}{DIM}{pair:<16}{RESET}{grp}")
        input(f"\n  {DIM}Press Enter to continue...{RESET}")
        return config_menu()

    elif choice == "6":
        print_rules_reference()
        input(f"\n  {DIM}Press Enter to continue...{RESET}")
        return config_menu()


def print_rules_reference():
    """Print complete Turtle Trading rules reference."""
    print(f"""
{BCYAN}{BOLD}== COMPLETE TURTLE TRADING RULES REFERENCE =={RESET}

{BYELLOW}1. POSITION SIZING (Volatility-Normalized Units){RESET}
   N = 20-day EMA of True Range
   True Range = max(H-L, |H-PrevClose|, |PrevClose-L|)
   N formula: N = (19 x PrevN + TR) / 20
   Unit Size = (1% of Equity) / N

{BYELLOW}2. ENTRIES (Donchian Channel Breakouts){RESET}
   System 1: Buy when price > 20-day high, sell when < 20-day low
   System 2: Buy when price > 55-day high, sell when < 55-day low
   {RED}S1 FILTER:{RESET} Skip if last breakout was a WINNER
   {GREEN}S1 FAILSAFE:{RESET} If S1 skipped, enter at 55-day breakout
   S2: Take ALL signals regardless of prior outcome

{BYELLOW}3. PYRAMIDING (Adding Units){RESET}
   Add 1 unit every 1/2 N from last entry price
   Maximum 4 units per market
   Update ALL stops to 2N from most recent unit

{BYELLOW}4. STOPS (N-Based Risk Control){RESET}
   Initial stop: 2N from entry (= 2% equity risk per unit)
   On each add: raise all stops to 2N from latest unit

{BYELLOW}5. EXITS (Contrary Breakout){RESET}
   System 1: Exit longs at 10-day low, shorts at 10-day high
   System 2: Exit longs at 20-day low, shorts at 20-day high
   Exit ENTIRE position (all units) at once

{BYELLOW}6. RISK LIMITS (Portfolio Level){RESET}
   Single market:        max  4 units
   Closely correlated:   max  6 units same direction
   Loosely correlated:   max 10 units same direction
   Single direction:     max 12 units total long or short

{BYELLOW}7. DRAWDOWN ADJUSTMENT{RESET}
   For each 10% drawdown from starting equity:
   Reduce notional account size by 20%

{BYELLOW}8. BUY STRENGTH / SELL WEAKNESS{RESET}
   Strength = (Price - Price_60d_ago) / N
""")


# ═══════════════════════════════════════════════════════════════
# MAIN LOOP
# ═══════════════════════════════════════════════════════════════

def main():
    """Main entry point."""
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s %(levelname)s %(message)s',
        handlers=[
            logging.FileHandler('turtlebot.log'),
            logging.StreamHandler(sys.stdout),
        ]
    )

    # --auto flag or non-interactive stdin skips the config menu
    if "--auto" in sys.argv or not sys.stdin.isatty():
        pass  # use defaults
    else:
        config_menu()

    try:
        from port_guard import ensure_port, write_pidfile, cleanup_pidfile
        import atexit
        _port = CONFIG["dashboard_port"]
        ensure_port(_port, "turtlesue")
        write_pidfile("turtlesue", _port)
        atexit.register(cleanup_pidfile, "turtlesue")
    except Exception as _e:
        print(f"[PORT_GUARD] Warning: {_e}")

    engine = TurtleEngine()

    # Start web dashboard
    dash = DashboardServer(engine, CONFIG["dashboard_port"])
    dash.start()

    print(f"\n{BCYAN}{BOLD} TURTLEBOT ULTRA STARTING...{RESET}")
    print(f"{DIM} Fetching initial market data for {len(MARKETS)} pairs...{RESET}")
    print(f"{DIM} This takes ~{len(MARKETS) * 2}s due to API rate limits.{RESET}")
    print(f"{BGREEN} Dashboard: http://localhost:{CONFIG['dashboard_port']}{RESET}\n")

    cycle = 0
    try:
        while True:
            cycle += 1
            try:
                engine.scan()
                Display.render_full(engine)
            except KeyboardInterrupt:
                raise
            except Exception as e:
                print(f"\n{BRED}Scan error: {e}{RESET}")

            wait = CONFIG["refresh_seconds"]
            for remaining in range(wait, 0, -1):
                mins, secs = divmod(remaining, 60)
                print(f"\r  {DIM}Next scan in {mins:02d}:{secs:02d} | "
                      f"Ctrl+C to exit | Dashboard: :{CONFIG['dashboard_port']}{RESET}",
                      end="", flush=True)
                time.sleep(1)
            print("\r" + " " * 70 + "\r", end="")

    except KeyboardInterrupt:
        print(f"\n\n{BYELLOW}{'=' * Display.W}")
        print(f" TURTLEBOT ULTRA -- SESSION SUMMARY")
        print(f"{'=' * Display.W}{RESET}\n")

        tl = engine.trade_log
        eq = engine.equity
        start = engine.starting_equity
        pnl = eq - start
        pnl_pct = (pnl / start * 100) if start > 0 else 0

        print(f"  {'Final Equity:':<20}${eq:>12,.2f}")
        print(f"  {'Total P&L:':<20}"
              f"{'%s$%+.2f (%+.1f%%)%s' % (GREEN if pnl >= 0 else RED, pnl, pnl_pct, RESET)}")
        print(f"  {'Total Trades:':<20}{len(tl.trades)}")
        if tl.trades:
            print(f"  {'Win Rate:':<20}{tl.win_rate:.1f}%")
            print(f"  {'Profit Factor:':<20}{tl.profit_factor:.2f}")
            print(f"  {'Expectancy (R):':<20}{tl.expectancy_r:+.2f}")
            print(f"  {'Avg Win:':<20}{GREEN}${tl.avg_win:+.2f}{RESET}")
            print(f"  {'Avg Loss:':<20}{RED}${tl.avg_loss:+.2f}{RESET}")

        n_open = len(engine.positions)
        if n_open > 0:
            total_upnl = sum(
                p.unrealized_pnl(engine.tickers.get(pair, {}).get("last", p.avg_entry))
                for pair, p in engine.positions.items()
            )
            print(f"\n  {BYELLOW}Open positions: {n_open} "
                  f"(unrealized: ${total_upnl:+.2f}){RESET}")

        print(f"\n{DIM}  \"The key is consistency and discipline.\"")
        print(f"  -- Richard Dennis{RESET}\n")

        engine._save_state()
        engine._save_positions()
        print(f"  {GREEN}State saved.{RESET}")


if __name__ == "__main__":
    main()
