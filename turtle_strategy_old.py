#!/usr/bin/env python3
"""
Turtle Strategy + Dynamic Rebalancing Signal Bot
Dual System (20/55 day) + ATR Position Sizing + Correlation Filter
Patched: robust initialization, safe ATR sizing, correlation filter renormalization,
fallbacks for API misses, and safe state persistence.
"""

import os
import requests
import time
import json
import statistics
import pickle
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Dict, List, Optional
from dotenv import load_dotenv

load_dotenv()

# Files
STATE_FILE = os.getenv('STATE_FILE', 'bot_state.pkl')
LOG_FILE = os.getenv('LOG_FILE', 'turtle_signals.log')

import logging

# === LOGGING CONFIGURATION ===
log_file_path = Path(__file__).parent / LOG_FILE
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler(log_file_path),
        logging.StreamHandler(sys.stdout)
    ]
)
logger = logging.getLogger(__name__)

# === COLORS (Dark Mode Friendly) ===
class Colors:
    RESET = '\033[0m'
    PURPLE = '\033[38;5;141m'
    CYAN = '\033[38;5;117m'
    GREEN = '\033[38;5;120m'
    YELLOW = '\033[38;5;228m'
    ORANGE = '\033[38;5;215m'
    RED = '\033[38;5;210m'
    GRAY = '\033[38;5;245m'
    WHITE = '\033[38;5;255m'
    BLUE = '\033[38;5;111m'
    MAGENTA = '\033[38;5;177m'

def colored(text, color):
    return f"{color}{text}{Colors.RESET}"

# === CONFIGURATION (REQUIRED) ===
ACCOUNT_SIZE = float(os.getenv('ACCOUNT_SIZE', '130')) # ← ENTER YOUR BALANCE HERE (MUST BE > 0)
CHECK_INTERVAL = int(os.getenv('CHECK_INTERVAL', '300')) # 5 minutes
MIN_COINS = int(os.getenv('MIN_COINS', '2'))
MAX_COINS = int(os.getenv('MAX_COINS', '10'))
MIN_ALLOCATION = float(os.getenv('MIN_ALLOCATION', '0.10'))
MAX_ALLOCATION = float(os.getenv('MAX_ALLOCATION', '0.50'))
REBALANCE_THRESHOLD = float(os.getenv('REBALANCE_THRESHOLD', '0.05'))

# === TURTLE SYSTEMS ===
SYSTEM_1_ENABLED = os.getenv('SYSTEM_1_ENABLED', 'True').lower() == 'true'
SYSTEM_2_ENABLED = os.getenv('SYSTEM_2_ENABLED', 'True').lower() == 'true'
SYSTEM_SPLIT = float(os.getenv('SYSTEM_SPLIT', '0.6'))

# === ATR POSITION SIZING ===
ATR_PERIOD = int(os.getenv('ATR_PERIOD', '20'))
RISK_PER_TRADE = float(os.getenv('RISK_PER_TRADE', '0.02'))

# === CORRELATION FILTER ===
MAX_CORRELATED_COINS = int(os.getenv('MAX_CORRELATED_COINS', '2'))

# Coin sectors for correlation filtering (keys expected uppercase)
COIN_SECTORS = {
    "BTC": "L1", "ETH": "L1", "SOL": "L1", "ADA": "L1", "AVAX": "L1",
    "DOT": "L1", "ATOM": "L1", "NEAR": "L1", "FTM": "L1", "ALGO": "L1",
    "TRX": "L1", "TON": "L1", "APT": "L1", "SUI": "L1",
    "UNI": "DEFI", "AAVE": "DEFI", "MKR": "DEFI", "CRV": "DEFI",
    "COMP": "DEFI", "SNX": "DEFI", "SUSHI": "DEFI",
    "LINK": "INFRA", "GRT": "INFRA", "FIL": "INFRA", "AR": "INFRA",
    "BNB": "CEX", "OKB": "CEX", "LEO": "CEX",
    "DOGE": "MEME", "SHIB": "MEME", "PEPE": "MEME",
    "XRP": "PAYMENT", "XLM": "PAYMENT", "LTC": "PAYMENT",
    "FET": "AI", "RNDR": "AI", "IMX": "GAMING", "SAND": "GAMING",
    "HYPE": "OTHER", "OP": "L2", "ARB": "L2", "MATIC": "L2"
}

