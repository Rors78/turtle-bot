"""
Bot State Management
JSON-only persistence with atomic writes
"""

import json
import os
import logging
from datetime import datetime, timezone
from typing import Dict, List, Optional

from core.position import TurtlePosition

logger = logging.getLogger(__name__)


class BotState:
    """
    Persistent bot state — all fields expected by main.py.

    Saved as JSON only (no pickle). Atomic writes via temp-file + rename
    to prevent corruption if the process dies mid-write.
    """

    def __init__(self, account_size: float = 0.0):
        # Loop counter
        self.iteration: int = 0

        # Equity tracking
        self.initial_equity: float = account_size
        self.current_equity: float = account_size
        self.peak_equity: float = account_size
        self.cash_balance: float = 0.0  # Realised cash (decremented on entry, incremented on exit)

        # Positions
        self.active_positions: Dict[str, TurtlePosition] = {}
        self.closed_positions: List[Dict] = []

        # Trade statistics
        self.total_pnl: float = 0.0
        self.total_trades: int = 0
        self.winning_trades: int = 0
        self.losing_trades: int = 0
        self.max_drawdown: float = 0.0

        # System tracking (which symbols each system owns)
        self.system_1_symbols: List[str] = []
        self.system_2_symbols: List[str] = []

        # Pause control
        self.is_paused: bool = False
        self.paused_at: Optional[datetime] = None
        self.pause_reason: str = ''

    # ─── Equity ───────────────────────────────────────────────

    def update_equity(self, new_equity: float):
        """Update current equity and track peak / max drawdown."""
        self.current_equity = new_equity
        if new_equity > self.peak_equity:
            self.peak_equity = new_equity

        if self.peak_equity > 0:
            drawdown = (self.peak_equity - new_equity) / self.peak_equity
            if drawdown > self.max_drawdown:
                self.max_drawdown = drawdown

    # ─── Positions ────────────────────────────────────────────

    def get_position(self, symbol: str) -> Optional[TurtlePosition]:
        return self.active_positions.get(symbol)

    def add_position(self, position: TurtlePosition):
        self.active_positions[position.symbol] = position
        if position.system == 1 and position.symbol not in self.system_1_symbols:
            self.system_1_symbols.append(position.symbol)
        elif position.system == 2 and position.symbol not in self.system_2_symbols:
            self.system_2_symbols.append(position.symbol)

    def close_position(self, symbol: str, exit_price: float, exit_reason: str):
        """Move position from active to closed, record trade result."""
        position = self.active_positions.pop(symbol, None)
        if not position:
            return

        pnl = position.calculate_pnl(exit_price)
        self.total_pnl += pnl
        self.total_trades += 1
        if pnl >= 0:
            self.winning_trades += 1
        else:
            self.losing_trades += 1

        # Cash back from position
        market_value = exit_price * position.total_quantity
        self.cash_balance += market_value

        # Archive
        closed = position.to_dict()
        closed['exit_price'] = exit_price
        closed['exit_reason'] = exit_reason
        closed['exit_time'] = datetime.now(timezone.utc).isoformat()
        closed['realized_pnl'] = pnl
        self.closed_positions.append(closed)

        # Remove from system symbol lists
        if symbol in self.system_1_symbols:
            self.system_1_symbols.remove(symbol)
        if symbol in self.system_2_symbols:
            self.system_2_symbols.remove(symbol)

    # ─── Summary ──────────────────────────────────────────────

    def get_summary(self) -> Dict:
        """Return dict used by notifier / dashboard."""
        win_rate = (self.winning_trades / self.total_trades) if self.total_trades > 0 else 0.0
        total_return = ((self.current_equity - self.initial_equity) / self.initial_equity) if self.initial_equity > 0 else 0.0
        return {
            'iteration': self.iteration,
            'initial_equity': self.initial_equity,
            'current_equity': self.current_equity,
            'peak_equity': self.peak_equity,
            'cash_balance': self.cash_balance,
            'total_pnl': self.total_pnl,
            'total_return_pct': total_return * 100,
            'total_trades': self.total_trades,
            'winning_trades': self.winning_trades,
            'losing_trades': self.losing_trades,
            'win_rate': win_rate,
            'max_drawdown': self.max_drawdown,
            'active_positions': len(self.active_positions),
        }

    # ─── Persistence ──────────────────────────────────────────

    def save(self, filepath: str):
        """
        Atomic JSON save: write to .tmp then rename.
        Prevents a corrupt state file if the process dies mid-write.
        """
        data = {
            'iteration': self.iteration,
            'initial_equity': self.initial_equity,
            'current_equity': self.current_equity,
            'peak_equity': self.peak_equity,
            'cash_balance': self.cash_balance,
            'total_pnl': self.total_pnl,
            'total_trades': self.total_trades,
            'winning_trades': self.winning_trades,
            'losing_trades': self.losing_trades,
            'max_drawdown': self.max_drawdown,
            'system_1_symbols': self.system_1_symbols,
            'system_2_symbols': self.system_2_symbols,
            'is_paused': self.is_paused,
            'paused_at': self.paused_at.isoformat() if self.paused_at else None,
            'pause_reason': self.pause_reason,
            'active_positions': {sym: pos.to_dict() for sym, pos in self.active_positions.items()},
            'closed_positions': self.closed_positions,
            'saved_at': datetime.now(timezone.utc).isoformat(),
        }

        tmp_path = filepath + '.tmp'
        try:
            with open(tmp_path, 'w') as f:
                json.dump(data, f, indent=2)
            os.replace(tmp_path, filepath)  # Atomic on POSIX and Windows
        except Exception as e:
            logger.error(f"Failed to save state: {e}")
            if os.path.exists(tmp_path):
                os.remove(tmp_path)
            raise

    @classmethod
    def load(cls, filepath: str, account_size: float = 0.0) -> 'BotState':
        """
        Load state from JSON file.
        Returns a fresh BotState with account_size if file doesn't exist.
        """
        state = cls(account_size=account_size)

        if not os.path.exists(filepath):
            logger.info(f"No state file at {filepath} — starting fresh")
            return state

        try:
            with open(filepath, 'r') as f:
                data = json.load(f)

            state.iteration = data.get('iteration', 0)
            state.initial_equity = data.get('initial_equity', account_size)
            state.current_equity = data.get('current_equity', account_size)
            state.peak_equity = data.get('peak_equity', account_size)
            state.cash_balance = data.get('cash_balance', 0.0)
            state.total_pnl = data.get('total_pnl', 0.0)
            state.total_trades = data.get('total_trades', 0)
            state.winning_trades = data.get('winning_trades', 0)
            state.losing_trades = data.get('losing_trades', 0)
            state.max_drawdown = data.get('max_drawdown', 0.0)
            state.system_1_symbols = data.get('system_1_symbols', [])
            state.system_2_symbols = data.get('system_2_symbols', [])
            state.is_paused = data.get('is_paused', False)
            state.pause_reason = data.get('pause_reason', '')

            paused_at = data.get('paused_at')
            state.paused_at = datetime.fromisoformat(paused_at) if paused_at else None

            # Restore active positions
            for sym, pos_data in data.get('active_positions', {}).items():
                state.active_positions[sym] = TurtlePosition.from_dict(pos_data)

            state.closed_positions = data.get('closed_positions', [])

            logger.info(f"State loaded from {filepath} "
                        f"(iteration {state.iteration}, "
                        f"{len(state.active_positions)} active positions)")

        except (json.JSONDecodeError, KeyError, ValueError) as e:
            logger.error(f"State file corrupt: {e} — starting fresh")
            return cls(account_size=account_size)

        return state
