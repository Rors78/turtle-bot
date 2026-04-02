"""
Kraken Market Data Fetcher
Fetches all OHLC and price data exclusively from Kraken via ccxt.
Named MultiExchangeFetcher for import compatibility with main.py,
but Kraken is the only data source — no fallback chain.
"""

import time
import logging
from typing import Dict, List, Optional

logger = logging.getLogger(__name__)


class MultiExchangeFetcher:
    """
    Fetches OHLC and ticker data from Kraken only.

    CoinGecko is NOT used as a price source — only for coin discovery
    (handled separately in main.py via CoinGeckoAPI).

    If Kraken data fetch fails for a symbol, that symbol is skipped
    for the cycle. No price fallback — bad data is worse than no data.
    """

    def __init__(
        self,
        primary_exchange,           # CCXTAdapter instance (Kraken)
        quote_currency: str = 'USDT',
        secondary_exchange=None,    # Accepted but ignored — Kraken only
    ):
        self.exchange = primary_exchange
        self.quote_currency = quote_currency

    def fetch_market_data(
        self,
        symbols: List[str],
        timeframe: str = '1d',
        limit: int = 60,
        batch_size: int = 20,
    ) -> Dict:
        """
        Fetch OHLC + current price for each symbol from Kraken.

        Args:
            symbols: List of base symbols (e.g. ['BTC', 'ETH']) or
                     full pairs (e.g. ['BTC/USDT']). Both formats accepted.
            timeframe: OHLC timeframe ('1d', '4h', etc.)
            limit: Number of candles to fetch per symbol
            batch_size: How many symbols to process per batch (rate limit pacing)

        Returns:
            Dict[symbol -> {'ohlc': [...], 'price': float, 'source': 'kraken'}]
            Only includes symbols for which valid data was obtained.
        """
        # Normalise all symbols to full pair format
        pairs = []
        for sym in symbols:
            if '/' in sym:
                pairs.append(sym.upper())
            else:
                pairs.append(f"{sym.upper()}/{self.quote_currency}")

        # Filter to symbols actually available on Kraken
        available = set(self.exchange.get_available_symbols())
        valid_pairs = [p for p in pairs if p in available]

        if not valid_pairs:
            logger.warning("No requested symbols found on Kraken — check coin list")
            return {}

        skipped = len(pairs) - len(valid_pairs)
        if skipped:
            logger.debug(f"{skipped} symbols not available on Kraken, skipping")

        results = {}
        processed = 0

        for i in range(0, len(valid_pairs), batch_size):
            batch = valid_pairs[i:i + batch_size]

            for pair in batch:
                try:
                    ohlc = self.exchange.get_ohlc(pair, timeframe=timeframe, limit=limit)
                    ticker = self.exchange.get_ticker(pair)
                    price = ticker.get('last', 0)

                    if not ohlc or price <= 0:
                        logger.debug(f"No usable data for {pair}, skipping")
                        continue

                    results[pair] = {
                        'ohlc': ohlc,
                        'price': price,
                        'ticker': ticker,
                        'source': 'kraken',
                    }
                    processed += 1

                except Exception as e:
                    logger.warning(f"Failed to fetch {pair}: {e}")
                    continue

            # Pace between batches to respect Kraken rate limits
            if i + batch_size < len(valid_pairs):
                time.sleep(1.5)

        logger.info(f"Fetched data for {processed}/{len(valid_pairs)} symbols from Kraken")
        return results

    def get_current_price(self, symbol: str) -> Optional[float]:
        """Convenience method to fetch a single current price."""
        if '/' not in symbol:
            symbol = f"{symbol.upper()}/{self.quote_currency}"
        try:
            ticker = self.exchange.get_ticker(symbol)
            price = ticker.get('last', 0)
            return price if price > 0 else None
        except Exception as e:
            logger.warning(f"Could not fetch price for {symbol}: {e}")
            return None