# === INSTANT SIGNAL MODE (BETA) ===
INSTANT_SIGNAL_MODE = os.getenv('INSTANT_SIGNAL_MODE', 'True').lower() == 'true'

# === SCAN MODE ===
SCAN_TOP_COINS = os.getenv('SCAN_TOP_COINS', 'True').lower() == 'true'
TOP_N_COINS = int(os.getenv('TOP_N_COINS', '50'))

# System parameters
SYSTEM_1_ENTRY = int(os.getenv('SYSTEM_1_ENTRY', '20'))
SYSTEM_1_EXIT = int(os.getenv('SYSTEM_1_EXIT', '10'))
SYSTEM_2_ENTRY = int(os.getenv('SYSTEM_2_ENTRY', '55'))
SYSTEM_2_EXIT = int(os.getenv('SYSTEM_2_EXIT', '20'))
MIN_HISTORY_POINTS = int(os.getenv('MIN_HISTORY_POINTS', '10'))
MAX_HISTORY_LENGTH = max(SYSTEM_1_ENTRY, SYSTEM_2_ENTRY, ATR_PERIOD) + 10 # Buffer for safety



# Fixed portfolio (id values are CoinGecko ids)
FIXED_COINS = {
    "BTC": "bitcoin", "ETH": "ethereum", "XRP": "ripple", "SOL": "solana",
    "BNB": "binancecoin", "LINK": "chainlink", "TRX": "tron",
    "ADA": "cardano", "HYPE": "hyperliquid", "XLM": "stellar"
}

# runtime coin map SYMBOL -> coin_id
COINS: Dict[str, str] = {}

class BotState:
    """Persistent bot state with safe merging of histories"""
    def __init__(self):
        self.price_history: Dict[str, List[Dict]] = {}
        self.system_1_portfolio: Dict[str, float] = {}
        self.system_2_portfolio: Dict[str, float] = {}
        self.last_signal: Optional[str] = None
        self.iteration: int = 0

    def save(self):
        try:
            with open(STATE_FILE, 'wb') as f:
                pickle.dump(self, f)
        except (IOError, pickle.PickleError) as e:
            logger.warning(colored(f"⚠ Could not save state: {e}", Colors.YELLOW))
        except Exception as e:
            logger.error(colored(f"Unhandled error saving state: {e}", Colors.RED))

    @staticmethod
    def load():
        state = BotState()
        if Path(STATE_FILE).exists():
            try:
                with open(STATE_FILE, 'rb') as f:
                    loaded = pickle.load(f)
                    # Merge safe attributes
                    state.system_1_portfolio = getattr(loaded, 'system_1_portfolio', {}).copy()
                    state.system_2_portfolio = getattr(loaded, 'system_2_portfolio', {}).copy()
                    state.last_signal = getattr(loaded, 'last_signal', None)
                    state.iteration = getattr(loaded, 'iteration', 0)
                    saved_hist = getattr(loaded, 'price_history', {}) or {}
                    # shallow copy lists so we can append safely
                    state.price_history = {k: v[:] for k, v in saved_hist.items()}
                    logger.info(colored(f"✓ Loaded state: {len(state.price_history)} histories", Colors.CYAN))
            except (IOError, pickle.PickleError) as e:
                logger.warning(colored(f"⚠ Failed to load state (starting fresh): {e}", Colors.YELLOW))
            except Exception as e:
                logger.error(colored(f"Unhandled error loading state (starting fresh): {e}", Colors.RED))
        else:
            logger.info(colored("ℹ No state file found — starting fresh", Colors.GRAY))

        # ensure keys for current COINS will exist (caller should initialize COINS before calling load)
        for sym in COINS.keys():
            state.price_history.setdefault(sym, [])
        return state

def fetch_top_coins(limit: int = 50) -> Dict[str, str]:
    """Fetch top N coins by market cap from CoinGecko (returns SYMBOL->id). Falls back cleanly."""
    url = "https://api.coingecko.com/api/v3/coins/markets"
    try:
        r = requests.get(url, params={
            "vs_currency": "usd",
            "order": "market_cap_desc",
            "per_page": limit,
            "page": 1,
            "sparkline": False
        }, timeout=10)
        r.raise_for_status()
        out = {}
        for coin in r.json():
            # force symbol uppercase to match COIN_SECTORS keys
            out[coin['symbol'].upper()] = coin['id']
        return out
    except Exception as e:
        logger.warning(colored(f"⚠ Could not fetch top coins: {e}", Colors.YELLOW))
        # return a copy to avoid accidental mutation
        return FIXED_COINS.copy()

