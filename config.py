"""
Configuration Management for Turtle Bot
Loads settings from .env and provides validation
"""

import os
from dotenv import load_dotenv
from typing import Dict, List


class Config:
    """Central configuration for Turtle Bot"""

    def __init__(self):
        # load_dotenv is idempotent — safe to call multiple times
        load_dotenv()

        # === ACCOUNT CONFIGURATION ===
        self.ACCOUNT_SIZE = float(os.getenv('ACCOUNT_SIZE', '130'))

        # === EXCHANGE CONFIGURATION ===
        self.PRIMARY_EXCHANGE = 'kraken'  # Kraken only — not overridable

        # API Credentials
        self.KRAKEN_API_KEY = os.getenv('KRAKEN_API_KEY', '')
        self.KRAKEN_API_SECRET = os.getenv('KRAKEN_API_SECRET', '')
        # Trading Mode
        self.PAPER_TRADING = os.getenv('PAPER_TRADING', 'True').lower() == 'true'

        # === TURTLE SYSTEM PARAMETERS ===
        self.SYSTEM_1_ENABLED = os.getenv('SYSTEM_1_ENABLED', 'True').lower() == 'true'
        self.SYSTEM_2_ENABLED = os.getenv('SYSTEM_2_ENABLED', 'True').lower() == 'true'
        self.SYSTEM_SPLIT = float(os.getenv('SYSTEM_SPLIT', '0.6'))  # % capital to S1

        # Entry/Exit Periods
        self.SYSTEM_1_ENTRY = int(os.getenv('SYSTEM_1_ENTRY', '20'))
        self.SYSTEM_1_EXIT = int(os.getenv('SYSTEM_1_EXIT', '10'))
        self.SYSTEM_2_ENTRY = int(os.getenv('SYSTEM_2_ENTRY', '55'))
        self.SYSTEM_2_EXIT = int(os.getenv('SYSTEM_2_EXIT', '20'))

        # ATR and Position Sizing
        self.ATR_PERIOD = int(os.getenv('ATR_PERIOD', '20'))
        self.RISK_PER_TRADE = float(os.getenv('RISK_PER_TRADE', '0.02'))  # 2% default

        # Turtle Rules
        self.MAX_UNITS_PER_POSITION = int(os.getenv('MAX_UNITS_PER_POSITION', '4'))
        self.PYRAMID_INCREMENT = float(os.getenv('PYRAMID_INCREMENT', '0.5'))  # 0.5N
        self.STOP_DISTANCE = float(os.getenv('STOP_DISTANCE', '2.0'))  # 2N

        # === PORTFOLIO MANAGEMENT ===
        self.MIN_COINS = int(os.getenv('MIN_COINS', '2'))
        self.MAX_COINS = int(os.getenv('MAX_COINS', '10'))
        self.MIN_ALLOCATION = float(os.getenv('MIN_ALLOCATION', '0.10'))
        self.MAX_ALLOCATION = float(os.getenv('MAX_ALLOCATION', '0.50'))

        # Correlation Filter
        self.MAX_CORRELATED_COINS = int(os.getenv('MAX_CORRELATED_COINS', '2'))

        # === RISK LIMITS ===
        self.MAX_TOTAL_RISK = float(os.getenv('MAX_TOTAL_RISK', '0.20'))  # 20% max
        self.EMERGENCY_STOP_LOSS = float(os.getenv('EMERGENCY_STOP_LOSS', '0.30'))  # 30% drawdown
        self.MIN_ACCOUNT_BALANCE = float(os.getenv('MIN_ACCOUNT_BALANCE', '100.00'))
        self.RESERVE_CASH_PCT = float(os.getenv('RESERVE_CASH_PCT', '0.10'))  # Keep 10% cash

        # === DATA SOURCES ===
        self.OHLC_TIMEFRAME = os.getenv('OHLC_TIMEFRAME', '1d')  # Daily candles
        self.OHLC_LIMIT = int(os.getenv('OHLC_LIMIT', '60'))  # Fetch 60 days

        # Coin Selection
        self.SCAN_TOP_COINS = os.getenv('SCAN_TOP_COINS', 'True').lower() == 'true'
        self.TOP_N_COINS = int(os.getenv('TOP_N_COINS', '50'))
        self.BATCH_SIZE = int(os.getenv('BATCH_SIZE', '20'))  # Process coins in batches

        # === OPERATIONAL SETTINGS ===
        self.CHECK_INTERVAL = int(os.getenv('CHECK_INTERVAL', '300'))  # 5 minutes
        self.STATE_FILE = os.getenv('STATE_FILE', 'bot_state.json')
        self.LOG_FILE = os.getenv('LOG_FILE', 'turtle_signals.log')
        self.AUDIT_FILE = os.getenv('AUDIT_FILE', 'trade_audit.jsonl')

        # === WEB DASHBOARD ===
        self.DASHBOARD_PORT = int(os.getenv('DASHBOARD_PORT', '5001'))
        self.STATE_FILE_PATH = os.getenv('STATE_FILE_PATH', 'bot_state.json')
        self.AUDIT_FILE_PATH = os.getenv('AUDIT_FILE_PATH', 'trade_audit.jsonl')

        # === TRAILING STOPS ===
        self.TRAILING_STOP_ENABLED = os.getenv('TRAILING_STOP_ENABLED', 'False').lower() == 'true'
        self.TRAILING_STOP_METHOD = os.getenv('TRAILING_STOP_METHOD', 'atr')
        self.TRAILING_STOP_DISTANCE = float(os.getenv('TRAILING_STOP_DISTANCE', '2.0'))

        # === REGIME DETECTION ===
        self.REGIME_FILTER_ENABLED = os.getenv('REGIME_FILTER_ENABLED', 'False').lower() == 'true'
        self.REGIME_ADX_PERIOD = int(os.getenv('REGIME_ADX_PERIOD', '14'))
        self.REGIME_MIN_ADX = float(os.getenv('REGIME_MIN_ADX', '25.0'))

        # === PAPER TRADING SLIPPAGE ===
        # Realistic slippage for liquid crypto pairs on Kraken (0.1%)
        self.PAPER_SLIPPAGE = float(os.getenv('PAPER_SLIPPAGE', '0.001'))

        # === LOGGING FORMAT ===
        # 'json' produces structured JSON Lines for the file handler;
        # console always uses human-readable text.
        self.LOG_FORMAT = os.getenv('LOG_FORMAT', 'json')

        # === NOTIFICATIONS ===
        self.ALERT_ON_ENTRY = os.getenv('ALERT_ON_ENTRY', 'True').lower() == 'true'
        self.ALERT_ON_EXIT = os.getenv('ALERT_ON_EXIT', 'True').lower() == 'true'
        self.ALERT_ON_STOP = os.getenv('ALERT_ON_STOP', 'True').lower() == 'true'
        self.ALERT_ON_ERROR = os.getenv('ALERT_ON_ERROR', 'True').lower() == 'true'

        # Discord webhook (disabled by default — set URL to enable)
        self.ALERT_ON_DISCORD = os.getenv('ALERT_ON_DISCORD', 'False').lower() == 'true'
        self.DISCORD_WEBHOOK_URL = os.getenv('DISCORD_WEBHOOK_URL', '')

        # === COIN SECTORS (for correlation filtering) ===
        # This is a soft lookup — coins absent from this dict simply have no
        # sector assigned and are not counted against any sector limit.
        self.COIN_SECTORS = {
            "BTC": "L1", "ETH": "L1", "SOL": "L1", "ADA": "L1", "AVAX": "L1",
            "DOT": "L1", "ATOM": "L1", "NEAR": "L1", "FTM": "L1", "ALGO": "L1",
            "TRX": "L1", "TON": "L1", "APT": "L1", "SUI": "L1",
            "UNI": "DEFI", "AAVE": "DEFI", "MKR": "DEFI", "CRV": "DEFI",
            "COMP": "DEFI", "SNX": "DEFI", "SUSHI": "DEFI",
            "LINK": "INFRA", "GRT": "INFRA", "FIL": "INFRA", "AR": "INFRA",
            # BNB and OKB trade on their own exchanges, not Kraken — omitted
            "LEO": "CEX",
            "DOGE": "MEME", "SHIB": "MEME", "PEPE": "MEME",
            "XRP": "PAYMENT", "XLM": "PAYMENT", "LTC": "PAYMENT",
            "FET": "AI", "RNDR": "AI", "IMX": "GAMING", "SAND": "GAMING",
            "HYPE": "OTHER", "OP": "L2", "ARB": "L2", "MATIC": "L2"
        }

        # Fixed coin list (fallback if SCAN_TOP_COINS is False)
        self.FIXED_COINS = {
            "BTC": "bitcoin", "ETH": "ethereum", "XRP": "ripple", "SOL": "solana",
            "LINK": "chainlink", "TRX": "tron",
            "ADA": "cardano", "HYPE": "hyperliquid", "XLM": "stellar"
        }

    def get_api_credentials(self) -> Dict[str, str]:
        """
        Get Kraken API credentials

        Returns:
            Dict with 'api_key' and 'api_secret' keys
        """
        return {
            'api_key': self.KRAKEN_API_KEY,
            'api_secret': self.KRAKEN_API_SECRET
        }

    def validate(self) -> List[str]:
        """
        Validate configuration and return list of errors

        Returns:
            List of error messages (empty if valid)
        """
        errors = []

        # Account size validation
        if self.ACCOUNT_SIZE <= 0:
            errors.append(f"ACCOUNT_SIZE must be > 0, got {self.ACCOUNT_SIZE}")

        if self.ACCOUNT_SIZE < self.MIN_ACCOUNT_BALANCE:
            errors.append(f"ACCOUNT_SIZE ({self.ACCOUNT_SIZE}) below MIN_ACCOUNT_BALANCE ({self.MIN_ACCOUNT_BALANCE})")

        # System validation
        if not self.SYSTEM_1_ENABLED and not self.SYSTEM_2_ENABLED:
            errors.append("At least one system (S1 or S2) must be enabled")

        if not (0 <= self.SYSTEM_SPLIT <= 1):
            errors.append(f"SYSTEM_SPLIT must be 0-1, got {self.SYSTEM_SPLIT}")

        # Risk validation
        if not (0 < self.RISK_PER_TRADE <= 0.1):
            errors.append(f"RISK_PER_TRADE should be 0-10%, got {self.RISK_PER_TRADE * 100}%")

        if not (0 < self.MAX_TOTAL_RISK <= 1):
            errors.append(f"MAX_TOTAL_RISK must be 0-100%, got {self.MAX_TOTAL_RISK * 100}%")

        if not (0 < self.EMERGENCY_STOP_LOSS <= 1):
            errors.append(f"EMERGENCY_STOP_LOSS must be 0-100%, got {self.EMERGENCY_STOP_LOSS * 100}%")

        # Portfolio validation
        if self.MIN_COINS < 1:
            errors.append(f"MIN_COINS must be >= 1, got {self.MIN_COINS}")

        if self.MAX_COINS < self.MIN_COINS:
            errors.append(f"MAX_COINS ({self.MAX_COINS}) < MIN_COINS ({self.MIN_COINS})")

        # Turtle rules validation (warnings only — allow experimentation)
        warnings = []
        if self.MAX_UNITS_PER_POSITION != 4:
            warnings.append(f"MAX_UNITS_PER_POSITION={self.MAX_UNITS_PER_POSITION} (standard Turtle rule is 4)")
        if self.PYRAMID_INCREMENT != 0.5:
            warnings.append(f"PYRAMID_INCREMENT={self.PYRAMID_INCREMENT} (standard Turtle rule is 0.5N)")
        if self.STOP_DISTANCE != 2.0:
            warnings.append(f"STOP_DISTANCE={self.STOP_DISTANCE} (standard Turtle rule is 2.0N)")
        if warnings:
            print("\n  Non-standard Turtle parameters:")
            for w in warnings:
                print(f"   * {w}")

        # API keys validation for live trading
        if not self.PAPER_TRADING:
            if not (self.KRAKEN_API_KEY and self.KRAKEN_API_SECRET):
                errors.append("Live trading enabled but missing Kraken API credentials")

        return errors

    def print_summary(self):
        """Print configuration summary"""
        print("\n" + "=" * 75)
        print("TURTLE BOT CONFIGURATION")
        print("=" * 75)
        print(f"\n  Account: ${self.ACCOUNT_SIZE:,.2f}")
        print(f"  Mode: {'PAPER TRADING' if self.PAPER_TRADING else 'LIVE TRADING'}")
        print(f"  Exchange: KRAKEN (data + execution) | CoinGecko (coin discovery only)")
        print(f"  Quote Currency: USDT ONLY")

        print(f"\n  Systems:")
        if self.SYSTEM_1_ENABLED:
            print(f"   * System 1 (20-day): {self.SYSTEM_SPLIT * 100:.0f}% capital")
        if self.SYSTEM_2_ENABLED:
            print(f"   * System 2 (55-day): {(1 - self.SYSTEM_SPLIT) * 100:.0f}% capital")

        print(f"\n  Turtle Rules:")
        print(f"   * ATR Period: {self.ATR_PERIOD} days")
        print(f"   * Risk Per Trade: {self.RISK_PER_TRADE * 100:.1f}%")
        print(f"   * Max Units: {self.MAX_UNITS_PER_POSITION}")
        print(f"   * Pyramid Increment: {self.PYRAMID_INCREMENT}N")
        print(f"   * Stop Distance: {self.STOP_DISTANCE}N")

        print(f"\n  Risk Limits:")
        print(f"   * Max Total Risk: {self.MAX_TOTAL_RISK * 100:.0f}%")
        print(f"   * Emergency Stop: {self.EMERGENCY_STOP_LOSS * 100:.0f}% drawdown")
        print(f"   * Reserve Cash: {self.RESERVE_CASH_PCT * 100:.0f}%")

        print(f"\n  Portfolio:")
        print(f"   * Max Positions: {self.MAX_COINS}")
        print(f"   * Max Per Sector: {self.MAX_CORRELATED_COINS}")
        if self.SCAN_TOP_COINS:
            print(f"   * Scanning: Top {self.TOP_N_COINS} coins (USDT pairs, batches of {self.BATCH_SIZE})")
        else:
            print(f"   * Scanning: Fixed list (USDT pairs)")

        print(f"\n  Updates: Every {self.CHECK_INTERVAL // 60} minutes")
        print("=" * 75 + "\n")

    @classmethod
    def from_env(cls) -> 'Config':
        """
        Create a Config instance, validate it, and return it.

        Returns:
            Validated Config instance

        Raises:
            ValueError if configuration is invalid
        """
        instance = cls()
        errors = instance.validate()

        if errors:
            raise ValueError("Configuration errors:\n" + "\n".join(f"  * {e}" for e in errors))

        return instance


# Convenience function
def load_config() -> Config:
    """Load and validate configuration"""
    return Config.from_env()
