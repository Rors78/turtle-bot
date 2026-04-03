"""
Order Audit Trail
Appends every order event to a JSON Lines file for compliance and debugging.
"""

import json
import logging
from datetime import datetime, timezone
from typing import Optional

logger = logging.getLogger(__name__)

# Valid event types — mirrors the execution paths in PortfolioManager
EVENT_TYPES = frozenset({'ENTRY', 'PYRAMID', 'EXIT', 'STOP_HIT', 'EMERGENCY_STOP'})


class AuditLog:
    """
    Append-only audit trail for all order events.

    Each record is written as a single JSON line to the configured file.
    Writes are atomic in the sense that each call opens, appends one line,
    flushes, and closes — no partial lines can be left by an abrupt exit
    between records.
    """

    def __init__(self, filepath: str = 'trade_audit.jsonl'):
        self.filepath = filepath

    def log_order(
        self,
        event_type: str,
        symbol: str,
        side: str,
        quantity: float,
        price: float,
        fill_price: float,
        order_id: str,
        system: int,
        pnl: Optional[float] = None,
        reason: Optional[str] = None,
    ) -> None:
        """
        Append one order event to the audit file.

        Args:
            event_type:  One of ENTRY, PYRAMID, EXIT, STOP_HIT, EMERGENCY_STOP
            symbol:      Trading pair (e.g. 'BTC/USDT')
            side:        'buy' or 'sell'
            quantity:    Order quantity in base currency
            price:       Requested/signal price
            fill_price:  Actual execution price (may differ due to slippage)
            order_id:    Exchange order ID (or paper order ID)
            system:      Turtle system number (1 or 2)
            pnl:         Realised P&L in USD (exits only)
            reason:      Human-readable reason string (e.g. 'STOP_HIT', 'EXIT_SIGNAL')
        """
        if event_type not in EVENT_TYPES:
            logger.warning(f"AuditLog: unknown event_type '{event_type}' — logging anyway")

        record = {
            'timestamp': datetime.now(timezone.utc).isoformat(),
            'event_type': event_type,
            'symbol': symbol,
            'side': side,
            'quantity': quantity,
            'price': price,
            'fill_price': fill_price,
            'order_id': order_id,
            'system': system,
            'pnl': pnl,
            'reason': reason,
        }

        try:
            with open(self.filepath, 'a', encoding='utf-8') as fh:
                fh.write(json.dumps(record) + '\n')
                fh.flush()
        except OSError as exc:
            # Log but never crash the bot over an audit write failure
            logger.error(f"AuditLog: failed to write record: {exc}")
