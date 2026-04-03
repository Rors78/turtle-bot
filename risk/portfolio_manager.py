"""
Portfolio Manager
Orchestrates all trading decisions: stops, exits, pyramids, entries.
Uses TurtleEngine for signals and RiskManager for constraint checks.
"""

import logging
from typing import Any, Dict, List, Optional

import config as _config_module
from core.position import TurtlePosition
from utils.notifications import Colors, colored
from utils.audit import AuditLog

logger = logging.getLogger(__name__)


class PortfolioManager:
    """
    Executes the Turtle trading loop in correct priority order:
      1. Stop loss checks
      2. Exit signal checks
      3. Pyramid opportunities
      4. New entry signals

    All order execution goes through CCXTAdapter which enforces
    paper/live mode. All risk checks go through RiskManager.
    """

    def __init__(self, config: Any, turtle_engine: Any, risk_manager: Any, exchanges: Dict, notifier: Any) -> None:
        self.config = config
        self.engine = turtle_engine
        self.risk = risk_manager
        self.exchanges = exchanges
        self.notifier = notifier
        self.exchange = exchanges.get('kraken') or next(iter(exchanges.values()))
        self.audit = AuditLog(filepath=getattr(config, 'AUDIT_FILE', 'trade_audit.jsonl'))

        # Regime detector — only instantiated when the filter is enabled
        self.regime_detector = None
        if getattr(config, 'REGIME_FILTER_ENABLED', False):
            from utils.regime import RegimeDetector
            self.regime_detector = RegimeDetector(config)

    # ─── Stop Scanning ────────────────────────────────────────

    def scan_for_stops(
        self,
        market_data: Dict,
        active_positions: Dict,
    ) -> List[str]:
        """
        Check all active positions for stop loss hits.

        Returns list of symbols that have hit their stop.
        """
        hit = []
        for symbol, position in active_positions.items():
            data = market_data.get(symbol)
            if not data:
                continue
            price = data.get('price', 0)
            if price <= 0:
                continue
            if position.check_stop_hit(price):
                logger.info(f"Stop hit: {symbol} @ ${price:,.4f} (stop ${position.stop_price:,.4f})")
                hit.append(symbol)
        return hit

    # ─── Trailing Stops ───────────────────────────────────────────

    def scan_trailing_stops(
        self,
        market_data: Dict,
        active_positions: Dict,
    ) -> None:
        """
        Update trailing stops for all active positions when enabled.

        Loops through all active positions and calls
        position.update_trailing_stop() for each one.  Stop movements
        are logged at INFO level.
        """
        if not getattr(self.config, 'TRAILING_STOP_ENABLED', False):
            return

        distance = getattr(self.config, 'TRAILING_STOP_DISTANCE', 2.0)

        for symbol, position in active_positions.items():
            data = market_data.get(symbol)
            if not data:
                continue
            price = data.get('price', 0)
            if price <= 0:
                continue

            old_stop = position.stop_price
            position.update_trailing_stop(price, trailing_distance=distance)
            if position.stop_price > old_stop:
                logger.info(
                    f"Trailing stop updated: {symbol} stop moved to ${position.stop_price:.4f}"
                )

    # ─── Exit Scanning ────────────────────────────────────────

    def scan_for_exits(
        self,
        market_data: Dict,
        active_positions: Dict,
    ) -> List[str]:
        """
        Check all active positions for Turtle exit signals (Donchian low breakdown).

        Returns list of symbols with exit signals.
        """
        exits = []
        for symbol, position in active_positions.items():
            data = market_data.get(symbol)
            if not data:
                continue
            ohlc = data.get('ohlc', [])
            price = data.get('price', 0)
            if not ohlc or price <= 0:
                continue

            signal = self.engine.generate_exit_signal(ohlc, price, position.system)
            if signal:
                logger.info(f"Exit signal: {symbol} S{position.system} @ ${price:,.4f} "
                            f"(breakdown below ${signal['breakdown_level']:,.4f})")
                exits.append(symbol)

        return exits

    # ─── Pyramid Scanning ─────────────────────────────────────

    def scan_for_pyramids(
        self,
        market_data: Dict,
        active_positions: Dict,
        account_balance: float,
    ) -> List[Dict]:
        """
        Check all active positions for pyramid opportunities (0.5N move).

        Returns list of pyramid dicts: {'symbol', 'quantity', 'price', 'atr'}
        """
        ops = []
        for symbol, position in active_positions.items():
            if not position.can_pyramid:
                continue

            data = market_data.get(symbol)
            if not data:
                continue
            price = data.get('price', 0)
            atr = data.get('atr')
            ohlc = data.get('ohlc', [])

            if price <= 0 or not atr:
                continue

            if not position.should_pyramid(price):
                continue

            # Size the pyramid unit
            quantity, notional = self.engine.calculate_position_size(
                account_size=account_balance,
                atr=position.initial_n,  # Use locked-in N from first entry
                current_price=price,
                exchange_limits=self.exchange.get_trading_limits(symbol),
            )
            if quantity <= 0:
                continue

            # Risk check
            allowed, reason = self.risk.can_pyramid(position, notional, account_balance)
            if not allowed:
                logger.debug(f"Pyramid blocked for {symbol}: {reason}")
                continue

            # Kraken min order check
            valid, reason = self.risk.validate_kraken_order(symbol, quantity, price, self.exchange)
            if not valid:
                logger.warning(f"Pyramid order invalid for {symbol}: {reason}")
                continue

            ops.append({
                'symbol': symbol,
                'quantity': quantity,
                'price': price,
                'atr': position.initial_n,
            })

        return ops

    # ─── Entry Scanning ───────────────────────────────────────

    def scan_for_entries(
        self,
        market_data: Dict,
        active_positions: Dict,
        account_balance: float,
    ) -> List[Dict]:
        """
        Scan universe for Turtle entry signals on both systems.

        Returns list of entry dicts: {'symbol', 'system', 'quantity', 'price', 'atr'}
        """
        signals = []

        # Check total risk before scanning
        current_prices = {sym: d.get('price', 0) for sym, d in market_data.items()}
        if self.risk.is_total_risk_exceeded(active_positions, current_prices):
            logger.info("Total portfolio risk exceeded — skipping entry scan")
            return []

        systems = []
        if getattr(self.config, 'SYSTEM_1_ENABLED', True):
            systems.append(1)
        if getattr(self.config, 'SYSTEM_2_ENABLED', True):
            systems.append(2)

        for symbol, data in market_data.items():
            ohlc = data.get('ohlc', [])
            price = data.get('price', 0)
            atr = data.get('atr')

            if not ohlc or price <= 0 or not atr:
                continue

            # Skip if we already have a position here
            if symbol in active_positions:
                continue

            # Regime filter — only applied to NEW entries
            if self.regime_detector is not None:
                enter_ok, regime_msg = self.regime_detector.should_enter(ohlc)
                if not enter_ok:
                    logger.debug(f"Regime filter blocked {symbol}: {regime_msg}")
                    continue

            for system in systems:
                sufficient, msg = self.engine.check_sufficient_history(ohlc, system)
                if not sufficient:
                    continue

                signal = self.engine.generate_entry_signal(ohlc, price, system)
                if not signal:
                    continue

                # Size the position
                quantity, notional = self.engine.calculate_position_size(
                    account_size=account_balance,
                    atr=atr,
                    current_price=price,
                    exchange_limits=self.exchange.get_trading_limits(symbol),
                )
                if quantity <= 0:
                    continue

                # Risk checks
                allowed, reason = self.risk.can_open_position(
                    symbol, notional, account_balance, active_positions, system
                )
                if not allowed:
                    logger.debug(f"Entry blocked {symbol} S{system}: {reason}")
                    continue

                # Kraken min order check
                valid, reason = self.risk.validate_kraken_order(symbol, quantity, price, self.exchange)
                if not valid:
                    logger.warning(f"Entry order invalid {symbol}: {reason}")
                    continue

                signals.append({
                    'symbol': symbol,
                    'system': system,
                    'quantity': quantity,
                    'price': price,
                    'atr': atr,
                    'breakout_level': signal.get('breakout_level', 0),
                })

                # Only take one system's signal per symbol per cycle
                break

        return signals

    # ─── Execution ────────────────────────────────────────────

    def execute_entry(
        self,
        symbol: str,
        system: int,
        exchange_name: str,
        quantity: float,
        price: float,
        atr: float,
        state: Any,
    ) -> None:
        """Open a new Turtle position (Unit 1)."""
        try:
            order = self.exchange.create_market_order(symbol, 'buy', quantity)
            fill_price = order.get('price', price)
            fill_qty = order.get('filled', quantity)

            position = TurtlePosition(
                symbol=symbol,
                exchange=exchange_name,
                system=system,
            )
            position.add_unit(fill_price, fill_qty, current_atr=atr)

            state.add_position(position)

            # Deduct from cash balance
            cost = fill_price * fill_qty
            state.cash_balance -= cost

            stop = position.stop_price
            self.notifier.alert_entry(symbol, system, fill_price, fill_qty, atr, stop)
            logger.info(f"Entered {symbol} S{system}: {fill_qty:.6f} @ ${fill_price:,.4f}, stop ${stop:,.4f}")

            self.audit.log_order(
                event_type='ENTRY',
                symbol=symbol,
                side='buy',
                quantity=fill_qty,
                price=price,
                fill_price=fill_price,
                order_id=order.get('id', ''),
                system=system,
                reason=f"S{system} breakout",
            )

        except Exception as e:
            self.notifier.alert_error(f"Entry failed for {symbol}", e)

    def execute_pyramid(
        self,
        symbol: str,
        quantity: float,
        price: float,
        state: Any,
    ) -> None:
        """Add a pyramid unit to an existing position."""
        position = state.get_position(symbol)
        if not position:
            logger.warning(f"Pyramid requested but no position found for {symbol}")
            return

        try:
            order = self.exchange.create_market_order(symbol, 'buy', quantity)
            fill_price = order.get('price', price)
            fill_qty = order.get('filled', quantity)

            unit_num = position.unit_count + 1
            position.add_unit(fill_price, fill_qty)

            cost = fill_price * fill_qty
            state.cash_balance -= cost

            self.notifier.alert_pyramid(symbol, unit_num, fill_price, fill_qty)
            logger.info(f"Pyramid U{unit_num} {symbol}: {fill_qty:.6f} @ ${fill_price:,.4f}, "
                        f"new stop ${position.stop_price:,.4f}")

            self.audit.log_order(
                event_type='PYRAMID',
                symbol=symbol,
                side='buy',
                quantity=fill_qty,
                price=price,
                fill_price=fill_price,
                order_id=order.get('id', ''),
                system=position.system,
                reason=f"pyramid unit {unit_num}",
            )

        except Exception as e:
            self.notifier.alert_error(f"Pyramid failed for {symbol}", e)

    def execute_exit(
        self,
        symbol: str,
        price: float,
        reason: str,
        state: Any,
    ) -> None:
        """Close an entire position."""
        position = state.get_position(symbol)
        if not position:
            logger.warning(f"Exit requested but no position for {symbol}")
            return

        try:
            total_qty = position.total_quantity
            order = self.exchange.create_market_order(symbol, 'sell', total_qty)
            fill_price = order.get('price', price)

            pnl = position.calculate_pnl(fill_price)
            pnl_pct = position.calculate_pnl_pct(fill_price)

            # Map caller-provided reason to a canonical event_type
            _event_map = {
                'EMERGENCY_STOP': 'EMERGENCY_STOP',
                'STOP_HIT': 'STOP_HIT',
            }
            event_type = _event_map.get(reason, 'EXIT')

            state.close_position(symbol, fill_price, reason)

            self.notifier.alert_exit(symbol, reason, fill_price, pnl, pnl_pct)
            logger.info(f"Exited {symbol} ({reason}): {total_qty:.6f} @ ${fill_price:,.4f}, "
                        f"P&L ${pnl:+,.2f} ({pnl_pct:+.1%})")

            self.audit.log_order(
                event_type=event_type,
                symbol=symbol,
                side='sell',
                quantity=total_qty,
                price=price,
                fill_price=fill_price,
                order_id=order.get('id', ''),
                system=position.system,
                pnl=pnl,
                reason=reason,
            )

        except Exception as e:
            self.notifier.alert_error(f"Exit failed for {symbol}", e)
