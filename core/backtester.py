"""
Backtester
Replays historical OHLC data through TurtleEngine + RiskManager logic,
simulating the same priority order used in main.py:
  1. Stops
  2. Exits
  3. Pyramids
  4. Entries

No real API calls — everything is driven from the historical data passed in.
"""

import logging
from dataclasses import dataclass, field
from datetime import datetime, timezone, timedelta
from typing import Any, Dict, List, Optional, Tuple

from core.turtle_engine import TurtleEngine
from core.position import TurtlePosition
from risk.risk_manager import RiskManager
from utils.analytics import (
    sharpe_ratio as calc_sharpe,
    sortino_ratio as calc_sortino,
    calmar_ratio as calc_calmar,
    profit_factor as calc_profit_factor,
    max_drawdown as calc_max_drawdown,
    monthly_returns as calc_monthly_returns,
    expectancy as calc_expectancy,
)

logger = logging.getLogger(__name__)

# Kraken taker fee (0.26%)
KRAKEN_TAKER_FEE = 0.0026


@dataclass
class BacktestResult:
    """Aggregated results from a backtest run."""
    total_return: float = 0.0          # percentage (e.g. 12.5 = 12.5%)
    total_pnl: float = 0.0             # USD
    total_trades: int = 0
    winning_trades: int = 0
    losing_trades: int = 0
    win_rate: float = 0.0
    max_drawdown: float = 0.0          # fraction (e.g. 0.15 = 15%)
    sharpe_ratio: float = 0.0
    sortino_ratio: float = 0.0
    calmar_ratio: float = 0.0
    profit_factor: float = 0.0
    avg_win: float = 0.0
    avg_loss: float = 0.0
    largest_win: float = 0.0
    largest_loss: float = 0.0
    avg_holding_days: float = 0.0
    equity_curve: List[Dict] = field(default_factory=list)  # [{date, equity, drawdown}]
    trades: List[Dict] = field(default_factory=list)         # every closed trade
    monthly_returns: Dict[str, float] = field(default_factory=dict)