def initialize_coins():
    """Initialize coin list. Must be called BEFORE loading state to guarantee history keys exist."""
    global COINS
    if SCAN_TOP_COINS:
        logger.info(colored(f"🔍 Scanning top {TOP_N_COINS} coins...", Colors.CYAN))
        COINS = fetch_top_coins(TOP_N_COINS)
        if not COINS:
            COINS = FIXED_COINS.copy()
            logger.warning(colored("⚠ Falling back to fixed list", Colors.YELLOW))
        logger.info(colored(f"✓ {len(COINS)} coins loaded", Colors.GREEN))
    else:
        COINS = FIXED_COINS.copy()
        logger.info(colored(f"📋 Using fixed list of {len(COINS)} coins", Colors.CYAN))

def banner():
    mode_badge = colored(" [BETA]", Colors.YELLOW) if INSTANT_SIGNAL_MODE else ""
    print("\n" + colored("━" * 75, Colors.PURPLE))
    print(colored("🐢 TURTLE SIGNAL BOT", Colors.PURPLE) + colored(f" | Dual System + ATR{mode_badge}", Colors.CYAN))
    print(colored("━" * 75, Colors.PURPLE))
    print(colored(f"💰 Account: ", Colors.GRAY) + colored(f"${ACCOUNT_SIZE:,.2f}", Colors.WHITE))
    if SYSTEM_1_ENABLED and SYSTEM_2_ENABLED:
        print(colored(f"⚡ Systems: ", Colors.GRAY) +
              colored(f"S1 (20-day) {SYSTEM_SPLIT*100:.0f}%", Colors.GREEN) +
              colored(f" + ", Colors.GRAY) +
              colored(f"S2 (55-day) {(1-SYSTEM_SPLIT)*100:.0f}%", Colors.BLUE))
    elif SYSTEM_1_ENABLED:
        print(colored(f"⚡ System: ", Colors.GRAY) + colored(f"S1 (20-day) 100%", Colors.GREEN))
    else:
        print(colored(f"⚡ System: ", Colors.GRAY) + colored(f"S2 (55-day) 100%", Colors.BLUE))
    print(colored(f"📊 Position: ", Colors.GRAY) + colored(f"ATR-based, {RISK_PER_TRADE*100:.0f}% risk/trade", Colors.WHITE))
    print(colored(f"🎯 Portfolio: ", Colors.GRAY) + colored(f"{MIN_COINS}-{MAX_COINS} coins", Colors.WHITE))
    print(colored(f"🔗 Filter: ", Colors.GRAY) + colored(f"Max {MAX_CORRELATED_COINS} per sector", Colors.ORANGE))
    if SCAN_TOP_COINS:
        print(colored(f"🔍 Scanning: ", Colors.GRAY) + colored(f"Top {TOP_N_COINS} by market cap", Colors.GREEN))
    print(colored(f"⏰ Updates: ", Colors.GRAY) + colored(f"Every {CHECK_INTERVAL//60}min", Colors.WHITE))
    if INSTANT_SIGNAL_MODE:
        print(colored(f"⚡ IS Mode: ", Colors.GRAY) + colored("ACTIVE", Colors.GREEN))
    print(colored("━" * 75, Colors.PURPLE))

def fetch_prices_with_retry(max_retries: int = 3) -> Optional[Dict]:
    """Fetch prices with exponential backoff. Returns dict keyed by coin_id (CoinGecko)."""
    if not COINS:
        logger.warning(colored("⚠ No coins configured for price fetch.", Colors.YELLOW))
        return None
    coin_ids = ",".join(set(COINS.values()))
    url = "https://api.coingecko.com/api/v3/simple/price"
    for attempt in range(max_retries):
        try:
            r = requests.get(url, params={
                "ids": coin_ids,
                "vs_currency": "usd",
                "include_24hr_change": "true"
            }, timeout=10)
            r.raise_for_status()
            return r.json()
        except requests.exceptions.RequestException as e:
            if attempt < max_retries - 1:
                wait = 2 ** attempt
                logger.warning(colored(f"⚠ API error (retry {attempt+1}/{max_retries} in {wait}s)", Colors.YELLOW))
                time.sleep(wait)
            else:
                logger.error(colored(f"✗ API failed after retries: {e}", Colors.RED))
                return None
    return None

