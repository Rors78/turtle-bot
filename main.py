#!/usr/bin/env python3
"""
Turtle Trading Bot - Main Entry Point
Automated Turtle Trading Strategy for Cryptocurrency Markets
"""

import sys
import time
import logging
from pathlib import Path
from datetime import datetime, timezone
from typing import Dict, List

# Local imports
from config import load_config
from core.turtle_engine import TurtleEngine
from risk.risk_manager import RiskManager
from risk.portfolio_manager import PortfolioManager
from utils.state import BotState
from utils.notifications import Notifier, Colors, colored
from utils.logging_config import setup_logging
from exchange.base import CCXTAdapter
from utils.multi_exchange import MultiExchangeFetcher


logger = logging.getLogger(__name__)


# === MARKET DATA FETCHING ===
def fetch_market_data(multi_fetcher: MultiExchangeFetcher, symbols: List[str], config) -> Dict:
    """
    Fetch OHLC and current prices for all symbols using multi-exchange fallback

    Args:
        multi_fetcher: MultiExchangeFetcher instance
        symbols: List of symbols to fetch
        config: Config instance

    Returns:
        Dict of symbol -> {'ohlc': [...], 'price': float, 'ticker': dict, 'source': str}
    """
    return multi_fetcher.fetch_market_data(
        symbols,
        timeframe=config.OHLC_TIMEFRAME,
        limit=config.OHLC_LIMIT,
        batch_size=config.BATCH_SIZE
    )


def calculate_atrs(market_data: Dict, turtle_engine: TurtleEngine) -> Dict:
    """
    Calculate ATR for all symbols

    Args:
        market_data: Market data dict
        turtle_engine: TurtleEngine instance

    Returns:
        Updated market_data with 'atr' field
    """
    for symbol, data in market_data.items():
        ohlc = data.get('ohlc', [])
        if ohlc:
            atr = turtle_engine.calculate_atr(ohlc)
            data['atr'] = atr

    return market_data


def get_coin_universe(config, quote_currency: str = 'USDT') -> List[str]:
    """
    Get list of coins to trade

    Args:
        config: Config instance
        quote_currency: Quote currency (default: USDT)

    Returns:
        List of trading symbols
    """
    import json as _json
    from pathlib import Path as _Path

    # Load blocked coins list
    blocked_coins_path = _Path(__file__).parent / 'blocked_coins.json'
    try:
        with open(blocked_coins_path, 'r') as f:
            blocked_data = _json.load(f)
        blocked_set = set(blocked_data.get('blocked_coins', []))
        logger.info(f"Loaded {len(blocked_set)} blocked coins from blocked_coins.json")
    except Exception as e:
        logger.warning(f"Could not load blocked_coins.json: {e} — proceeding with no block list")
        blocked_set = set()

    if config.SCAN_TOP_COINS:
        # Fetch top N coins by volume from Kraken
        logger.info(f"Fetching top {config.TOP_N_COINS} coins from Kraken by volume...")
        from utils.kraken_discovery import KrakenDiscovery
        top_pairs = KrakenDiscovery().get_top_pairs_by_volume(
            limit=config.TOP_N_COINS,
            min_volume_usd=100_000,
            blocked_coins=blocked_set,
        )
        symbols = [p['symbol'] for p in top_pairs]
        logger.info(f"Got {len(symbols)} quality pairs from Kraken (filtered by volume)")
        return symbols
    else:
        # Use fixed coin list
        fixed_keys = [c for c in config.FIXED_COINS if c.upper() not in blocked_set]
        filtered_count = len(config.FIXED_COINS) - len(fixed_keys)
        if filtered_count:
            logger.info(f"Blocked coins filter removed {filtered_count} coin(s) from fixed coins list")
        return [f"{coin}/{quote_currency}" for coin in fixed_keys]


