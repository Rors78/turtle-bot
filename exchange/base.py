"""
Exchange Adapter Base Class
Abstract interface for exchange integration
"""

from abc import ABC, abstractmethod
from typing import List, Dict, Optional, Tuple
import logging

from utils.retry import retry

logger = logging.getLogger(__name__)


class ExchangeAdapter(ABC):
    """
    Abstract base class for exchange integration

    Provides unified interface for:
    - Fetching OHLC data (for ATR calculation)
    - Getting current prices
    - Executing orders
    - Checking balances
    - Validating order constraints
    """

    def __init__(self, exchange_name: str, paper_trading: bool = True):
        """
        Initialize exchange adapter

        Args:
            exchange_name: Name of exchange ('kraken', 'binance_us', etc.)
            paper_trading: If True, simulate trades without real execution
        """
        self.exchange_name = exchange_name
        self.paper_trading = paper_trading
        self.logger = logger

    @abstractmethod
    def get_balance(self, currency: str = 'USD') -> float:
        """
        Get account balance for specified currency

        Args:
            currency: Currency code (default 'USD')

        Returns:
            Available balance
        """
        pass

    @abstractmethod
    def get_ohlc(self, symbol: str, timeframe: str = '1d', limit: int = 100) -> List[Dict]:
        """
        Get OHLC candlestick data

        Args:
            symbol: Trading pair (e.g., 'BTC/USD')
            timeframe: Candle period ('1h', '4h', '1d', etc.)
            limit: Number of candles to fetch

        Returns:
            List of OHLC candles
            [{'timestamp': int, 'open': float, 'high': float,
              'low': float, 'close': float, 'volume': float}, ...]
        """
        pass

    @abstractmethod
    def get_ticker(self, symbol: str) -> Dict:
        """
        Get current market ticker

        Args:
            symbol: Trading pair (e.g., 'BTC/USD')

        Returns:
            Ticker data {'symbol': str, 'last': float, 'bid': float,
                        'ask': float, 'volume': float}
        """
        pass

    @abstractmethod
    def create_market_order(
        self,
        symbol: str,
        side: str,
        quantity: float
    ) -> Dict:
        """
        Create and execute market order

        Args:
            symbol: Trading pair (e.g., 'BTC/USD')
            side: 'buy' or 'sell'
            quantity: Amount to trade

        Returns:
            Order result {'id': str, 'symbol': str, 'side': str,
                         'quantity': float, 'filled': float, 'price': float,
                         'status': str, 'timestamp': int}
        """
        pass

    @abstractmethod
    def get_order_status(self, order_id: str, symbol: str) -> Dict:
        """
        Check order fill status

        Args:
            order_id: Exchange order ID
            symbol: Trading pair

        Returns:
            Order status {'id': str, 'status': str, 'filled': float,
                         'remaining': float, 'price': float}
        """
        pass

    @abstractmethod
    def get_trading_limits(self, symbol: str) -> Dict:
        """
        Get exchange trading limits for symbol

        Args:
            symbol: Trading pair (e.g., 'BTC/USD')

        Returns:
            Limits dict {'min_order': float, 'max_order': float,
                        'min_notional': float, 'price_precision': int,
                        'quantity_precision': int}
        """
        pass

    def validate_order(
        self,
        symbol: str,
        side: str,
        quantity: float
    ) -> Tuple[bool, str]:
        """
        Validate order meets exchange requirements

        Args:
            symbol: Trading pair
            side: 'buy' or 'sell'
            quantity: Order quantity

        Returns:
            Tuple of (valid: bool, error_message: str)
        """
        try:
            limits = self.get_trading_limits(symbol)

            # Check minimum order size
            if quantity < limits.get('min_order', 0):
                return (False, f"Quantity {quantity} below min {limits['min_order']}")

            # Check maximum order size
            if quantity > limits.get('max_order', float('inf')):
                return (False, f"Quantity {quantity} above max {limits['max_order']}")

            # Check minimum notional value
            ticker = self.get_ticker(symbol)
            notional = quantity * ticker.get('last', 0)

            if notional < limits.get('min_notional', 0):
                return (False, f"Notional ${notional:.2f} below min ${limits['min_notional']}")

            return (True, "Order valid")

        except Exception as e:
            return (False, f"Validation error: {str(e)}")

    def get_available_symbols(self) -> List[str]:
        """
        Get list of tradeable symbols on this exchange

        Returns:
            List of symbol strings (e.g., ['BTC/USD', 'ETH/USD', ...])
        """
        # Default implementation - subclasses should override
        return []

    def normalize_symbol(self, symbol: str) -> str:
        """
        Normalize symbol to exchange format

        Args:
            symbol: Symbol in various formats (BTC, btc, BTC/USD, etc.)

        Returns:
            Exchange-specific format
        """
        # Default implementation - subclasses may override
        symbol = symbol.upper()
        if '/' not in symbol:
            symbol = f"{symbol}/USD"
        return symbol

    def _kraken_symbol_map(self, base: str) -> str:
        """
        Map standard symbol to Kraken format

        Kraken uses X prefix for many coins (XBT, XETH, etc.)
        """
        KRAKEN_MAP = {
            'BTC': 'XBT',
            'DOGE': 'XDG',
            # Most other symbols work as-is on Kraken
        }
        return KRAKEN_MAP.get(base, base)

    def __repr__(self) -> str:
        """String representation"""
        mode = "PAPER" if self.paper_trading else "LIVE"
        return f"<{self.__class__.__name__}({self.exchange_name}, {mode})>"


