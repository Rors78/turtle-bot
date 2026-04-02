"""
Notifications, Colors, and Console Output
ANSI terminal colors + structured alerts for trading events
"""

import logging
from typing import Dict

logger = logging.getLogger(__name__)


# ---- ANSI Color Constants ----

class Colors:
    RESET  = "\033[0m"
    BOLD   = "\033[1m"
    DIM    = "\033[2m"
    RED    = "\033[91m"
    GREEN  = "\033[92m"
    YELLOW = "\033[93m"
    BLUE   = "\033[94m"
    PURPLE = "\033[95m"
    CYAN   = "\033[96m"
    WHITE  = "\033[97m"
    GRAY   = "\033[90m"
    ORANGE = "\033[33m"


def colored(text: str, color: str) -> str:
    """Wrap text in ANSI color codes."""
    return f"{color}{text}{Colors.RESET}"


# ---- Notifier ----

class Notifier:
    """
    Handles all console output and alerting for the bot.
    Structured for easy extension (e.g. Discord webhook, email) later.
    """

    def __init__(self, config):
        self.config = config
        self.alert_on_entry = getattr(config, 'ALERT_ON_ENTRY', True)
        self.alert_on_exit  = getattr(config, 'ALERT_ON_EXIT', True)
        self.alert_on_stop  = getattr(config, 'ALERT_ON_STOP', True)
        self.alert_on_error = getattr(config, 'ALERT_ON_ERROR', True)

    def print_banner(self):
        """Print startup banner."""
        mode = "Paper Mode" if getattr(self.config, 'PAPER_TRADING', True) else "LIVE TRADING"
        print(colored("-" * 75, Colors.CYAN))
        print(colored(f"  TURTLE BOT  --  Kraken Spot  --  {mode}", Colors.CYAN))
        print(colored("  System 1: 20-day breakout | System 2: 55-day breakout", Colors.GRAY))
        print(colored("  Stops: 2N | Pyramid: 4 units at 0.5N | Risk: 1% per unit", Colors.GRAY))
        print(colored("-" * 75, Colors.CYAN))

    def alert_entry(self, symbol: str, system: int, price: float,
                    quantity: float, atr: float, stop: float):
        if not self.alert_on_entry:
            return
        tag = colored(f"[S{system} ENTRY]", Colors.GREEN)
        print(f"\n{tag} {colored(symbol, Colors.WHITE)}")
        print(f"   Price: ${price:,.4f}  |  Qty: {quantity:.6f}  |  ATR: ${atr:,.4f}")
        print(f"   Stop:  ${stop:,.4f}  |  Risk: ${(price - stop) * quantity:,.2f}")

    def alert_exit(self, symbol: str, reason: str, price: float,
                   pnl: float, pnl_pct: float):
        if not self.alert_on_exit:
            return
        color = Colors.GREEN if pnl >= 0 else Colors.RED
        tag = colored(f"[EXIT {reason}]", color)
        pnl_str = colored(f"${pnl:+,.2f} ({pnl_pct:+.1%})", color)
        print(f"\n{tag} {colored(symbol, Colors.WHITE)}  P&L: {pnl_str}")
        print(f"   Exit price: ${price:,.4f}")

    def alert_stop_hit(self, symbol: str, price: float, stop: float, market_value: float):
        if not self.alert_on_stop:
            return
        tag = colored("[STOP HIT]", Colors.RED)
        print(f"\n{tag} {colored(symbol, Colors.WHITE)}")
        print(f"   Price: ${price:,.4f}  |  Stop was: ${stop:,.4f}  |  Value: ${market_value:,.2f}")

    def alert_pyramid(self, symbol: str, unit_num: int, price: float, quantity: float):
        tag = colored(f"[PYRAMID U{unit_num}]", Colors.CYAN)
        print(f"\n{tag} {colored(symbol, Colors.WHITE)}")
        print(f"   Price: ${price:,.4f}  |  Qty: {quantity:.6f}")

    def alert_error(self, message: str, error: Exception = None):
        if not self.alert_on_error:
            return
        tag = colored("[ERROR]", Colors.RED)
        print(f"\n{tag} {message}")
        if error:
            print(f"   {colored(str(error), Colors.GRAY)}")
        logger.error(f"{message}: {error}" if error else message)

    def print_portfolio_summary(self, state, current_prices: Dict):
        """Print a summary table of all active positions."""
        print(colored(f"\n  Portfolio ({len(state.active_positions)} positions):", Colors.BLUE))
        hdr = f"   {'Symbol':<12} {'Sys':>3}  {'Units':>5}  {'Avg Entry':>12}  {'Price':>12}  {'P&L':>12}  {'Stop':>12}"
        print(colored(hdr, Colors.GRAY))
        print(colored("   " + "-" * 70, Colors.GRAY))

        for symbol, pos in state.active_positions.items():
            price = current_prices.get(symbol, 0)
            pnl = pos.calculate_pnl(price)
            pnl_color = Colors.GREEN if pnl >= 0 else Colors.RED
            pnl_str = colored(f"${pnl:>+,.2f}", pnl_color)
            print(
                f"   {colored(symbol, Colors.WHITE):<12} "
                f"S{pos.system}   "
                f"{pos.unit_count:>5}  "
                f"${pos.avg_entry_price:>11,.4f}  "
                f"${price:>11,.4f}  "
                f"{pnl_str:>12}  "
                f"${pos.stop_price:>11,.4f}"
            )

        eq_color = Colors.GREEN if state.current_equity >= state.initial_equity else Colors.RED
        print(colored(
            f"\n   Equity: {colored(f'${state.current_equity:,.2f}', eq_color)}"
            f"  |  Cash: ${state.cash_balance:,.2f}"
            f"  |  Peak: ${state.peak_equity:,.2f}"
            f"  |  Drawdown: {state.max_drawdown:.1%}",
            Colors.GRAY
        ))

    def print_performance(self, state):
        """Print performance statistics."""
        summary = state.get_summary()
        win_rate = summary['win_rate']
        wr_color = Colors.GREEN if win_rate >= 0.5 else Colors.YELLOW

        pnl = summary['total_pnl']
        ret = summary['total_return_pct']
        dd  = summary['max_drawdown']
        pnl_str = colored(f"${pnl:+,.2f}", Colors.GREEN if pnl >= 0 else Colors.RED)
        ret_str = colored(f"{ret:+.1f}%", Colors.GREEN if ret >= 0 else Colors.RED)
        dd_str  = colored(f"{dd:.1%}", Colors.RED)

        print(colored("\n  Performance:", Colors.PURPLE))
        print(f"   Trades: {summary['total_trades']}  |  "
              f"Win Rate: {colored(f'{win_rate:.1%}', wr_color)}  |  "
              f"Total P&L: {pnl_str}  |  Return: {ret_str}")
        print(f"   Max Drawdown: {dd_str}  |  "
              f"W/L: {summary['winning_trades']}/{summary['losing_trades']}")
