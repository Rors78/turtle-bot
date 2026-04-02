"""
CoinGecko API Wrapper
Used ONLY for coin universe discovery (market cap ranking).
All price/OHLC data comes from Kraken via ccxt.
"""

import time
import logging
import urllib.request
import urllib.error
import json
from typing import List, Dict

logger = logging.getLogger(__name__)

COINGECKO_BASE = "https://api.coingecko.com/api/v3"
RATE_LIMIT_DELAY = 3.0  # CoinGecko free tier: ~20 req/min; 3s is safe


class CoinGeckoAPI:
    """
    Minimal CoinGecko client for coin discovery only.
    No API key required (free public endpoints).
    """

    def __init__(self):
        self._last_request = 0.0

    def _get(self, path: str, params: Dict = None) -> Dict:
        """Make a rate-limited GET request."""
        # Enforce rate limit
        elapsed = time.time() - self._last_request
        if elapsed < RATE_LIMIT_DELAY:
            time.sleep(RATE_LIMIT_DELAY - elapsed)

        url = f"{COINGECKO_BASE}{path}"
        if params:
            query = "&".join(f"{k}={v}" for k, v in params.items())
            url = f"{url}?{query}"

        req = urllib.request.Request(
            url,
            headers={'User-Agent': 'TurtleBot/1.0 (crypto trading bot)'}
        )

        try:
            with urllib.request.urlopen(req, timeout=15) as resp:
                self._last_request = time.time()
                return json.loads(resp.read().decode('utf-8'))
        except urllib.error.HTTPError as e:
            if e.code == 429:
                logger.warning("CoinGecko rate limit hit — waiting 60s")
                time.sleep(60)
                raise
            raise

    def get_top_coins(
        self,
        limit: int = 50,
        min_volume: float = 1_000_000,
        min_market_cap: float = 10_000_000
    ) -> List[Dict]:
        """
        Fetch top coins by market cap, filtered by volume and market cap.

        Returns list of dicts with 'symbol', 'name', 'market_cap', 'volume_24h'.
        Symbols are returned as uppercase base currency (e.g. 'BTC', 'ETH').
        Stablecoins and wrapped tokens are excluded automatically via the
        min_market_cap / min_volume filters plus a symbol blocklist.
        """
        STABLE_SYMBOLS = {
            'USDT', 'USDC', 'BUSD', 'DAI', 'TUSD', 'USDP', 'FRAX',
            'LUSD', 'USDD', 'GUSD', 'PAXG', 'WBTC', 'STETH', 'WETH',
            'CBETH', 'RETH', 'FRXETH', 'CRVUSD', 'SUSDS', 'AUSD',
        }

        try:
            data = self._get('/coins/markets', {
                'vs_currency': 'usd',
                'order': 'market_cap_desc',
                'per_page': min(limit * 2, 250),  # Fetch extra to account for filtering
                'page': 1,
                'sparkline': 'false',
            })
        except Exception as e:
            logger.error(f"CoinGecko fetch failed: {e}")
            return []

        results = []
        for coin in data:
            symbol = (coin.get('symbol') or '').upper()
            market_cap = coin.get('market_cap') or 0
            volume = coin.get('total_volume') or 0

            if symbol in STABLE_SYMBOLS:
                continue
            if market_cap < min_market_cap:
                continue
            if volume < min_volume:
                continue

            results.append({
                'symbol': symbol,
                'name': coin.get('name', ''),
                'market_cap': market_cap,
                'volume_24h': volume,
                'coingecko_id': coin.get('id', ''),
            })

            if len(results) >= limit:
                break

        logger.info(f"CoinGecko returned {len(results)} coins after filtering")
        return results