class Backtester:
    """
    Drives historical data through the existing TurtleEngine / RiskManager
    logic and produces a BacktestResult.
    """

    def __init__(self, config: Any) -> None:
        self.config = config
        self.engine = TurtleEngine(config)
        self.risk = RiskManager(config)
        self.slippage = getattr(config, 'PAPER_SLIPPAGE', 0.001)
        self.fee_rate = KRAKEN_TAKER_FEE

    # ─── Public entry point ───────────────────────────────────────────────────

    def run(
        self,
        historical_data: Dict[str, List[Dict]],
        start_date: str = None,
        end_date: str = None,
    ) -> BacktestResult:
        """
        Replay historical OHLC data and return a BacktestResult.

        Args:
            historical_data: {symbol: [candle_dicts]} — candles must have
                             'timestamp' (ms epoch or ISO str), 'open', 'high',
                             'low', 'close' keys.
            start_date: Optional ISO date string "YYYY-MM-DD" to slice data
            end_date: Optional ISO date string "YYYY-MM-DD" to slice data

        Returns:
            BacktestResult with all fields populated.
        """
        if not historical_data:
            return BacktestResult()

        # Normalise and sort all candles; build a unified timeline of dates
        norm_data = self._normalise_data(historical_data, start_date, end_date)
        if not norm_data:
            return BacktestResult()

        all_dates = self._build_date_timeline(norm_data)
        if not all_dates:
            return BacktestResult()

        # --- Simulation state ---
        account_size = getattr(self.config, 'ACCOUNT_SIZE', 130.0)
        cash = float(account_size)
        initial_equity = cash
        active_positions: Dict[str, TurtlePosition] = {}
        closed_trades: List[Dict] = []
        equity_curve: List[Dict] = []
        daily_returns: List[float] = []

        prev_equity = initial_equity

        # --- Day-by-day loop ---
        for date_str in all_dates:
            # Emergency stop: if equity has reached zero or below, the account is
            # wiped out — stop the simulation and record all remaining days as flat.
            if prev_equity <= 0:
                equity_curve.append({
                    'date': date_str,
                    'equity': 0.0,
                    'drawdown': 1.0,
                })
                daily_returns.append(0.0)
                continue
            # Build market snapshot for this day
            market_snapshot = self._build_snapshot(norm_data, date_str)

            if not market_snapshot:
                equity_curve.append({
                    'date': date_str,
                    'equity': prev_equity,
                    'drawdown': 0.0,
                })
                continue

            current_prices = {sym: d['price'] for sym, d in market_snapshot.items() if d['price'] > 0}

            # === PRIORITY 1: STOPS ===
            stops_hit = self._check_stops(market_snapshot, active_positions)
            for symbol in stops_hit:
                trade = self._close_position(
                    symbol, active_positions, cash,
                    market_snapshot[symbol]['price'], 'STOP_HIT', date_str
                )
                cash += trade['gross_proceeds']
                closed_trades.append(trade)

            # === PRIORITY 2: EXITS ===
            exits = self._check_exits(market_snapshot, active_positions)
            for symbol in exits:
                if symbol not in active_positions:
                    continue
                trade = self._close_position(
                    symbol, active_positions, cash,
                    market_snapshot[symbol]['price'], 'EXIT_SIGNAL', date_str
                )
                cash += trade['gross_proceeds']
                closed_trades.append(trade)

            # === PRIORITY 3: PYRAMIDS ===
            total_unrealized = sum(
                p.calculate_pnl(current_prices.get(p.symbol, p.avg_entry_price))
                for p in active_positions.values()
            )
            equity_for_sizing = cash + total_unrealized
            pyramid_ops = self._check_pyramids(market_snapshot, active_positions, equity_for_sizing)
            for op in pyramid_ops:
                cost = self._execute_pyramid(op, active_positions, cash)
                cash -= cost

            # === PRIORITY 4: ENTRIES ===
            total_unrealized = sum(
                p.calculate_pnl(current_prices.get(p.symbol, p.avg_entry_price))
                for p in active_positions.values()
            )
            equity_for_sizing = cash + total_unrealized
            entry_signals = self._check_entries(market_snapshot, active_positions, equity_for_sizing)
            for sig in entry_signals:
                cost = self._execute_entry(sig, active_positions, cash, date_str)
                cash -= cost

            # === EQUITY SNAPSHOT ===
            total_unrealized = sum(
                p.calculate_pnl(current_prices.get(p.symbol, p.avg_entry_price))
                for p in active_positions.values()
            )
            current_equity = cash + total_unrealized

            # Clamp equity to zero: once all capital is lost we stop at 0, we do
            # not allow a negative equity value to corrupt drawdown or return maths.
            current_equity = max(current_equity, 0.0)

            # Daily percentage return — prev_equity is always > 0 here because the
            # emergency-stop block at the top of the loop guards the zero case.
            daily_ret = (current_equity - prev_equity) / prev_equity
            daily_returns.append(daily_ret)

            # Running max drawdown (uses clamped current_equity)
            peak_eq = max((pt['equity'] for pt in equity_curve), default=initial_equity)
            peak_eq = max(peak_eq, current_equity)
            dd = (peak_eq - current_equity) / peak_eq if peak_eq > 0 else 0.0
            # Hard cap so the per-day drawdown field is also bounded
            dd = min(dd, 1.0)

            equity_curve.append({
                'date': date_str,
                'equity': current_equity,
                'drawdown': dd,
            })

            prev_equity = current_equity

        # --- Compute summary metrics ---
        return self._compute_result(
            closed_trades, equity_curve, daily_returns, initial_equity, all_dates
        )

    # ─── Data normalisation ───────────────────────────────────────────────────

    def _normalise_data(
        self,
        historical_data: Dict[str, List[Dict]],
        start_date: Optional[str],
        end_date: Optional[str],
    ) -> Dict[str, List[Dict]]:
        """
        Normalise candle timestamps to ISO date strings and optionally slice.
        Returns {symbol: [candle_with_date_str]}.
        """
        result = {}
        for symbol, candles in historical_data.items():
            if not candles:
                continue
            normalised = []
            for c in candles:
                date_str = self._candle_date(c)
                if not date_str:
                    continue
                if start_date and date_str < start_date:
                    continue
                if end_date and date_str > end_date:
                    continue
                nc = dict(c)
                nc['_date'] = date_str
                normalised.append(nc)
            if normalised:
                normalised.sort(key=lambda x: x['_date'])
                result[symbol] = normalised
        return result

    @staticmethod
    def _candle_date(candle: Dict) -> Optional[str]:
        """Extract YYYY-MM-DD string from a candle's timestamp field."""
        ts = candle.get('timestamp')
        if ts is None:
            # Try 'date' field directly
            ts = candle.get('date', '')
        if isinstance(ts, str):
            # Already an ISO string — take just the date part
            return ts[:10] if len(ts) >= 10 else None
        if isinstance(ts, (int, float)):
            # Millisecond epoch
            try:
                dt = datetime.fromtimestamp(ts / 1000.0, tz=timezone.utc)
                return dt.strftime('%Y-%m-%d')
            except Exception:
                pass
        return None

    @staticmethod
    def _build_date_timeline(norm_data: Dict[str, List[Dict]]) -> List[str]:
        """Build a sorted, deduplicated list of all dates across all symbols."""
        dates = set()
        for candles in norm_data.values():
            for c in candles:
                dates.add(c['_date'])
        return sorted(dates)

    # ─── Market snapshot for a single day ────────────────────────────────────

    def _build_snapshot(
        self, norm_data: Dict[str, List[Dict]], date_str: str
    ) -> Dict[str, Dict]:
        """
        Build {symbol: {ohlc, ohlc_prev, price, atr, today_candle}} for a given day.

        ohlc        — full window up to and including today (for ATR, stop checks)
        ohlc_prev   — window EXCLUDING today (for entry/exit signal generation,
                      matching the live-bot pattern where signals compare the
                      ticker's current price against the historical N-day high/low)
        price       — today's closing price
        atr         — ATR calculated from the full window
        today_candle— today's raw OHLC dict
        """
        snapshot = {}
        for symbol, candles in norm_data.items():
            # All candles up to and including today
            window = [c for c in candles if c['_date'] <= date_str]
            if not window:
                continue
            today = window[-1]
            if today['_date'] != date_str:
                # No candle for this symbol today — skip
                continue
            price = today.get('close', 0)
            if price <= 0:
                continue
            atr = self.engine.calculate_atr(window)
            # Historical window excludes today — used for signal generation
            ohlc_prev = window[:-1]
            snapshot[symbol] = {
                'ohlc': window,
                'ohlc_prev': ohlc_prev,
                'price': price,
                'atr': atr,
                'today_candle': today,
            }
        return snapshot

    # ─── Signal checking (mirrors portfolio_manager.py) ───────────────────────

    def _check_stops(
        self, snapshot: Dict, active: Dict[str, TurtlePosition]
    ) -> List[str]:
        """Return symbols where stop price was hit today."""
        hit = []
        for symbol, pos in active.items():
            data = snapshot.get(symbol)
            if not data:
                continue
            # Use the daily low to check if stop was touched intraday
            today_candle = data['ohlc'][-1]
            low = today_candle.get('low', data['price'])
            if low <= pos.stop_price:
                hit.append(symbol)
        return hit

    def _check_exits(
        self, snapshot: Dict, active: Dict[str, TurtlePosition]
    ) -> List[str]:
        """Return symbols with a Turtle exit signal (Donchian low breakdown)."""
        exits = []
        for symbol, pos in active.items():
            data = snapshot.get(symbol)
            if not data:
                continue
            # Use ohlc_prev so signal compares today's close against prior N-day low
            signal = self.engine.generate_exit_signal(data['ohlc_prev'], data['price'], pos.system)
            if signal:
                exits.append(symbol)
        return exits

    def _check_pyramids(
        self,
        snapshot: Dict,
        active: Dict[str, TurtlePosition],
        account_size: float,
    ) -> List[Dict]:
        """Return list of pyramid ops: {symbol, quantity, price, atr}."""
        ops = []
        for symbol, pos in active.items():
            if not pos.can_pyramid:
                continue
            data = snapshot.get(symbol)
            if not data or not data['atr']:
                continue
            if not pos.should_pyramid(data['price']):
                continue

            qty, notional = self.engine.calculate_position_size(
                account_size=account_size,
                atr=pos.initial_n,
                current_price=data['price'],
            )
            if qty <= 0:
                continue

            allowed, _ = self.risk.can_pyramid(pos, notional, account_size)
            if not allowed:
                continue

            ops.append({
                'symbol': symbol,
                'quantity': qty,
                'price': data['price'],
                'atr': pos.initial_n,
            })
        return ops

    def _check_entries(
        self,
        snapshot: Dict,
        active: Dict[str, TurtlePosition],
        account_size: float,
    ) -> List[Dict]:
        """Return list of entry signals filtered by risk constraints."""
        # Check total risk guard
        current_prices = {s: d['price'] for s, d in snapshot.items()}
        if self.risk.is_total_risk_exceeded(active, current_prices):
            return []

        signals = []
        systems = []
        if getattr(self.config, 'SYSTEM_1_ENABLED', True):
            systems.append(1)
        if getattr(self.config, 'SYSTEM_2_ENABLED', True):
            systems.append(2)

        for symbol, data in snapshot.items():
            if symbol in active:
                continue
            if not data['atr'] or data['price'] <= 0:
                continue

            for system in systems:
                # Use ohlc_prev: compare today's close against prior N-day high
                sufficient, _ = self.engine.check_sufficient_history(data['ohlc_prev'], system)
                if not sufficient:
                    continue

                signal = self.engine.generate_entry_signal(data['ohlc_prev'], data['price'], system)
                if not signal:
                    continue

                qty, notional = self.engine.calculate_position_size(
                    account_size=account_size,
                    atr=data['atr'],
                    current_price=data['price'],
                )
                if qty <= 0:
                    continue

                allowed, _ = self.risk.can_open_position(
                    symbol, notional, account_size, active, system
                )
                if not allowed:
                    continue

                signals.append({
                    'symbol': symbol,
                    'system': system,
                    'quantity': qty,
                    'price': data['price'],
                    'atr': data['atr'],
                })
                break  # one system per symbol per day

        return signals

    # ─── Execution (simulated) ────────────────────────────────────────────────

    def _fill_price(self, price: float, side: str) -> float:
        """Apply slippage to get a realistic fill price."""
        if side == 'buy':
            return price * (1 + self.slippage)
        else:
            return price * (1 - self.slippage)

    def _apply_fee(self, notional: float) -> float:
        """Return the fee amount for a given notional value."""
        return notional * self.fee_rate

    def _execute_entry(
        self,
        signal: Dict,
        active: Dict[str, TurtlePosition],
        cash: float,
        date_str: str,
    ) -> float:
        """
        Open a new position. Returns the cash cost (including fees).
        Modifies active in-place.
        """
        symbol = signal['symbol']
        qty = signal['quantity']
        raw_price = signal['price']
        atr = signal['atr']
        system = signal['system']

        fill_price = self._fill_price(raw_price, 'buy')
        cost = fill_price * qty
        fee = self._apply_fee(cost)
        total_cost = cost + fee

        if total_cost > cash:
            # Scale down quantity to fit available cash
            affordable_notional = cash * (1 - self.fee_rate)
            qty = affordable_notional / fill_price
            if qty <= 0:
                return 0.0
            cost = fill_price * qty
            fee = self._apply_fee(cost)
            total_cost = cost + fee

        pos = TurtlePosition(symbol=symbol, exchange='backtest', system=system)
        pos.add_unit(fill_price, qty, current_atr=atr)
        pos.opened_at = datetime.strptime(date_str, '%Y-%m-%d').replace(tzinfo=timezone.utc)
        active[symbol] = pos

        logger.debug(f"BT ENTRY {date_str}: {symbol} S{system} {qty:.6f} @ ${fill_price:.4f}")
        return total_cost

    def _execute_pyramid(
        self,
        op: Dict,
        active: Dict[str, TurtlePosition],
        cash: float,
    ) -> float:
        """
        Add a pyramid unit. Returns the cash cost (including fees).
        Modifies active in-place.
        """
        symbol = op['symbol']
        qty = op['quantity']
        raw_price = op['price']

        pos = active.get(symbol)
        if not pos:
            return 0.0

        fill_price = self._fill_price(raw_price, 'buy')
        cost = fill_price * qty
        fee = self._apply_fee(cost)
        total_cost = cost + fee

        if total_cost > cash:
            return 0.0

        pos.add_unit(fill_price, qty)
        return total_cost

    def _close_position(
        self,
        symbol: str,
        active: Dict[str, TurtlePosition],
        cash: float,
        raw_price: float,
        reason: str,
        date_str: str,
    ) -> Dict:
        """
        Close position. Returns a trade dict and removes from active.
        """
        pos = active.pop(symbol, None)
        if not pos:
            return {}

        fill_price = self._fill_price(raw_price, 'sell')
        gross_proceeds = fill_price * pos.total_quantity
        fee = self._apply_fee(gross_proceeds)
        net_proceeds = gross_proceeds - fee

        # Cost basis (entry costs)
        entry_cost = pos.get_cost_basis()
        # Entry fees already deducted from cash; net P&L is exit proceeds minus basis
        pnl = net_proceeds - entry_cost

        # Holding period
        opened_at = pos.opened_at
        try:
            closed_dt = datetime.strptime(date_str, '%Y-%m-%d').replace(tzinfo=timezone.utc)
            holding_days = max(0, (closed_dt - opened_at).days)
        except Exception:
            holding_days = 0

        trade = {
            'symbol': symbol,
            'system': pos.system,
            'entry_price': pos.avg_entry_price,
            'exit_price': fill_price,
            'quantity': pos.total_quantity,
            'units': pos.unit_count,
            'pnl': pnl,
            'pnl_pct': pnl / entry_cost if entry_cost > 0 else 0.0,
            'entry_date': pos.opened_at.strftime('%Y-%m-%d'),
            'exit_date': date_str,
            'holding_days': holding_days,
            'reason': reason,
            'gross_proceeds': net_proceeds,  # net proceeds returned to cash
        }

        logger.debug(
            f"BT CLOSE {date_str}: {symbol} {pos.total_quantity:.6f} @ ${fill_price:.4f} "
            f"PnL=${pnl:+.2f} ({reason})"
        )
        return trade

    # ─── Result computation ───────────────────────────────────────────────────

    def _compute_result(
        self,
        closed_trades: List[Dict],
        equity_curve: List[Dict],
        daily_returns: List[float],
        initial_equity: float,
        all_dates: List[str],
    ) -> BacktestResult:
        """Aggregate closed_trades and equity_curve into a BacktestResult."""
        result = BacktestResult()
        result.equity_curve = equity_curve
        result.trades = closed_trades

        if not equity_curve:
            return result

        final_equity = equity_curve[-1]['equity']
        result.total_pnl = final_equity - initial_equity
        result.total_return = (result.total_pnl / initial_equity * 100) if initial_equity > 0 else 0.0

        # Trade stats
        result.total_trades = len(closed_trades)
        winning = [t for t in closed_trades if t.get('pnl', 0) > 0]
        losing = [t for t in closed_trades if t.get('pnl', 0) <= 0]
        result.winning_trades = len(winning)
        result.losing_trades = len(losing)
        result.win_rate = result.winning_trades / result.total_trades if result.total_trades > 0 else 0.0

        win_pnls = [t['pnl'] for t in winning]
        loss_pnls = [t['pnl'] for t in losing]

        result.avg_win = sum(win_pnls) / len(win_pnls) if win_pnls else 0.0
        result.avg_loss = sum(loss_pnls) / len(loss_pnls) if loss_pnls else 0.0
        result.largest_win = max(win_pnls) if win_pnls else 0.0
        result.largest_loss = min(loss_pnls) if loss_pnls else 0.0

        holding_days = [t.get('holding_days', 0) for t in closed_trades]
        result.avg_holding_days = sum(holding_days) / len(holding_days) if holding_days else 0.0

        result.profit_factor = calc_profit_factor(win_pnls, loss_pnls)

        # Drawdown
        equity_values = [pt['equity'] for pt in equity_curve]
        dd, _, _ = calc_max_drawdown(equity_values)
        result.max_drawdown = dd

        # Ratios
        raw_sharpe = calc_sharpe(daily_returns)
        raw_sortino = calc_sortino(daily_returns)

        # Sanity guard: when the overall strategy lost money (total_return < 0)
        # both Sharpe and Sortino must be non-positive.  Large intra-period swings
        # (equity surging then crashing) can produce a positive sum/mean of daily
        # percentage returns even when final equity < initial equity, because a big
        # percentage gain on a tiny equity base outweighs earlier losses on a large
        # base.  In that case the computed ratio is misleading; flip its sign so it
        # correctly signals an undesirable outcome.
        total_return_frac = result.total_return / 100.0
        if total_return_frac < 0 and raw_sharpe > 0:
            logger.warning(
                "Sharpe sanity check: total return %.2f%% is negative but Sharpe is "
                "positive (%.4f). Negating Sharpe to reflect actual loss.",
                result.total_return, raw_sharpe,
            )
            raw_sharpe = -raw_sharpe
        if total_return_frac < 0 and raw_sortino > 0:
            logger.warning(
                "Sortino sanity check: total return %.2f%% is negative but Sortino is "
                "positive (%.4f). Negating Sortino to reflect actual loss.",
                result.total_return, raw_sortino,
            )
            raw_sortino = -raw_sortino

        result.sharpe_ratio = raw_sharpe
        result.sortino_ratio = raw_sortino

        # Calmar needs years
        if len(all_dates) >= 2:
            try:
                d0 = datetime.strptime(all_dates[0], '%Y-%m-%d')
                d1 = datetime.strptime(all_dates[-1], '%Y-%m-%d')
                years = max((d1 - d0).days / 365.25, 1 / 365.25)
            except Exception:
                years = 1.0
        else:
            years = 1.0

        total_return_frac = result.total_return / 100.0
        result.calmar_ratio = calc_calmar(total_return_frac, result.max_drawdown, years)

        # Monthly returns
        result.monthly_returns = calc_monthly_returns(equity_curve)

        return result