# === MAIN BOT FUNCTION ===
def run_bot():
    """Main bot execution"""

    # Load configuration
    try:
        config = load_config()
    except ValueError as e:
        print(colored(f"\n!! Configuration Error:\n{e}\n", Colors.RED))
        sys.exit(1)

    # Setup logging
    setup_logging(config.LOG_FILE, log_format=config.LOG_FORMAT)

    # Print configuration summary
    config.print_summary()

    # Initialize components
    logger.info("Initializing components...")

    # Turtle Engine
    turtle_engine = TurtleEngine(config)

    # Risk Manager
    risk_manager = RiskManager(config)

    # Notifier
    notifier = Notifier(config)
    notifier.print_banner()

    # Exchange adapters
    exchanges = {}
    quote_currency = 'USDT'  # USDT-only trading

    try:
        # Kraken exchange (only exchange)
        creds = config.get_api_credentials()
        exchanges['kraken'] = CCXTAdapter(
            'kraken',
            api_key=creds['api_key'],
            api_secret=creds['api_secret'],
            paper_trading=config.PAPER_TRADING,
            slippage=config.PAPER_SLIPPAGE,
        )
        logger.info(f"Initialized Kraken exchange "
                    f"({'PAPER TRADING' if config.PAPER_TRADING else 'LIVE TRADING'})")

        # Kraken data fetcher (Kraken also used for coin discovery in get_coin_universe)
        multi_fetcher = MultiExchangeFetcher(
            primary_exchange=exchanges['kraken'],
            quote_currency=quote_currency
        )
        logger.info(f"Kraken fetcher initialized (quote: {quote_currency})")

    except Exception as e:
        print(colored(f"\n!! Exchange Initialization Error: {e}\n", Colors.RED))
        sys.exit(1)

    # Portfolio Manager
    portfolio_manager = PortfolioManager(
        config,
        turtle_engine,
        risk_manager,
        exchanges,
        notifier
    )

    # Load state
    logger.info(f"Loading state from {config.STATE_FILE}...")
    state = BotState.load(config.STATE_FILE, config.ACCOUNT_SIZE)

    # Initialize equity if not set
    if state.initial_equity == 0:
        state.initial_equity = config.ACCOUNT_SIZE
        state.current_equity = config.ACCOUNT_SIZE
        state.peak_equity = config.ACCOUNT_SIZE

    # Get coin universe (USDT pairs only)
    symbols = get_coin_universe(config, quote_currency=quote_currency)
    logger.info(f"Trading universe: {len(symbols)} symbols (quote: {quote_currency})")

    # Check if bot was previously emergency-stopped — require manual reset
    if state.emergency_stopped:
        print(colored("\n!! Bot is locked after an emergency stop.", Colors.RED))
        print(colored(f"   Triggered at: {state.emergency_stopped_at}", Colors.RED))
        print(colored("   Edit bot_state.json and set emergency_stopped to false to restart.", Colors.YELLOW))
        sys.exit(1)

    # Main loop
    print(colored(f"\n>> Turtle Bot started at {datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M UTC')}", Colors.CYAN))
    print(colored(f"$$ Initial Equity: ${state.initial_equity:,.2f}", Colors.WHITE))
    print(colored(f"  Press Ctrl+C to stop\n", Colors.GRAY))

    try:
        while True:
            state.iteration += 1

            print("\n" + colored("=" * 75, Colors.BLUE))
            print(colored(f"~  Update #{state.iteration}", Colors.BLUE) +
                  colored(f" | {datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M UTC')}", Colors.GRAY))
            print(colored("=" * 75, Colors.BLUE))

            # Fetch market data (with multi-exchange fallback)
            logger.info("Fetching market data...")
            market_data = fetch_market_data(multi_fetcher, symbols, config)

            if not market_data:
                logger.warning("No market data fetched, skipping cycle")
                time.sleep(config.CHECK_INTERVAL)
                continue

            # Calculate ATRs
            market_data = calculate_atrs(market_data, turtle_engine)

            logger.info(f"Fetched data for {len(market_data)} symbols")

            # Get current prices
            current_prices = {sym: data['price'] for sym, data in market_data.items()}

            # Get account balance
            account_balance = exchanges[config.PRIMARY_EXCHANGE].get_balance()
            if config.PAPER_TRADING:
                # Use realized cash balance for position sizing (not total equity)
                # This prevents double-counting unrealized P&L
                if state.cash_balance == 0:
                    # Initialize cash balance on first run
                    state.cash_balance = state.current_equity
                account_balance = state.cash_balance

            # === PRIORITY 0: CHECK EMERGENCY STOP (HIGHEST PRIORITY) ===
            # Check emergency stop BEFORE any trading decisions
            if risk_manager.check_emergency_stop(state.current_equity, state.initial_equity):
                print(colored("\n!! EMERGENCY STOP TRIGGERED!", Colors.RED))
                print(colored(f"Drawdown: {risk_manager.emergency_stop_loss * 100:.1f}%", Colors.RED))
                print(colored("Closing all positions...\n", Colors.YELLOW))

                # Close all positions
                for symbol in list(state.active_positions.keys()):
                    portfolio_manager.execute_exit(
                        symbol,
                        current_prices.get(symbol, 0),
                        'EMERGENCY_STOP',
                        state
                    )

                # Lock bot to prevent restart without manual reset
                state.emergency_stopped = True
                state.emergency_stopped_at = datetime.now(timezone.utc).isoformat()

                # Save state and stop
                state.save(config.STATE_FILE)
                logger.warning("Emergency stop triggered - exiting")
                break

            # === PRIORITY 1: CHECK STOPS ===
            logger.info("Checking stops...")
            stop_hits = portfolio_manager.scan_for_stops(market_data, state.active_positions)

            for symbol in stop_hits:
                position = state.get_position(symbol)
                if position:
                    notifier.alert_stop_hit(
                        symbol,
                        current_prices[symbol],
                        position.stop_price,
                        position.get_market_value(current_prices[symbol])
                    )

                    # Execute exit
                    portfolio_manager.execute_exit(
                        symbol,
                        current_prices[symbol],
                        'STOP_HIT',
                        state
                    )

            # === PRIORITY 1.5: UPDATE TRAILING STOPS ===
            # Run after stop checks so a newly-moved trailing stop is
            # evaluated on the *next* cycle (not the same cycle it moved).
            portfolio_manager.scan_trailing_stops(market_data, state.active_positions)

            # === PRIORITY 2: CHECK EXIT SIGNALS ===
            logger.info("Checking exit signals...")
            exit_symbols = portfolio_manager.scan_for_exits(market_data, state.active_positions)

            for symbol in exit_symbols:
                # Execute exit
                portfolio_manager.execute_exit(
                    symbol,
                    current_prices[symbol],
                    'EXIT_SIGNAL',
                    state
                )

            # === PRIORITY 3: CHECK PYRAMID OPPORTUNITIES ===
            logger.info("Checking pyramid opportunities...")
            pyramid_ops = portfolio_manager.scan_for_pyramids(
                market_data,
                state.active_positions,
                account_balance
            )

            for pyramid in pyramid_ops:
                # Execute pyramid
                portfolio_manager.execute_pyramid(
                    pyramid['symbol'],
                    pyramid['quantity'],
                    pyramid['price'],
                    state
                )

            # === PRIORITY 4: CHECK ENTRY SIGNALS (LOWEST PRIORITY) ===
            # Skip entry signals if bot is paused
            if state.is_paused:
                logger.info("Bot is paused - skipping entry signals")
                print(colored(f"\n||  Bot PAUSED: {state.pause_reason}", Colors.YELLOW))
                print(colored(f"   Paused since: {state.paused_at.strftime('%Y-%m-%d %H:%M UTC') if state.paused_at else 'Unknown'}", Colors.GRAY))
                print(colored("   Still managing existing positions (stops, exits, pyramids)", Colors.GRAY))
            else:
                logger.info("Checking entry signals...")
                entry_signals = portfolio_manager.scan_for_entries(
                    market_data,
                    state.active_positions,
                    account_balance
                )

                for signal in entry_signals:
                    # Execute entry
                    portfolio_manager.execute_entry(
                        signal['symbol'],
                        signal['system'],
                        config.PRIMARY_EXCHANGE,
                        signal['quantity'],
                        signal['price'],
                        signal['atr'],
                        state
                    )

            # Update equity
            total_pnl = sum(
                pos.calculate_pnl(current_prices.get(pos.symbol, 0))
                for pos in state.active_positions.values()
            )
            state.update_equity(account_balance + total_pnl)

            # Display portfolio
            if state.active_positions:
                notifier.print_portfolio_summary(state, current_prices)
            else:
                print(colored("\n>> No active positions", Colors.GRAY))

            # Display performance
            if state.total_trades > 0:
                notifier.print_performance(state)

            # Save state
            state.save(config.STATE_FILE)
            logger.info(f"State saved to {config.STATE_FILE}")

            # Sleep until next check
            if state.iteration > 0:
                print(colored(f"\nzz Next update in {config.CHECK_INTERVAL // 60} minutes...", Colors.GRAY))
                time.sleep(config.CHECK_INTERVAL)

    except KeyboardInterrupt:
        print("\n\n" + colored("=" * 75, Colors.PURPLE))
        print(colored("!! Stopping Turtle Bot...", Colors.YELLOW))

        # Save final state
        state.save(config.STATE_FILE)
        print(colored(f">> State saved to {config.STATE_FILE}", Colors.GREEN))

        # Display final summary
        if state.active_positions:
            print(colored(f"\n>> Final Portfolio ({len(state.active_positions)} positions):", Colors.PURPLE))
            for symbol, position in state.active_positions.items():
                print(f"  {colored(symbol, Colors.WHITE)}: {position.unit_count} units, "
                      f"Avg Entry: ${position.avg_entry_price:.2f}, Stop: ${position.stop_price:.2f}")

        if state.total_trades > 0:
            notifier.print_performance(state)

        print(colored("\n" + "=" * 75, Colors.PURPLE))
        print(colored(" Turtle Bot stopped. Trade by the Turtle rules!\n", Colors.CYAN))

    except Exception as e:
        logger.error(f"Unexpected error: {e}", exc_info=True)
        notifier.alert_error("Critical error in main loop", e)

        # Save state on error
        try:
            state.save(config.STATE_FILE)
            print(colored(f"\n>> State saved despite error", Colors.YELLOW))
        except Exception:
            pass

        sys.exit(1)


if __name__ == "__main__":
    run_bot()
