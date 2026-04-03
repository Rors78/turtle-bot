#!/usr/bin/env python3
"""
Backtest Runner
Fetches historical OHLC data from Kraken, runs the backtester,
prints a formatted results summary, and saves results to JSON.

Usage:
    python run_backtest.py [--days 365] [--account-size 130] [--top-coins 20]
"""

import argparse
import json
import logging
import sys
from datetime import datetime, timezone, timedelta
from pathlib import Path
from typing import Dict, List

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent))

from config import Config
from core.backtester import Backtester, BacktestResult
from exchange.base import CCXTAdapter
from utils.notifications import Colors, colored

logging.basicConfig(
    level=logging.WARNING,
    format='%(asctime)s %(levelname)s %(message)s',
    datefmt='%H:%M:%S',
)
logger = logging.getLogger(__name__)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description='Turtle Bot Backtester — replay historical data through the strategy'
    )
    parser.add_argument(
        '--days', type=int, default=180,
        help='Number of historical days to backtest (default: 180)'
    )
    parser.add_argument(
        '--account-size', type=float, default=None,
        help='Starting account size in USD (default: from config)'
    )
    parser.add_argument(
        '--top-coins', type=int, default=20,
        help='Number of top coins to include in backtest universe (default: 20)'
    )
    parser.add_argument(
        '--output', type=str, default='backtest_results.json',
        help='Output file path for results JSON (default: backtest_results.json)'
    )
    return parser.parse_args()


def fetch_historical_data(
    exchange: CCXTAdapter,
    symbols: List[str],
    days: int,
) -> Dict[str, List[Dict]]:
    """
    Fetch OHLC data from Kraken for all symbols.

    Returns {symbol: [candle_dicts]} — same format the backtester expects.
    """
    # We need extra bars for ATR warm-up (ATR_PERIOD + SYSTEM_2_ENTRY = 20+55=75)
    limit = days + 80

    historical: Dict[str, List[Dict]] = {}
    total = len(symbols)

    print(colored(f"\nFetching OHLC data for {total} symbols ({limit} daily bars)...", Colors.CYAN))

    for i, symbol in enumerate(symbols, 1):
        try:
            candles = exchange.get_ohlc(symbol, timeframe='1d', limit=limit)
            if candles:
                historical[symbol] = candles
                if i % 5 == 0 or i == total:
                    print(colored(f"  [{i}/{total}] fetched {len(candles)} bars for {symbol}", Colors.GRAY))
        except Exception as e:
            logger.warning(f"Could not fetch {symbol}: {e}")

    print(colored(f"\nLoaded data for {len(historical)}/{total} symbols.", Colors.WHITE))
    return historical


def get_backtest_symbols(config: Config, top_n: int) -> List[str]:
    """Return list of symbols to backtest, up to top_n coins."""
    # Use the fixed coin list as default; CoinGecko optional
    fixed = [f"{base}/USDT" for base in config.FIXED_COINS.keys()]

    if config.SCAN_TOP_COINS:
        try:
            from utils.coingecko import CoinGeckoAPI
            cg = CoinGeckoAPI()
            top = cg.get_top_coins(limit=top_n, min_volume=1_000_000, min_market_cap=10_000_000)
            symbols = [f"{c['symbol']}/USDT" for c in top[:top_n]]
            print(colored(f"Using {len(symbols)} CoinGecko top coins for backtest.", Colors.GRAY))
            return symbols
        except Exception as e:
            logger.warning(f"CoinGecko unavailable ({e}), using fixed coin list.")

    return fixed[:top_n]


