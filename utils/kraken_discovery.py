"""
Kraken Coin Discovery
Discovers tradable USDT pairs from Kraken's public REST API.
Replaces CoinGecko — all data now comes from a single source.
"""

import urllib.request
import urllib.error
import json
import logging
from typing import List, Dict

logger = logging.getLogger(__name__)

KRAKEN_API = "https://api.kraken.com/0/public"


class KrakenDiscovery:
    """
    Discovers top trading pairs on Kraken by 24h volume.
    Uses only Kraken's public REST API — no API key needed.
    """

    def _get(self, endpoint: str) -> dict:
        """Make a GET request to Kraken public API."""
        url = f"{KRAKEN_API}/{endpoint}"
        req = urllib.request.Request(url, headers={'User-Agent': 'TurtleBot/8.5'})
        try:
            with urllib.request.urlopen(req, timeout=15) as resp:
                data = json.loads(resp.read().decode('utf-8'))
                if data.get('error') and len(data['error']) > 0:
                    logger.warning(f"Kraken API error: {data['error']}")
                return data.get('result', {})
        except Exception as e:
            logger.error(f"Kraken API request failed: {e}")
            return {}

    def get_usdt_pairs(self) -> List[str]:
        """
        Get all USDT trading pairs available on Kraken.
        Returns list of pair names like ['BTC/USDT', 'ETH/USDT', ...].
        """
        result = self._get("AssetPairs")
        if not result:
            return []

        usdt_pairs = []
        for pair_name, pair_info in result.items():
            # Kraken returns both regular and .d (dark pool) pairs
            # Filter to USDT quote pairs only, skip dark pool
            quote = pair_info.get('quote', '')
            wsname = pair_info.get('wsname', '')
            if wsname and wsname.endswith('/USDT') and '.d' not in pair_name:
                usdt_pairs.append(wsname)

        logger.info(f"Found {len(usdt_pairs)} USDT pairs on Kraken")
        return usdt_pairs

    def get_top_pairs_by_volume(
        self,
        limit: int = 50,
        min_volume_usd: float = 100_000,
        blocked_coins: set = None,
    ) -> List[Dict]:
        """
        Get top USDT pairs ranked by 24h volume.

        Args:
            limit: Max number of pairs to return
            min_volume_usd: Minimum 24h volume in USD
            blocked_coins: Set of base symbols to exclude (e.g. {'AMP', 'BSV'})

        Returns:
            List of dicts: [{'symbol': 'BTC/USDT', 'base': 'BTC', 'volume_24h': 123456.0, 'price': 84000.0}, ...]
        """
        if blocked_coins is None:
            blocked_coins = set()

        # Get all USDT pairs
        pairs = self.get_usdt_pairs()
        if not pairs:
            logger.warning("No USDT pairs found on Kraken")
            return []

        # Fetch ticker data for all pairs to get volume
        # Kraken accepts comma-separated pair list
        # But the ticker endpoint works better with Kraken's internal names
        # So we'll fetch all tickers and filter
        result = self._get("Ticker")
        if not result:
            logger.warning("Could not fetch Kraken ticker data")
            return []

        # Build volume-ranked list
        pair_data = []
        for pair_wsname in pairs:
            base = pair_wsname.split('/')[0]

            # Apply blocked coins filter
            if base.upper() in blocked_coins:
                continue

            # Find matching ticker data
            # Kraken ticker keys use internal names (e.g. XXBTZUSD, XETHZUSD)
            # We need to match by iterating and checking
            ticker = None
            for ticker_key, ticker_val in result.items():
                # Normalize: remove X prefix and Z prefix Kraken uses
                if pair_wsname.replace('/', '') in ticker_key or \
                   pair_wsname.replace('/', '').replace('BTC', 'XBT') in ticker_key:
                    ticker = ticker_val
                    break

            if not ticker:
                # Try direct lookup with common Kraken naming
                for ticker_key, ticker_val in result.items():
                    if base in ticker_key and 'USDT' in ticker_key:
                        ticker = ticker_val
                        break

            if not ticker:
                continue

            try:
                # Kraken ticker format: v = [today_volume, 24h_volume]
                volume_24h = float(ticker['v'][1]) if 'v' in ticker else 0
                price = float(ticker['c'][0]) if 'c' in ticker else 0  # c = last trade [price, lot]
                volume_usd = volume_24h * price

                if volume_usd < min_volume_usd:
                    continue

                pair_data.append({
                    'symbol': pair_wsname,
                    'base': base,
                    'volume_24h': volume_usd,
                    'price': price,
                })
            except (ValueError, IndexError, KeyError) as e:
                logger.debug(f"Could not parse ticker for {pair_wsname}: {e}")
                continue

        # Sort by volume descending
        pair_data.sort(key=lambda x: x['volume_24h'], reverse=True)

        # Filter stablecoins and wrapped tokens
        EXCLUDE_BASES = {
            'USDT', 'USDC', 'DAI', 'BUSD', 'TUSD', 'USDP', 'FRAX',
            'USDD', 'GUSD', 'PAXG', 'WBTC', 'STETH', 'WETH',
            'CBETH', 'RETH', 'PYUSD', 'EURT',
        }
        pair_data = [p for p in pair_data if p['base'].upper() not in EXCLUDE_BASES]

        result_pairs = pair_data[:limit]
        logger.info(f"Kraken discovery: {len(result_pairs)} pairs by volume (min ${min_volume_usd:,.0f})")
        return result_pairs