def update_price_history(state: BotState, symbol: str, price: float):
    """Append price and cap history length."""
    state.price_history.setdefault(symbol, [])
    state.price_history[symbol].append({'price': price, 'timestamp': time.time()})
    if len(state.price_history[symbol]) > MAX_HISTORY_LENGTH:
        state.price_history[symbol] = state.price_history[symbol][-MAX_HISTORY_LENGTH:]

def calc_atr(prices: List[Dict], period: int = ATR_PERIOD) -> Optional[float]:
    """
    Estimate ATR from close prices (since simple API doesn't provide high/low).
    We use a robust TR estimate:
      - abs(curr - prev)
      - estimated daily range as 2% * price (fallback)
    Then average the last `period` TR values.
    """
    if len(prices) < period + 1:
        return None
    true_ranges = []
    for i in range(1, len(prices)):
        cur = prices[i]['price']
        prev = prices[i - 1]['price']
        # absolute move
        abs_move = abs(cur - prev)
        # fallback estimated daily range (conservative)
        est_range = max(cur * 0.01, cur * 0.02) # at least 1-2% of price
        tr = max(abs_move, est_range)
        true_ranges.append(tr)
    if len(true_ranges) < period:
        return None
    # use simple moving average of last N TRs
    return sum(true_ranges[-period:]) / period

def get_turtle_signal(prices: List[Dict], current_price: float, entry_period: int, exit_period: int) -> Dict:
    """Calculate Turtle signal and include ATR when available."""
    n = len(prices)
    if n < MIN_HISTORY_POINTS:
        return {'signal': 'BUILDING', 'tradeable': False, 'strength': 0, 'confidence': n / MIN_HISTORY_POINTS, 'atr': None}
    atr = calc_atr(prices)
    entry_n = min(n, entry_period)
    exit_n = min(n, exit_period)
    entry_high = max([p['price'] for p in prices[-entry_n:]])
    exit_low = min([p['price'] for p in prices[-exit_n:]])
    if current_price > entry_high:
        strength = min(((current_price - entry_high) / entry_high) * 100, 10)
        return {'signal': 'STRONG_BUY', 'tradeable': True, 'strength': 8 + strength, 'entry': entry_high, 'exit': exit_low, 'confidence': min(n / entry_period, 1.0), 'atr': atr}
    elif current_price < exit_low:
        return {'signal': 'SELL', 'tradeable': False, 'strength': 0, 'entry': entry_high, 'exit': exit_low, 'confidence': min(n / exit_period, 1.0), 'atr': atr}
    else:
        dist_to_entry = ((entry_high - current_price) / current_price) * 100
        if dist_to_entry < 2:
            strength = 5 + (2 - dist_to_entry)
            sig = 'NEAR_ENTRY'
        else:
            strength = 2
            sig = 'RANGING'
        return {'signal': sig, 'tradeable': True, 'strength': strength, 'entry': entry_high, 'exit': exit_low, 'confidence': min(n / entry_period, 1.0), 'atr': atr}

def calc_atr_position_size(price: float, atr: Optional[float]) -> float:
    """
    Return a position-sizing score based on ATR.
    Practical Turtle-ish approach: use price / ATR as a volatility-normalized score.
    Higher price/atr -> larger score (less relative volatility).
    """
    if not atr or atr <= 0:
        return 1.0
    return max( (price / atr), 0.0001 )

def apply_correlation_filter(allocations: Dict[str, float], max_per_sector: int) -> Dict[str, float]:
    """
    Keep only top N per sector (by allocation value). After filtering, renormalize the remaining allocations.
    """
    # Group by sector
    by_sector: Dict[str, List[tuple]] = {}
    for sym, alloc in allocations.items():
        sector = COIN_SECTORS.get(sym.upper(), "OTHER")
        by_sector.setdefault(sector, []).append((sym, alloc))
    kept: Dict[str, float] = {}
    for sector, coins in by_sector.items():
        coins_sorted = sorted(coins, key=lambda x: x[1], reverse=True)
        for sym, alloc in coins_sorted[:max_per_sector]:
            kept[sym] = alloc
    # Renormalize to preserve relative weights
    total = sum(kept.values())
    if total <= 0:
        return {}
    return {sym: alloc / total for sym, alloc in kept.items()}