def print_results(result: BacktestResult, days: int, account_size: float) -> None:
    """Pretty-print the BacktestResult to the console."""
    print(colored("\n" + "=" * 70, Colors.CYAN))
    print(colored("  BACKTEST RESULTS", Colors.CYAN))
    print(colored("=" * 70, Colors.CYAN))

    ret_color = Colors.GREEN if result.total_return >= 0 else Colors.RED
    pnl_color = Colors.GREEN if result.total_pnl >= 0 else Colors.RED

    print(f"\n  Period:      {days} days")
    print(f"  Start equity: ${account_size:,.2f}")
    print(
        f"  Total Return: {colored(f'{result.total_return:+.2f}%', ret_color)}"
        f"  |  Total P&L: {colored(f'${result.total_pnl:+,.2f}', pnl_color)}"
    )

    print(colored("\n  --- Trade Statistics ---", Colors.PURPLE))
    print(f"  Trades:      {result.total_trades}  "
          f"(W: {result.winning_trades} / L: {result.losing_trades})")
    wr_color = Colors.GREEN if result.win_rate >= 0.5 else Colors.YELLOW
    print(f"  Win Rate:    {colored(f'{result.win_rate:.1%}', wr_color)}")
    print(f"  Avg Win:     ${result.avg_win:+,.2f}")
    print(f"  Avg Loss:    ${result.avg_loss:+,.2f}")
    print(f"  Largest Win: ${result.largest_win:+,.2f}")
    print(f"  Largest Loss:${result.largest_loss:+,.2f}")
    print(f"  Avg Hold:    {result.avg_holding_days:.1f} days")

    print(colored("\n  --- Risk / Ratio Metrics ---", Colors.PURPLE))
    dd_color = Colors.RED if result.max_drawdown > 0.15 else Colors.YELLOW
    print(f"  Max Drawdown:  {colored(f'{result.max_drawdown:.1%}', dd_color)}")

    pf_color = Colors.GREEN if result.profit_factor >= 1.5 else (
        Colors.YELLOW if result.profit_factor >= 1.0 else Colors.RED
    )
    pf_str = f"{result.profit_factor:.2f}" if result.profit_factor != float('inf') else "inf"
    print(f"  Profit Factor: {colored(pf_str, pf_color)}")
    print(f"  Sharpe Ratio:  {result.sharpe_ratio:.2f}")
    print(f"  Sortino Ratio: {result.sortino_ratio:.2f}")
    print(f"  Calmar Ratio:  {result.calmar_ratio:.2f}")

    if result.monthly_returns:
        print(colored("\n  --- Monthly Returns ---", Colors.PURPLE))
        for month, ret in sorted(result.monthly_returns.items()):
            m_color = Colors.GREEN if ret >= 0 else Colors.RED
            print(f"  {month}:  {colored(f'{ret:+.2f}%', m_color)}")

    print(colored("\n" + "=" * 70, Colors.CYAN))


def save_results(result: BacktestResult, output_path: str) -> None:
    """Save equity curve and trade list to JSON."""
    # profit_factor may be float('inf') — replace for JSON serialisation
    pf = result.profit_factor
    if pf == float('inf'):
        pf = None

    data = {
        'summary': {
            'total_return_pct': result.total_return,
            'total_pnl': result.total_pnl,
            'total_trades': result.total_trades,
            'winning_trades': result.winning_trades,
            'losing_trades': result.losing_trades,
            'win_rate': result.win_rate,
            'max_drawdown': result.max_drawdown,
            'sharpe_ratio': result.sharpe_ratio,
            'sortino_ratio': result.sortino_ratio,
            'calmar_ratio': result.calmar_ratio,
            'profit_factor': pf,
            'avg_win': result.avg_win,
            'avg_loss': result.avg_loss,
            'largest_win': result.largest_win,
            'largest_loss': result.largest_loss,
            'avg_holding_days': result.avg_holding_days,
        },
        'monthly_returns': result.monthly_returns,
        'equity_curve': result.equity_curve,
        'trades': result.trades,
        'generated_at': datetime.now(timezone.utc).isoformat(),
    }

    with open(output_path, 'w') as f:
        json.dump(data, f, indent=2)

    print(colored(f"\n  Results saved to: {output_path}", Colors.GREEN))


def main() -> None:
    args = parse_args()

    # Load config
    try:
        config = Config()
    except Exception as e:
        print(colored(f"Config error: {e}", Colors.RED))
        sys.exit(1)

    # Override account size if specified
    if args.account_size:
        config.ACCOUNT_SIZE = args.account_size

    print(colored(f"\nTurtle Bot Backtester", Colors.CYAN))
    print(colored(f"Account: ${config.ACCOUNT_SIZE:,.2f}  |  Days: {args.days}  |  Coins: {args.top_coins}", Colors.GRAY))

    # Initialise exchange (paper-only for data fetching)
    try:
        exchange = CCXTAdapter(
            exchange_name='kraken',
            api_key=config.KRAKEN_API_KEY,
            api_secret=config.KRAKEN_API_SECRET,
            paper_trading=True,
            slippage=config.PAPER_SLIPPAGE,
        )
    except Exception as e:
        print(colored(f"Exchange init error: {e}", Colors.RED))
        sys.exit(1)

    # Get symbols
    symbols = get_backtest_symbols(config, args.top_coins)

    # Calculate date range
    end_date = datetime.now(timezone.utc)
    start_date = end_date - timedelta(days=args.days)
    start_str = start_date.strftime('%Y-%m-%d')
    end_str = end_date.strftime('%Y-%m-%d')

    print(colored(f"\nDate range: {start_str} → {end_str}", Colors.GRAY))

    # Fetch data
    historical_data = fetch_historical_data(exchange, symbols, args.days)

    if not historical_data:
        print(colored("No historical data fetched. Exiting.", Colors.RED))
        sys.exit(1)

    # Run backtest
    print(colored("\nRunning backtest...", Colors.CYAN))
    backtester = Backtester(config)
    result = backtester.run(historical_data, start_date=start_str, end_date=end_str)

    # Print results
    print_results(result, args.days, config.ACCOUNT_SIZE)

    # Save results
    save_results(result, args.output)


if __name__ == '__main__':
    main()
