"""
Risk Manager
Enforces Turtle risk rules and Kraken order size limits
"""

import logging
from typing import Any, Dict, Optional, Tuple

logger = logging.getLogger(__name__)


class RiskManager:
    """
    Validates all risk constraints before any trade is allowed:
    - Emergency drawdown stop
    - Max total portfolio risk
    - Per-symbol position limits
    - Sector correlation limits
    - Kraken minimum order size enforcement
    """

    def __init__(self, config: Any) -> None:
        self.config = config
        self.max_total_risk = getattr(config, 'MAX_TOTAL_RISK', 0.20)
        self.emergency_stop_loss = getattr(config, 'EMERGENCY_STOP_LOSS', 0.30)
        self.reserve_cash_pct = getattr(config, 'RESERVE_CASH_PCT', 0.10)
        self.max_coins = getattr(config, 'MAX_COINS', 10)
        self.max_correlated_coins = getattr(config, 'MAX_CORRELATED_COINS', 2)
        self.max_allocation = getattr(config, 'MAX_ALLOCATION', 0.50)
        self.coin_sectors = getattr(config, 'COIN_SECTORS', {})

    def check_emergency_stop(self, current_equity: float, initial_equity: float) -> bool:
        """
        Check if portfolio drawdown has breached the emergency stop threshold.

        Returns True if emergency stop should trigger.
        """
        if initial_equity <= 0:
            return False
        drawdown = (initial_equity - current_equity) / initial_equity
        return drawdown >= self.emergency_stop_loss

    def can_open_position(
        self,
        symbol: str,
        notional_usd: float,
        account_balance: float,
        active_positions: Dict,
        system: int,
    ) -> Tuple[bool, str]:
        """
        Check all risk constraints before opening a new position.

        Args:
            symbol: Trading pair (e.g. 'BTC/USDT')
            notional_usd: Dollar value of the proposed position
            account_balance: Available cash
            active_positions: Current open positions dict
            system: 1 or 2

        Returns:
            (allowed: bool, reason: str)
        """
        base = symbol.split('/')[0]

        # Already have a position in this symbol
        if symbol in active_positions:
            return False, f"Already have position in {symbol}"

        # Check same symbol not in both systems
        for pos in active_positions.values():
            if pos.symbol == symbol:
                return False, f"{symbol} already open in System {pos.system}"

        # Max positions cap
        if len(active_positions) >= self.max_coins:
            return False, f"Max positions ({self.max_coins}) reached"

        # Reserve cash: don't deploy the last reserve_cash_pct
        deployable = account_balance * (1 - self.reserve_cash_pct)
        if notional_usd > deployable:
            return False, f"Would exceed deployable cash (${deployable:,.2f} available)"

        # Per-position allocation cap
        total_equity_estimate = account_balance  # conservative
        if total_equity_estimate > 0 and notional_usd / total_equity_estimate > self.max_allocation:
            return False, f"Position size {notional_usd / total_equity_estimate:.1%} exceeds max allocation {self.max_allocation:.1%}"

        # Sector correlation limit
        sector = self.coin_sectors.get(base)
        if sector:
            sector_count = sum(
                1 for pos in active_positions.values()
                if self.coin_sectors.get(pos.symbol.split('/')[0]) == sector
            )
            if sector_count >= self.max_correlated_coins:
                return False, f"Sector '{sector}' already has {sector_count} positions (max {self.max_correlated_coins})"

        return True, "OK"

    def can_pyramid(
        self,
        position,
        notional_usd: float,
        account_balance: float,
    ) -> Tuple[bool, str]:
        """
        Check if a pyramid add is allowed from a risk perspective.

        Args:
            position: TurtlePosition instance
            notional_usd: Dollar value of the pyramid unit
            account_balance: Available cash

        Returns:
            (allowed: bool, reason: str)
        """
        if not position.can_pyramid:
            return False, f"Position already at max units ({position.unit_count}/4)"

        deployable = account_balance * (1 - self.reserve_cash_pct)
        if notional_usd > deployable:
            return False, f"Pyramid would exceed deployable cash (${deployable:,.2f})"

        return True, "OK"

    def validate_kraken_order(
        self,
        symbol: str,
        quantity: float,
        price: float,
        exchange,
    ) -> Tuple[bool, str]:
        """
        Validate order meets Kraken's minimum size and notional requirements.

        Args:
            symbol: Trading pair
            quantity: Order quantity (in base currency)
            price: Current price (for notional check)
            exchange: CCXTAdapter instance

        Returns:
            (valid: bool, reason: str)
        """
        try:
            limits = exchange.get_trading_limits(symbol)
        except Exception as e:
            logger.warning(f"Could not fetch Kraken limits for {symbol}: {e}")
            return True, "Limits unavailable — proceeding"

        min_qty = limits.get('min_order', 0)
        min_notional = limits.get('min_notional', 0)
        notional = quantity * price

        if min_qty and quantity < min_qty:
            return False, f"Qty {quantity:.8f} below Kraken min {min_qty:.8f} for {symbol}"

        if min_notional and notional < min_notional:
            return False, f"Notional ${notional:.2f} below Kraken min ${min_notional:.2f} for {symbol}"

        return True, "OK"

    def calculate_total_risk(self, active_positions: Dict, current_prices: Dict) -> float:
        """
        Calculate current total portfolio risk as fraction of equity.
        Risk is defined as the total potential loss if all stops were hit simultaneously.

        Returns:
            Total risk as a fraction (e.g. 0.15 = 15%)
        """
        total_risk_usd = 0.0
        total_value = 0.0

        for symbol, pos in active_positions.items():
            price = current_prices.get(symbol, 0)
            if price <= 0:
                continue
            market_value = pos.get_market_value(price)
            stop_loss_value = pos.stop_price * pos.total_quantity
            risk_usd = market_value - stop_loss_value
            total_risk_usd += max(risk_usd, 0)
            total_value += market_value

        if total_value <= 0:
            return 0.0

        return total_risk_usd / total_value

    def is_total_risk_exceeded(self, active_positions: Dict, current_prices: Dict) -> bool:
        """Returns True if total portfolio risk exceeds MAX_TOTAL_RISK."""
        return self.calculate_total_risk(active_positions, current_prices) > self.max_total_risk