def calculate_allocation(coin_data: Dict[str, Dict], system_name: str, entry_period: int, exit_period: int) -> Dict[str, float]:
    """
    Build allocations for a single system:
    - Require tradeable signal and available ATR
    - Score = (price/atr) * adjusted_strength * confidence
    - Normalize, apply min/max, apply correlation filter, then renormalize
    """
    signals = {}
    for sym, data in coin_data.items():
        history = data.get('history', [])
        price = data.get('price', 0.0)
        sig = get_turtle_signal(history, price, entry_period, exit_period)
        # require tradeable and at least an ATR estimate to position size sensibly
        if sig['tradeable'] and sig.get('atr'):
            signals[sym] = {'signal': sig, 'price': price, 'atr': sig['atr']}
    if not signals:
        return {}
    scores = {}
    for sym, d in signals.items():
        price = d['price']
        atr = d['atr']
        signal = d['signal']
        atr_score = calc_atr_position_size(price, atr) # price/atr
        strength_w = (signal.get('strength', 0) / 10.0) # 0..1
        confidence = signal.get('confidence', 1.0)
        # composite score: ATR-driven core, modest bump from strength/confidence
        score = atr_score * (0.7 + 0.2 * strength_w + 0.1 * confidence)
        scores[sym] = max(score, 0.0)
    total_score = sum(scores.values())
    if total_score == 0:
        return {}
    # raw allocations (before min/max)
    raw_alloc = {sym: sc / total_score for sym, sc in scores.items()}
    # enforce per-coin min/max bounds
    bounded = {}
    for sym, pct in raw_alloc.items():
        bounded[sym] = max(MIN_ALLOCATION, min(MAX_ALLOCATION, pct))
    # apply correlation filter (this will renormalize)
    filtered = apply_correlation_filter(bounded, MAX_CORRELATED_COINS)
    # if too many coins remain, trim to MAX_COINS
    if len(filtered) > MAX_COINS:
        items = sorted(filtered.items(), key=lambda x: x[1], reverse=True)[:MAX_COINS]
        filtered = dict(items)
    # final renormalize
    total = sum(filtered.values())
    if total <= 0:
        return {}
    return {sym: pct / total for sym, pct in filtered.items()}

def display_dual_portfolio(s1_alloc: Dict[str, float], s2_alloc: Dict[str, float], coin_data: Dict[str, Dict]):
    all_syms = set(s1_alloc.keys()) | set(s2_alloc.keys())
    logger.info("\n" + colored("━" * 75, Colors.PURPLE))
    logger.info(colored("📊 DUAL SYSTEM PORTFOLIO", Colors.PURPLE))
    logger.info(colored("━" * 75, Colors.PURPLE))
    combined = []
    for sym in all_syms:
        s1_pct = s1_alloc.get(sym, 0.0) * SYSTEM_SPLIT
        s2_pct = s2_alloc.get(sym, 0.0) * (1 - SYSTEM_SPLIT)
        total_pct = s1_pct + s2_pct
        if total_pct > 0.0001:
            combined.append((sym, total_pct, s1_pct, s2_pct))
    combined.sort(key=lambda x: x[1], reverse=True)
    logger.info(colored(f"{'COIN':<6} {'TOTAL':<7} {'S1':<7} {'S2':<7} {'VALUE':<12} {'PRICE'}", Colors.GRAY))
    logger.info(colored("─" * 75, Colors.GRAY))
    for sym, total_pct, s1_pct, s2_pct in combined:
        value = ACCOUNT_SIZE * total_pct
        data = coin_data.get(sym, {})
        price = data.get('price', 0.0)
        price_str = colored(f"${price:>8,.2f}", Colors.GRAY) if price else colored("N/A", Colors.RED)
        sector = COIN_SECTORS.get(sym.upper(), "OTHER")
        coin_name = colored(f"{sym:<6}", Colors.WHITE)
        total_str = colored(f"{total_pct*100:5.1f}%", Colors.GREEN)
        s1_str = colored(f"{s1_pct*100:5.1f}%", Colors.CYAN) if s1_pct > 0 else colored(" - ", Colors.GRAY)
        s2_str = colored(f"{s2_pct*100:5.1f}%", Colors.BLUE) if s2_pct > 0 else colored(" - ", Colors.GRAY)
        val_str = colored(f"${value:>9.2f}", Colors.WHITE)
        logger.info(f"{coin_name} {total_str} {s1_str} {s2_str} {val_str} {price_str}")
        if total_pct > 0.12:
            logger.info(colored(f" └─ {sector}", Colors.GRAY))
    logger.info(colored("─" * 75, Colors.GRAY))
    total_allocated_pct = sum(item[1] for item in combined)
    logger.info(colored(f"{ 'TOTAL':<6} {total_allocated_pct*100:5.1f}% ${ACCOUNT_SIZE * total_allocated_pct:>9.2f}", Colors.WHITE))
    logger.info(colored("━" * 75, Colors.PURPLE))