class CCXTAdapter(ExchangeAdapter):
    """
    CCXT-based exchange adapter

    Supports 100+ exchanges through CCXT library
    """

    def __init__(
        self,
        exchange_name: str = 'kraken',
        api_key: Optional[str] = None,
        api_secret: Optional[str] = None,
        paper_trading: bool = True,
        slippage: float = 0.001,
    ):
        """
        Initialize CCXT adapter (Kraken only)

        Args:
            exchange_name: Must be 'kraken' — any other value raises ValueError
            api_key: Kraken API key (optional for public data)
            api_secret: Kraken API secret (optional for public data)
            paper_trading: If True, don't execute real trades
            slippage: Fractional slippage applied to paper fills (default 0.001 = 0.1%)
        """
        if exchange_name.lower() != 'kraken':
            raise ValueError(f"Only Kraken is supported, got: {exchange_name}")

        super().__init__('kraken', paper_trading)

        # Slippage applied to paper-trade fills
        self.slippage = slippage

        # Import ccxt here to avoid dependency if not using
        try:
            import ccxt
        except ImportError:
            raise ImportError("CCXT library not installed. Run: pip install ccxt")

        self.exchange = ccxt.kraken({
            'enableRateLimit': True,
            'rateLimit': 3000,   # Kraken: conservative 3s between requests
            'timeout': 30000,
        })

        # Set API credentials if provided and not paper trading
        if not paper_trading and api_key and api_secret:
            self.exchange.apiKey = api_key
            self.exchange.secret = api_secret

        # Load markets
        try:
            self.exchange.load_markets()
            self.logger.info(f"Loaded {len(self.exchange.markets)} markets from {exchange_name}")
        except Exception as e:
            self.logger.warning(f"Could not load markets: {e}")

    @retry()
    def get_balance(self, currency: str = 'USD') -> float:
        """Get account balance"""
        if self.paper_trading:
            # Paper mode does not use this return value for position sizing.
            # The caller (main.py) overrides account_balance with state.cash_balance
            # immediately after this call, so returning 0.0 here is intentional.
            return 0.0

        try:
            balance = self.exchange.fetch_balance()
            return balance.get('free', {}).get(currency, 0.0)
        except Exception as e:
            self.logger.error(f"Error fetching balance: {e}")
            return 0.0

    @retry()
    def get_ohlc(self, symbol: str, timeframe: str = '1d', limit: int = 100) -> List[Dict]:
        """Get OHLC data"""
        try:
            symbol = self.normalize_symbol(symbol)
            ohlcv = self.exchange.fetch_ohlcv(symbol, timeframe, limit=limit)

            # Convert to our format
            candles = []
            for candle in ohlcv:
                candles.append({
                    'timestamp': candle[0],
                    'open': candle[1],
                    'high': candle[2],
                    'low': candle[3],
                    'close': candle[4],
                    'volume': candle[5]
                })

            return candles

        except Exception as e:
            self.logger.debug(f"No OHLC for {symbol}: {e}")  # DEBUG not ERROR - expected for unavailable pairs
            return []

    @retry()
    def get_ticker(self, symbol: str) -> Dict:
        """Get current ticker"""
        try:
            symbol = self.normalize_symbol(symbol)
            ticker = self.exchange.fetch_ticker(symbol)

            return {
                'symbol': symbol,
                'last': ticker.get('last', 0),
                'bid': ticker.get('bid', 0),
                'ask': ticker.get('ask', 0),
                'volume': ticker.get('volume', 0)
            }

        except Exception as e:
            self.logger.debug(f"No ticker for {symbol}: {e}")  # DEBUG not ERROR - expected
            return {'symbol': symbol, 'last': 0, 'bid': 0, 'ask': 0, 'volume': 0}

    @retry()
    def create_market_order(self, symbol: str, side: str, quantity: float) -> Dict:
        """Create market order"""
        symbol = self.normalize_symbol(symbol)

        if self.paper_trading:
            # Simulate order execution with realistic slippage.
            # Buys fill at ask * (1 + slippage); sells fill at bid * (1 - slippage).
            ticker = self.get_ticker(symbol)
            if side == 'buy':
                fill_price = ticker['ask'] * (1 + self.slippage)
            else:
                fill_price = ticker['bid'] * (1 - self.slippage)

            return {
                'id': f"paper_{symbol}_{side}_{quantity}",
                'symbol': symbol,
                'side': side,
                'quantity': quantity,
                'filled': quantity,
                'price': fill_price,
                'status': 'closed',
                'timestamp': self.exchange.milliseconds()
            }

        # Real order execution
        try:
            order = self.exchange.create_market_order(symbol, side, quantity)

            return {
                'id': order['id'],
                'symbol': order['symbol'],
                'side': order['side'],
                'quantity': order['amount'],
                'filled': order.get('filled', 0),
                'price': order.get('average', 0),
                'status': order.get('status', 'unknown'),
                'timestamp': order.get('timestamp', 0)
            }

        except Exception as e:
            self.logger.error(f"Error creating order: {e}")
            raise

    @retry()
    def get_order_status(self, order_id: str, symbol: str) -> Dict:
        """Get order status"""
        if self.paper_trading:
            # Paper orders are instantly filled
            return {
                'id': order_id,
                'status': 'closed',
                'filled': 0,
                'remaining': 0,
                'price': 0
            }

        try:
            symbol = self.normalize_symbol(symbol)
            order = self.exchange.fetch_order(order_id, symbol)

            return {
                'id': order['id'],
                'status': order.get('status', 'unknown'),
                'filled': order.get('filled', 0),
                'remaining': order.get('remaining', 0),
                'price': order.get('average', 0)
            }

        except Exception as e:
            self.logger.error(f"Error fetching order status: {e}")
            return {'id': order_id, 'status': 'error', 'filled': 0, 'remaining': 0, 'price': 0}

    def get_trading_limits(self, symbol: str) -> Dict:
        """Get trading limits"""
        try:
            symbol = self.normalize_symbol(symbol)
            market = self.exchange.market(symbol)

            return {
                'min_order': market['limits']['amount']['min'] or 0,
                'max_order': market['limits']['amount']['max'] or float('inf'),
                'min_notional': market['limits']['cost']['min'] or 0,
                'price_precision': market['precision']['price'] or 2,
                'quantity_precision': market['precision']['amount'] or 8
            }

        except Exception as e:
            self.logger.warning(f"Could not get limits for {symbol}: {e}")
            return {
                'min_order': 0,
                'max_order': float('inf'),
                'min_notional': 0,
                'price_precision': 2,
                'quantity_precision': 8
            }

    def get_available_symbols(self) -> List[str]:
        """Get available symbols"""
        return list(self.exchange.markets.keys()) if self.exchange.markets else []

    def normalize_symbol(self, symbol: str) -> str:
        """
        Normalize symbol to exchange-specific format

        Handles Kraken's special naming (XBT instead of BTC, etc.)
        """
        symbol = symbol.upper()

        # Split into base/quote if present
        if '/' in symbol:
            base, quote = symbol.split('/')
        else:
            base = symbol
            quote = 'USDT'

        # CCXT already normalises Kraken's internal XBT -> BTC, so no remapping needed.
        return f"{base}/{quote}"
