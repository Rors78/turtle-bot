"""
Turtle Trading Engine
Core logic for Turtle Trading strategy
"""

from typing import List, Dict, Optional, Tuple
import logging

logger = logging.getLogger(__name__)


class TurtleEngine:
    """
    Implements core Turtle Trading rules:
    - Proper ATR (N) calculation from OHLC data
    - Correct position sizing formula
    - Entry signal detection (20-day and 55-day breakouts)
    - Exit signal detection (10-day and 20-day breakdowns)
    - Stop loss calculation (2N from entry)
    """

    def __init__(self, config):
        """
        Initialize Turtle Engine

        Args:
            config: Configuration object with ATR_PERIOD, RISK_PER_TRADE, etc.
        """
        self.config = config
        self.atr_period = getattr(config, 'ATR_PERIOD', 20)
        self.risk_per_trade = getattr(config, 'RISK_PER_TRADE', 0.02)

    def calculate_atr(self, ohlc_data: List[Dict]) -> Optional[float]:
        """
        Calculate Average True Range (N) using proper OHLC data

        Original Turtle formula:
        TR = max(
            high - low,
            abs(high - prev_close),
            abs(low - prev_close)
        )
        ATR = simple moving average of TR over period

        Args:
            ohlc_data: List of OHLC candles
                      [{'open': float, 'high': float, 'low': float,
                        'close': float, 'timestamp': int}, ...]

        Returns:
            ATR value (N) or None if insufficient data
        """
        if len(ohlc_data) < self.atr_period + 1:
            return None

        true_ranges = []

        for i in range(1, len(ohlc_data)):
            current = ohlc_data[i]
            previous = ohlc_data[i - 1]

            high = current.get('high', 0)
            low = current.get('low', 0)
            open_price = current.get('open', 0)
            close = current.get('close', 0)
            prev_close = previous.get('close', 0)

            # OHLC Validation
            # Skip candle if any value is invalid
            if any(x <= 0 for x in [high, low, open_price, close, prev_close]):
                continue

            # Validate OHLC constraints: low <= min(O,C) and max(O,C) <= high
            if not (low <= min(open_price, close) and max(open_price, close) <= high):
                logging.warning(f"Invalid OHLC at index {i}: H={high}, L={low}, O={open_price}, C={close}")
                continue

            # Calculate True Range
            tr = max(
                high - low,
                abs(high - prev_close),
                abs(low - prev_close)
            )
            true_ranges.append(tr)

        if len(true_ranges) < self.atr_period:
            return None

        # Simple moving average of last N true ranges
        atr = sum(true_ranges[-self.atr_period:]) / self.atr_period
        return atr

    def calculate_atr_from_closes(self, close_prices: List[Dict]) -> Optional[float]:
        """
        Fallback ATR estimation from close prices only (when OHLC not available)

        Uses price changes as proxy for True Range.
        Less accurate than full OHLC, but better than nothing.

        Args:
            close_prices: List of {'price': float, 'timestamp': int}

        Returns:
            Estimated ATR or None if insufficient data
        """
        if len(close_prices) < self.atr_period + 1:
            return None

        price_changes = []

        for i in range(1, len(close_prices)):
            current = close_prices[i]['price']
            previous = close_prices[i - 1]['price']

            # Absolute price change
            change = abs(current - previous)
            price_changes.append(change)

        if len(price_changes) < self.atr_period:
            return None

        # Average absolute change
        atr = sum(price_changes[-self.atr_period:]) / self.atr_period
        return atr

    def calculate_position_size(
        self,
        account_size: float,
        atr: float,
        current_price: float,
        exchange_limits: Optional[Dict] = None
    ) -> Tuple[float, float]:
        """
        Calculate proper Turtle position size

        Original Turtle formula:
        Unit = (1% of Account) / (N × Contract Size)

        Crypto adaptation:
        Unit_USD = (Account × RISK_PER_TRADE) / N
        Quantity = Unit_USD / Price

        Args:
            account_size: Total account balance in USD
            atr: Current ATR (N value)
            current_price: Current market price
            exchange_limits: Optional {'min_order': float, 'max_order': float,
                                       'min_notional': float}

        Returns:
            Tuple of (quantity, notional_usd)
        """
        if atr <= 0 or current_price <= 0:
            logger.warning("Invalid ATR or price for position sizing")
            return (0.0, 0.0)

        # Calculate unit size in USD
        unit_usd = (account_size * self.risk_per_trade) / atr

        # Convert to quantity
        quantity = unit_usd / current_price

        # Apply exchange constraints if provided
        if exchange_limits:
            min_order = exchange_limits.get('min_order', 0)
            max_order = exchange_limits.get('max_order', float('inf'))
            min_notional = exchange_limits.get('min_notional', 0)

            # Check minimum notional value
            if unit_usd < min_notional:
                logger.warning(f"Position size ${unit_usd:.2f} below min notional ${min_notional:.2f}")
                return (0.0, 0.0)

            # Clamp quantity to exchange limits
            if quantity < min_order:
                quantity = min_order
            elif quantity > max_order:
                quantity = max_order

        notional_usd = quantity * current_price

        return (quantity, notional_usd)

    def generate_entry_signal(
        self,
        ohlc_data: List[Dict],
        current_price: float,
        system: int
    ) -> Optional[Dict]:
        """
        Check for Turtle entry signal (breakout above N-day high)

        System 1 (Short-term): 20-day high breakout
        System 2 (Long-term): 55-day high breakout

        Args:
            ohlc_data: Historical OHLC data
            current_price: Current market price
            system: 1 or 2

        Returns:
            Signal dict or None
            {'signal': 'ENTRY', 'system': int, 'breakout_level': float,
             'strength': float}
        """
        if system == 1:
            lookback = getattr(self.config, 'SYSTEM_1_ENTRY', 20)
        elif system == 2:
            lookback = getattr(self.config, 'SYSTEM_2_ENTRY', 55)
        else:
            logger.error(f"Invalid system number: {system}")
            return None

        if len(ohlc_data) < lookback:
            return None

        # Get highest high over lookback period
        recent_data = ohlc_data[-lookback:]
        highest_high = max(candle.get('high', candle.get('close', 0)) for candle in recent_data)

        # Check for breakout
        if current_price > highest_high:
            # Calculate breakout strength (how far above the high)
            strength = ((current_price - highest_high) / highest_high) * 100

            return {
                'signal': 'ENTRY',
                'system': system,
                'breakout_level': highest_high,
                'current_price': current_price,
                'strength': strength
            }

        return None

    def generate_exit_signal(
        self,
        ohlc_data: List[Dict],
        current_price: float,
        system: int
    ) -> Optional[Dict]:
        """
        Check for Turtle exit signal (breakdown below N-day low)

        System 1: 10-day low breakdown
        System 2: 20-day low breakdown

        Args:
            ohlc_data: Historical OHLC data
            current_price: Current market price
            system: 1 or 2

        Returns:
            Signal dict or None
            {'signal': 'EXIT', 'system': int, 'breakdown_level': float}
        """
        if system == 1:
            lookback = getattr(self.config, 'SYSTEM_1_EXIT', 10)
        elif system == 2:
            lookback = getattr(self.config, 'SYSTEM_2_EXIT', 20)
        else:
            logger.error(f"Invalid system number: {system}")
            return None

        if len(ohlc_data) < lookback:
            return None

        # Get lowest low over lookback period
        recent_data = ohlc_data[-lookback:]
        lowest_low = min(candle.get('low', candle.get('close', 0)) for candle in recent_data)

        # Check for breakdown
        if current_price < lowest_low:
            return {
                'signal': 'EXIT',
                'system': system,
                'breakdown_level': lowest_low,
                'current_price': current_price
            }

        return None

    def calculate_stop_price(
        self,
        entry_price: float,
        atr: float,
        stop_distance: float = 2.0,
        direction: str = 'long'
    ) -> float:
        """
        Calculate Turtle stop loss price

        Turtle rule: 2N stop
        For longs: entry_price - (2 × N)
        For shorts: entry_price + (2 × N)

        Args:
            entry_price: Position entry price
            atr: ATR (N) value at entry
            stop_distance: Multiple of N for stop (default 2.0)
            direction: 'long' or 'short' (currently only long supported)

        Returns:
            Stop loss price
        """
        if direction == 'long':
            return entry_price - (stop_distance * atr)
        elif direction == 'short':
            # Future implementation for shorts
            return entry_price + (stop_distance * atr)
        else:
            raise ValueError(f"Invalid direction: {direction}")

    def check_sufficient_history(
        self,
        ohlc_data: List[Dict],
        system: int
    ) -> Tuple[bool, str]:
        """
        Check if we have enough data to generate signals

        Args:
            ohlc_data: Historical OHLC data
            system: 1 or 2

        Returns:
            Tuple of (sufficient: bool, message: str)
        """
        if system == 1:
            entry_period = getattr(self.config, 'SYSTEM_1_ENTRY', 20)
        else:
            entry_period = getattr(self.config, 'SYSTEM_2_ENTRY', 55)

        # Need entry_period + ATR_period data points minimum
        required = max(entry_period, self.atr_period) + 1

        if len(ohlc_data) < required:
            return (False, f"Need {required} candles, have {len(ohlc_data)}")

        return (True, "Sufficient data")

    def get_donchian_channels(
        self,
        ohlc_data: List[Dict],
        entry_period: int,
        exit_period: int
    ) -> Dict:
        """
        Calculate Donchian Channel levels (high and low bands)

        Used by Turtles for entry and exit signals.

        Args:
            ohlc_data: Historical OHLC data
            entry_period: Period for entry channel (20 or 55)
            exit_period: Period for exit channel (10 or 20)

        Returns:
            Dictionary with channel levels
            {'entry_high': float, 'exit_low': float}
        """
        if len(ohlc_data) < max(entry_period, exit_period):
            return {}

        # Entry channel (for breakouts)
        entry_data = ohlc_data[-entry_period:]
        entry_high = max(candle.get('high', candle.get('close', 0)) for candle in entry_data)

        # Exit channel (for breakdowns)
        exit_data = ohlc_data[-exit_period:]
        exit_low = min(candle.get('low', candle.get('close', 0)) for candle in exit_data)

        return {
            'entry_high': entry_high,
            'exit_low': exit_low
        }