def needs_rebalance(old: Dict[str, float], new: Dict[str, float]) -> bool:
    if not old and not new:
        return False
    if not old or not new:
        return True
    if set(old.keys()) != set(new.keys()):
        return True
    for sym in new:
        if abs(new[sym] - old.get(sym, 0.0)) > REBALANCE_THRESHOLD:
            return True
    return False

def print_rebalance_signals(old_s1: Dict, new_s1: Dict, old_s2: Dict, new_s2: Dict, prices: Dict[str, float], state: BotState):
    old_combined = {}
    new_combined = {}
    all_keys = set(old_s1.keys()) | set(old_s2.keys()) | set(new_s1.keys()) | set(new_s2.keys())
    for sym in all_keys:
        old_combined[sym] = old_s1.get(sym, 0.0) * SYSTEM_SPLIT + old_s2.get(sym, 0.0) * (1 - SYSTEM_SPLIT)
        new_combined[sym] = new_s1.get(sym, 0.0) * SYSTEM_SPLIT + new_s2.get(sym, 0.0) * (1 - SYSTEM_SPLIT)
    if INSTANT_SIGNAL_MODE:
        logger.info("\n" + colored("━" * 75, Colors.ORANGE))
        logger.info(colored("🚨 INSTANT SIGNAL", Colors.ORANGE) + colored(" | TAKE ACTION NOW", Colors.YELLOW))
        logger.info(colored("━" * 75, Colors.ORANGE))
    else:
        logger.info("\n" + colored("━" * 75, Colors.ORANGE))
        logger.info(colored("⚡ REBALANCE SIGNAL", Colors.ORANGE))
        logger.info(colored("━" * 75, Colors.ORANGE))
    trades = []
    for sym in sorted(all_keys):
        old_pct = old_combined.get(sym, 0.0)
        new_pct = new_combined.get(sym, 0.0)
        if abs(old_pct - new_pct) < 0.0001:
            continue
        old_val = ACCOUNT_SIZE * old_pct
        new_val = ACCOUNT_SIZE * new_pct
        diff = new_val - old_val
        price = prices.get(sym, 0.0)
        if price <= 0:
            # skip symbols without price (can't compute qty)
            continue
        qty = abs(diff) / price
        in_s1 = sym in new_s1
        in_s2 = sym in new_s2
        sys_tag = "[S1+S2]" if in_s1 and in_s2 else "[S1]" if in_s1 else "[S2]" if in_s2 else ""
        action = "BUY" if diff > 0 else "SELL"
        trades.append((action, sym, qty, abs(diff), old_val, new_val, price, sys_tag))
    # sells first
    sells = [t for t in trades if t[0] == "SELL"]
    buys = [t for t in trades if t[0] == "BUY"]
    if sells:
        if INSTANT_SIGNAL_MODE:
            logger.info("\n" + colored("⬇️ SELL THESE NOW:", Colors.RED))
        else:
            logger.info("\n" + colored("📉 SELL SIGNALS:", Colors.RED))
        logger.info(colored("─" * 75, Colors.GRAY))
        for _, sym, qty, diff, old_val, new_val, price, tag in sells:
            if INSTANT_SIGNAL_MODE:
                if new_val < 0.01:
                    logger.info(colored(f"\n EXIT {sym} {tag}:", Colors.RED))
                    logger.info(colored(f" → Sell {qty:.6f} {sym} at ${price:,.2f}", Colors.WHITE))
                    logger.info(colored(f" → Close ${old_val:.2f} position", Colors.GRAY))
                else:
                    logger.info(colored(f"\n REDUCE {sym} {tag}:", Colors.RED))
                    logger.info(colored(f" → Sell {qty:.6f} {sym} at ${price:,.2f}", Colors.WHITE))
                    logger.info(colored(f" → ${old_val:.2f} → ${new_val:.2f}", Colors.GRAY))
            else:
                if new_val < 0.01:
                    logger.info(colored(f" ✗ EXIT {sym} {tag}:", Colors.RED) + f" Sell {qty:.6f}")
                else:
                    logger.info(colored(f" ↓ REDUCE {sym} {tag}:", Colors.RED) + f" Sell {qty:.6f}")
        logger.info("") # replace print() with logger.info("")
    if buys:
        if INSTANT_SIGNAL_MODE:
            logger.info(colored("⬆️ BUY THESE NOW:", Colors.GREEN))
        else:
            logger.info(colored("📈 BUY SIGNALS:", Colors.GREEN))
        logger.info(colored("─" * 75, Colors.GRAY))
        for _, sym, qty, diff, old_val, new_val, price, tag in buys:
            sector = COIN_SECTORS.get(sym.upper(), "OTHER")
            if INSTANT_SIGNAL_MODE:
                if old_val < 0.01:
                    logger.info(colored(f"\n ENTER {sym} {tag}:", Colors.GREEN))
                    logger.info(colored(f" → Buy {qty:.6f} {sym} at ${price:,.2f}", Colors.WHITE))
                    logger.info(colored(f" → Open ${new_val:.2f} position [{sector}]", Colors.GRAY))
                else:
                    logger.info(colored(f"\n ADD TO {sym} {tag}:", Colors.GREEN))
                    logger.info(colored(f" → Buy {qty:.6f} {sym} at ${price:,.2f}", Colors.WHITE))
                    logger.info(colored(f" → ${old_val:.2f} → ${new_val:.2f} [{sector}]", Colors.GRAY))
            else:
                if old_val < 0.01:
                    logger.info(colored(f" ✓ ENTER {sym} {tag}:", Colors.GREEN) + f" Buy {qty:.6f} [{sector}]")
                else:
                    logger.info(colored(f" ↑ ADD {sym} {tag}:", Colors.GREEN) + f" Buy {qty:.6f}")
        logger.info("") # replace print() with logger.info("")
    logger.info(colored("━" * 75, Colors.ORANGE))
    if INSTANT_SIGNAL_MODE:
        logger.info(colored("⚡ Execute immediately on your exchange", Colors.YELLOW))
        logger.info(colored(f"⏰ {datetime.now(timezone.utc).strftime('%H:%M:%S UTC')}", Colors.GRAY))
    else:
        logger.info(colored("💡 Execute manually on your exchange", Colors.YELLOW))
    logger.info(colored("━" * 75, Colors.ORANGE) + "\n")
    # log minimal info
    log_entry = {
        'timestamp': datetime.now(timezone.utc).isoformat(),
        'system_1': {'old': old_s1, 'new': new_s1},
        'system_2': {'old': old_s2, 'new': new_s2},
        'trades': [(a, s, round(q, 6), round(d, 2), tag) for a, s, q, d, *_ , tag in trades]
    }
    try:
        with open(LOG_FILE, 'a') as f:
            f.write(json.dumps(log_entry) + '\n')
    except Exception as e:
        logger.error(f"Failed to write log entry: {e}") # Changed to logger.error for better error handling
    state.last_signal = datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M UTC')

