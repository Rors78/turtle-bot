"""
Configuration Management for Turtle Bot
Loads settings from .env and provides validation
"""

import os
from dotenv import load_dotenv
from typing import Dict, List

load_dotenv()


class Config:
    """Central configuration for Turtle Bot"""

    # === ACCOUNT CONFIGURATION ===
    ACCOUNT_SIZE = float(os.getenv('ACCOUNT_SIZE', '130'))

    # === EXCHANGE CONFIGURATION ===
    PRIMARY_EXCHANGE = 'kraken'  # Kraken only — not overridable

    # API Credentials
    KRAKEN_API_KEY = os.getenv('KRAKEN_API_KEY', '')
    KRAKEN_API_SECRET = os.getenv('KRAKEN_API_SECRET', '')
    # Trading Mode
    PAPER_TRADING = os.getenv('PAPER_TRADING', 'True').lower() == 'true'

    # === TURTLE SYSTEM PARAMETERS ===
    SYSTEM_1_ENABLED = os.getenv('SYSTEM_1_ENABLED', 'True').lower() == 'true'
    SYSTEM_2_ENABLED = os.getenv('SYSTEM_2_ENABLED', 'True').lower() == 'true'
    SYSTEM_SPLIT = float(os.getenv('SYSTEM_SPLIT', '0.6'))  # % capital to S1

    # Entry/Exit Periods
    SYSTEM_1_ENTRY = int(os.getenv('SYSTEM_1_ENTRY', '20'))
    SYSTEM_1_EXIT = int(os.getenv('SYSTEM_1_EXIT', '10'))
    SYSTEM_2_ENTRY = int(os.getenv('SYSTEM_2_ENTRY', '55'))
    SYSTEM_2_EXIT = int(os.getenv('SYSTEM_2_EXIT', '20'))

    # ATR and Position Sizing
    ATR_PERIOD = int(os.getenv('ATR_PERIOD', '20'))
    RISK_PER_TRADE = float(os.getenv('RISK_PER_TRADE', '0.02'))  # 2% default

    # Turtle Rules
    MAX_UNITS_PER_POSITION = int(os.getenv('MAX_UNITS_PER_POSITION', '4'))
    PYRAMID_INCREMENT = float(os.getenv('PYRAMID_INCREMENT', '0.5'))  # 0.5N
    STOP_DISTANCE = float(os.getenv('STOP_DISTANCE', '2.0'))  # 2N

    # === PORTFOLIO MANAGEMENT ===
    MIN_COINS = int(os.getenv('MIN_COINS', '2'))
    MAX_COINS = int(os.getenv('MAX_COINS', '10'))
    MIN_ALLOCATION = float(os.getenv('MIN_ALLOCATION', '0.10'))
    MAX_ALLOCATION = float(os.getenv('MAX_ALLOCATION', '0.50'))

    # Correlation Filter
    MAX_CORRELATED_COINS = int(os.getenv('MAX_CORRELATED_COINS', '2'))

    # === RISK LIMITS ===
    MAX_TOTAL_RISK = float(os.getenv('MAX_TOTAL_RISK', '0.20'))  # 20% max
    EMERGENCY_STOP_LOSS = float(os.getenv('EMERGENCY_STOP_LOSS', '0.30'))  # 30% drawdown
    MIN_ACCOUNT_BALANCE = float(os.getenv('MIN_ACCOUNT_BALANCE', '100.00'))
    RESERVE_CASH_PCT = float(os.getenv('RESERVE_CASH_PCT', '0.10'))  # Keep 10% cash

    # === DATA SOURCES ===
    OHLC_TIMEFRAME = os.getenv('OHLC_TIMEFRAME', '1d')  # Daily candles
    OHLC_LIMIT = int(os.getenv('OHLC_LIMIT', '60'))  # Fetch 60 days

    # Coin Selection
    SCAN_TOP_COINS = os.getenv('SCAN_TOP_COINS', 'True').lower() == 'true'
    TOP_N_COINS = int(os.getenv('TOP_N_COINS', '50'))
    BATCH_SIZE = int(os.getenv('BATCH_SIZE', '20'))  # Process coins in batches

    # === OPERATIONAL SETTINGS ===
    CHECK_INTERVAL = int(os.getenv('CHECK_INTERVAL', '300'))  # 5 minutes
    STATE_FILE = os.getenv('STATE_FILE', 'bot_state.json')
    LOG_FILE = os.getenv('LOG_FILE', 'turtle_signals.log')

    # === NOTIFICATIONS ===
    ALERT_ON_ENTRY = os.getenv('ALERT_ON_ENTRY', 'True').lower() == 'true'
    ALERT_ON_EXIT = os.getenv('ALERT_ON_EXIT', 'True').lower() == 'true'
    ALERT_ON_STOP = os.getenv('ALERT_ON_STOP', 'True').lower() == 'true'
    ALERT_ON_ERROR = os.getenv('ALERT_ON_ERROR', 'True').lower() == 'true'

    # === COIN SECTORS (for correlation filtering) ===
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

    # Fixed coin list (fallback if SCAN_TOP_COINS is False)
    FIXED_COINS = {
        "BTC": "bitcoin", "ETH": "ethereum", "XRP": "ripple", "SOL": "solana",
        "BNB": "binancecoin", "LINK": "chainlink", "TRX": "tron",
        "ADA": "cardano", "HYPE": "hyperliquid", "XLM": "stellar"
    }

    @classmethod
    def get_api_credentials(cls) -> Dict[str, str]:
        """
        Get Kraken API credentials

        Returns:
            Dict with 'api_key' and 'api_secret' keys
        """
        return {
            'api_key': cls.KRAKEN_API_KEY,
            'api_secret': cls.KRAKEN_API_SECRET
        }

    @classmethod
    def validate(cls) -> List[str]:
        """
        Validate configuration and return list of errors

        Returns:
            List of error messages (empty if valid)
        """
        errors = []

        # Account size validation
        if cls.ACCOUNT_SIZE <= 0:
            errors.append(f"ACCOUNT_SIZE must be > 0, got {cls.ACCOUNT_SIZE}")

        if cls.ACCOUNT_SIZE < cls.MIN_ACCOUNT_BALANCE:
            errors.append(f"ACCOUNT_SIZE ({cls.ACCOUNT_SIZE}) below MIN_ACCOUNT_BALANCE ({cls.MIN_ACCOUNT_BALANCE})")

        # System validation
        if not cls.SYSTEM_1_ENABLED and not cls.SYSTEM_2_ENABLED:
            errors.append("At least one system (S1 or S2) must be enabled")

        if not (0 <= cls.SYSTEM_SPLIT <= 1):
            errors.append(f"SYSTEM_SPLIT must be 0-1, got {cls.SYSTEM_SPLIT}")

        # Risk validation
        if not (0 < cls.RISK_PER_TRADE <= 0.1):
            errors.append(f"RISK_PER_TRADE should be 0-10%, got {cls.RISK_PER_TRADE * 100}%")

        if not (0 < cls.MAX_TOTAL_RISK <= 1):
            errors.append(f"MAX_TOTAL_RISK must be 0-100%, got {cls.MAX_TOTAL_RISK * 100}%")

        if not (0 < cls.EMERGENCY_STOP_LOSS <= 1):
            errors.append(f"EMERGENCY_STOP_LOSS must be 0-100%, got {cls.EMERGENCY_STOP_LOSS * 100}%")

        # Portfolio validation
        if cls.MIN_COINS < 1:
            errors.append(f"MIN_COINS must be >= 1, got {cls.MIN_COINS}")

        if cls.MAX_COINS < cls.MIN_COINS:
            errors.append(f"MAX_COINS ({cls.MAX_COINS}) < MIN_COINS ({cls.MIN_COINS})")

        # Turtle rules validation (warnings only — allow experimentation)
        warnings = []
        if cls.MAX_UNITS_PER_POSITION != 4:
            warnings.append(f"MAX_UNITS_PER_POSITION={cls.MAX_UNITS_PER_POSITION} (standard Turtle rule is 4)")
        if cls.PYRAMID_INCREMENT != 0.5:
            warnings.append(f"PYRAMID_INCREMENT={cls.PYRAMID_INCREMENT} (standard Turtle rule is 0.5N)")
        if cls.STOP_DISTANCE != 2.0:
            warnings.append(f"STOP_DISTANCE={cls.STOP_DISTANCE} (standard Turtle rule is 2.0N)")
        if warnings:
            print("\n⚠️  Non-standard Turtle parameters:")
            for w in warnings:
                print(f"   • {w}")

        # API keys validation for live trading
        if not cls.PAPER_TRADING:
            if not (cls.KRAKEN_API_KEY and cls.KRAKEN_API_SECRET):
                errors.append("Live trading enabled but missing Kraken API credentials")

        return errors

    @classmethod
    def print_summary(cls):
        """Print configuration summary"""
        print("\n" + "=" * 75)
        print("TURTLE BOT CONFIGURATION")
        print("=" * 75)
        print(f"\n  Account: ${cls.ACCOUNT_SIZE:,.2f}")
        print(f"  Mode: {'PAPER TRADING' if cls.PAPER_TRADING else 'LIVE TRADING'}")
        print(f"  Exchange: KRAKEN (data + execution) | CoinGecko (coin discovery only)")
        print(f"  Quote Currency: USDT ONLY")

        print(f"\n  Systems:")
        if cls.SYSTEM_1_ENABLED:
            print(f"   * System 1 (20-day): {cls.SYSTEM_SPLIT * 100:.0f}% capital")
        if cls.SYSTEM_2_ENABLED:
            print(f"   * System 2 (55-day): {(1 - cls.SYSTEM_SPLIT) * 100:.0f}% capital")

        print(f"\n  Turtle Rules:")
        print(f"   * ATR Period: {cls.ATR_PERIOD} days")
        print(f"   * Risk Per Trade: {cls.RISK_PER_TRADE * 100:.1f}%")
        print(f"   * Max Units: {cls.MAX_UNITS_PER_POSITION}")
        print(f"   * Pyramid Increment: {cls.PYRAMID_INCREMENT}N")
        print(f"   * Stop Distance: {cls.STOP_DISTANCE}N")

        print(f"\n  Risk Limits:")
        print(f"   * Max Total Risk: {cls.MAX_TOTAL_RISK * 100:.0f}%")
        print(f"   * Emergency Stop: {cls.EMERGENCY_STOP_LOSS * 100:.0f}% drawdown")
        print(f"   * Reserve Cash: {cls.RESERVE_CASH_PCT * 100:.0f}%")

        print(f"\n  Portfolio:")
        print(f"   * Max Positions: {cls.MAX_COINS}")
        print(f"   * Max Per Sector: {cls.MAX_CORRELATED_COINS}")
        if cls.SCAN_TOP_COINS:
            print(f"   * Scanning: Top {cls.TOP_N_COINS} coins (USDT pairs, batches of {cls.BATCH_SIZE})")
        else:
            print(f"   * Scanning: Fixed list (USDT pairs)")

        print(f"\n  Updates: Every {cls.CHECK_INTERVAL // 60} minutes")
        print("=" * 75 + "\n")

    @classmethod
    def from_env(cls) -> 'Config':
        """
        Load configuration from environment and validate

        Returns:
            Config instance

        Raises:
            ValueError if configuration is invalid
        """
        errors = cls.validate()

        if errors:
            raise ValueError(f"Configuration errors:\n" + "\n".join(f"  • {e}" for e in errors))

        return cls()


# Convenience function
def load_config() -> Config:
    """Load and validate configuration"""
    return Config.from_env()
