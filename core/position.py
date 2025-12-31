"""
Turtle Position Data Structure
Tracks individual positions with pyramiding, stops, and P&L
"""

from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import List, Dict, Optional


@dataclass
class Unit:
    """A single unit within a Turtle position"""
    entry_price: float
    quantity: float
    entry_time: datetime

    def to_dict(self) -> Dict:
        return {
            'entry_price': self.entry_price,
            'quantity': self.quantity,
            'entry_time': self.entry_time.isoformat()
        }

    @classmethod
    def from_dict(cls, data: Dict) -> 'Unit':
        return cls(
            entry_price=data['entry_price'],
            quantity=data['quantity'],
            entry_time=datetime.fromisoformat(data['entry_time'])
        )


@dataclass
class TurtlePosition:
    """
    Represents a single Turtle position with pyramiding support

    Key Turtle Rules Implemented:
    - Max 4 units per position
    - Add units at 0.5N intervals
    - Stop loss at 2N from newest entry
    - N (ATR) locked at initial entry
    """
    symbol: str
    exchange: str
    system: int  # 1 (20-day) or 2 (55-day)

    # Units (max 4)
    units: List[Unit] = field(default_factory=list)

    # ATR locked at first entry (Turtle rule: N doesn't change)
    initial_atr: float = 0.0
    initial_n: float = 0.0  # Alias for clarity

    # Stop tracking
    stop_price: float = 0.0  # 2N from newest entry

    # Position metrics
    avg_entry_price: float = 0.0
    total_quantity: float = 0.0
    unrealized_pnl: float = 0.0

    # Metadata
    opened_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    last_pyramid_price: float = 0.0  # Track for 0.5N increment checks

    def __post_init__(self):
        """Ensure N values are synced"""
        if self.initial_n == 0.0 and self.initial_atr > 0.0:
            self.initial_n = self.initial_atr
        elif self.initial_atr == 0.0 and self.initial_n > 0.0:
            self.initial_atr = self.initial_n

    @property
    def unit_count(self) -> int:
        """Number of units in this position"""
        return len(self.units)

    @property
    def can_pyramid(self) -> bool:
        """Can we add another unit? (max 4 Turtle rule)"""
        return self.unit_count < 4

    @property
    def is_empty(self) -> bool:
        """Position has no units"""
        return self.unit_count == 0

    def add_unit(self, price: float, quantity: float, current_atr: float = None):
        """
        Add a pyramid unit (max 4 total per Turtle rules)

        Args:
            price: Entry price for this unit
            quantity: Number of coins/tokens
            current_atr: Current ATR (only used for first unit to lock N)
        """
        if self.unit_count >= 4:
            raise ValueError("Cannot add more than 4 units (Turtle rule)")

        # Create new unit
        new_unit = Unit(
            entry_price=price,
            quantity=quantity,
            entry_time=datetime.now(timezone.utc)
        )
        self.units.append(new_unit)

        # Lock N value on first entry
        if self.unit_count == 1 and current_atr:
            self.initial_atr = current_atr
            self.initial_n = current_atr
            self.opened_at = new_unit.entry_time

        # Update position metrics
        self._recalculate_metrics()

        # Update stop to 2N from this new entry
        self.update_stop(price)

        # Track this price for next pyramid check
        self.last_pyramid_price = price

    def update_stop(self, latest_entry_price: float):
        """
        Move stop to 2N below latest entry (Turtle rule)

        After pyramiding, the stop moves up to protect the newest unit
        while still allowing earlier units room to run.
        """
        if self.initial_n <= 0:
            raise ValueError("Cannot set stop: N value not initialized")

        # Stop is 2N below the most recent entry (with minimum price guard)
        self.stop_price = max(0.01, latest_entry_price - (2.0 * self.initial_n))

    def check_stop_hit(self, current_price: float) -> bool:
        """
        Check if 2N stop loss has been hit

        Returns:
            True if current price at or below stop price
        """
        return current_price <= self.stop_price

    def should_pyramid(self, current_price: float) -> bool:
        """
        Check if price has moved 0.5N favorable for next unit (Turtle rule)

        Returns:
            True if current price >= last_entry + 0.5N
        """
        if not self.can_pyramid:
            return False

        if self.initial_n <= 0 or self.last_pyramid_price <= 0:
            return False

        # Need 0.5N move above last pyramid entry
        required_price = self.last_pyramid_price + (0.5 * self.initial_n)
        return current_price >= required_price

    def calculate_pnl(self, current_price: float) -> float:
        """
        Calculate unrealized P&L for entire position

        Returns:
            Unrealized P&L in USD
        """
        if self.is_empty:
            return 0.0

        pnl = 0.0
        for unit in self.units:
            unit_pnl = (current_price - unit.entry_price) * unit.quantity
            pnl += unit_pnl

        self.unrealized_pnl = pnl
        return pnl

    def calculate_pnl_pct(self, current_price: float) -> float:
        """
        Calculate unrealized P&L as percentage of cost basis

        Returns:
            P&L percentage (e.g., 0.15 for 15%)
        """
        if self.is_empty or self.avg_entry_price <= 0:
            return 0.0

        return (current_price - self.avg_entry_price) / self.avg_entry_price

    def get_cost_basis(self) -> float:
        """
        Total USD invested in this position

        Returns:
            Sum of (entry_price × quantity) for all units
        """
        return sum(unit.entry_price * unit.quantity for unit in self.units)

    def get_market_value(self, current_price: float) -> float:
        """
        Current market value of position

        Returns:
            current_price × total_quantity
        """
        return current_price * self.total_quantity

    def _recalculate_metrics(self):
        """Recalculate average entry and total quantity"""
        if self.is_empty:
            self.avg_entry_price = 0.0
            self.total_quantity = 0.0
            return

        total_cost = sum(unit.entry_price * unit.quantity for unit in self.units)
        self.total_quantity = sum(unit.quantity for unit in self.units)

        if self.total_quantity > 0:
            self.avg_entry_price = total_cost / self.total_quantity
        else:
            self.avg_entry_price = 0.0

    def to_dict(self) -> Dict:
        """Serialize to dictionary for state persistence"""
        return {
            'symbol': self.symbol,
            'exchange': self.exchange,
            'system': self.system,
            'units': [unit.to_dict() for unit in self.units],
            'initial_atr': self.initial_atr,
            'initial_n': self.initial_n,
            'stop_price': self.stop_price,
            'avg_entry_price': self.avg_entry_price,
            'total_quantity': self.total_quantity,
            'unrealized_pnl': self.unrealized_pnl,
            'opened_at': self.opened_at.isoformat(),
            'last_pyramid_price': self.last_pyramid_price
        }

    @classmethod
    def from_dict(cls, data: Dict) -> 'TurtlePosition':
        """Deserialize from dictionary"""
        position = cls(
            symbol=data['symbol'],
            exchange=data['exchange'],
            system=data['system'],
            initial_atr=data['initial_atr'],
            initial_n=data.get('initial_n', data['initial_atr']),
            stop_price=data['stop_price'],
            avg_entry_price=data['avg_entry_price'],
            total_quantity=data['total_quantity'],
            unrealized_pnl=data['unrealized_pnl'],
            opened_at=datetime.fromisoformat(data['opened_at']),
            last_pyramid_price=data['last_pyramid_price']
        )

        # Restore units
        position.units = [Unit.from_dict(u) for u in data['units']]

        return position

    def __repr__(self) -> str:
        """String representation for debugging"""
        return (f"TurtlePosition({self.symbol}, System {self.system}, "
                f"{self.unit_count} units, "
                f"Avg Entry: ${self.avg_entry_price:.2f}, "
                f"Stop: ${self.stop_price:.2f}, "
                f"Total Qty: {self.total_quantity:.6f})")