def run_bot():
    initialize_coins() # must happen before loading state (so history keys can be prepared)
    banner()
    if ACCOUNT_SIZE <= 0.0:
        logger.critical(colored("\nFATAL ERROR: ACCOUNT_SIZE must be > 0.", Colors.RED))
        sys.exit(1)
    state = BotState.load()
    # ensure histories exist for all coins
    for sym in COINS.keys():
        state.price_history.setdefault(sym, [])
    logger.info(colored(f"\n🚀 Dual Turtle System started", Colors.CYAN))
    logger.info(colored(f"💾 State: {STATE_FILE} | Log: {LOG_FILE}", Colors.GRAY))
    logger.info(colored(f"⚡ System 1: 20-day breakout ({SYSTEM_SPLIT*100:.0f}% capital)", Colors.GREEN))
    logger.info(colored(f"⚡ System 2: 55-day breakout ({(1-SYSTEM_SPLIT)*100:.0f}% capital)", Colors.BLUE))
    logger.info(colored(f"📊 ATR position sizing + correlation filter active", Colors.ORANGE))
    logger.info(colored(f"⌨️ Press Ctrl+C to stop\n", Colors.GRAY))
    try:
        while True:
            state.iteration += 1
            if state.iteration > 1:
                logger.info(colored(f"\n💤 Next update in {CHECK_INTERVAL//60} minutes...", Colors.GRAY))
                try:
                    time.sleep(CHECK_INTERVAL)
                except KeyboardInterrupt:
                    raise
            logger.info("\n" + colored("━" * 75, Colors.BLUE))
            timestamp = datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M UTC')
            logger.info(colored(f"♻️ Update #{state.iteration}", Colors.BLUE) + colored(f" | {timestamp}", Colors.GRAY))
            logger.info(colored("━" * 75, Colors.BLUE))
            logger.info(colored("📡 Fetching live prices...", Colors.CYAN))
            price_data = fetch_prices_with_retry()
            if not price_data:
                logger.warning(colored("✗ Skipping cycle", Colors.RED))
                state.save()
                continue
            logger.info(colored("✓", Colors.GREEN))
            # build coin_data keyed by SYMBOL
            coin_data: Dict[str, Dict] = {}
            # price_data is keyed by coin_id; invert COINS dict to find symbol for each returned id
            id_to_sym = {cid: sym for sym, cid in COINS.items()}
            for coin_id, payload in price_data.items():
                sym = id_to_sym.get(coin_id)
                if not sym:
                    continue
                price = payload.get('usd')
                if price is None:
                    continue
                update_price_history(state, sym, price)
                coin_data[sym] = {'price': price, 'history': state.price_history.get(sym, [])}
            # compute allocations
            new_s1_alloc = {}
            new_s2_alloc = {}
            if SYSTEM_1_ENABLED:
                new_s1_alloc = calculate_allocation(coin_data, "System 1", SYSTEM_1_ENTRY, SYSTEM_1_EXIT)
            if SYSTEM_2_ENABLED:
                new_s2_alloc = calculate_allocation(coin_data, "System 2", SYSTEM_2_ENTRY, SYSTEM_2_EXIT)
            if not new_s1_alloc and not new_s2_alloc:
                logger.warning(colored("⚠ No tradeable signals yet - building history...", Colors.YELLOW))
                state.save()
                continue
            display_dual_portfolio(new_s1_alloc, new_s2_alloc, coin_data)
            s1_needs = needs_rebalance(state.system_1_portfolio, new_s1_alloc)
            s2_needs = needs_rebalance(state.system_2_portfolio, new_s2_alloc)
            if s1_needs or s2_needs:
                prices = {sym: data['price'] for sym, data in coin_data.items()}
                print_rebalance_signals(state.system_1_portfolio, new_s1_alloc, state.system_2_portfolio, new_s2_alloc, prices, state)
                state.system_1_portfolio = new_s1_alloc.copy()
                state.system_2_portfolio = new_s2_alloc.copy()
            else:
                logger.info("\n" + colored("✓ Both systems balanced - no signals", Colors.GREEN))
            state.save()
            logger.info(colored(f"\n✓ Update complete", Colors.CYAN))
    except KeyboardInterrupt:
        logger.info("\n\n" + colored("━" * 75, Colors.PURPLE))
        logger.info(colored("🛑 Stopping Turtle bot...", Colors.YELLOW))
        state.save()
        logger.info(colored(f"💾 State saved", Colors.GREEN))
        if state.system_1_portfolio or state.system_2_portfolio:
            logger.info(colored(f"\n📊 Final Portfolio:", Colors.PURPLE))
            if state.system_1_portfolio:
                logger.info(colored(f"\n System 1 (20-day):", Colors.GREEN))
                for sym, pct in sorted(state.system_1_portfolio.items(), key=lambda x: x[1], reverse=True):
                    val = ACCOUNT_SIZE * SYSTEM_SPLIT * pct
                    logger.info(f" {colored(sym, Colors.WHITE)}: {colored(f'{pct*100:.1f}%', Colors.CYAN)} (${val:.2f})")
            if state.system_2_portfolio:
                logger.info(colored(f"\n System 2 (55-day):", Colors.BLUE))
                for sym, pct in sorted(state.system_2_portfolio.items(), key=lambda x: x[1], reverse=True):
                    val = ACCOUNT_SIZE * (1-SYSTEM_SPLIT) * pct
                    logger.info(f" {colored(sym, Colors.WHITE)}: {colored(f'{pct*100:.1f}%', Colors.CYAN)} (${val:.2f})")
        logger.info(colored("\n━" * 75, Colors.PURPLE))
        logger.info(colored("👋 Trade by the Turtle rules!\n", Colors.CYAN))
        sys.exit(0)

if __name__ == "__main__":
    run_bot()
