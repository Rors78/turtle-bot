"""
Retry decorator with exponential backoff for transient network/exchange errors.
"""

import time
import logging
import functools
from typing import Tuple, Type

logger = logging.getLogger(__name__)

# Exceptions that are worth retrying (transient)
_DEFAULT_RETRYABLE: Tuple[Type[BaseException], ...] = (
    ConnectionError,
)

# Exceptions that must NOT be retried (permanent failures)
_NEVER_RETRY: Tuple[Type[BaseException], ...] = ()


def _build_exception_tuples():
    """
    Build retryable / never-retry exception tuples at call time so that
    ccxt can be imported lazily (it may not be installed in all envs).
    """
    retryable = list(_DEFAULT_RETRYABLE)
    never_retry = list(_NEVER_RETRY)

    try:
        import ccxt
        retryable += [
            ccxt.NetworkError,
            ccxt.ExchangeNotAvailable,
            ccxt.RequestTimeout,
        ]
        never_retry += [
            ccxt.AuthenticationError,
            ccxt.InsufficientFunds,
            ccxt.InvalidOrder,
        ]
    except ImportError:
        pass

    return tuple(retryable), tuple(never_retry)


def retry(max_attempts: int = 3, base_delay: float = 1.0):
    """
    Decorator factory that retries a function on transient errors.

    Retries on: ccxt.NetworkError, ccxt.ExchangeNotAvailable,
                ccxt.RequestTimeout, ConnectionError
    Never retries: ccxt.AuthenticationError, ccxt.InsufficientFunds,
                   ccxt.InvalidOrder

    Uses exponential backoff: base_delay * 2^(attempt - 1)
    (e.g. 1s, 2s, 4s for max_attempts=3, base_delay=1.0)

    Args:
        max_attempts: Total number of attempts (including the first)
        base_delay:   Delay before the second attempt in seconds
    """
    def decorator(func):
        @functools.wraps(func)
        def wrapper(*args, **kwargs):
            retryable, never_retry = _build_exception_tuples()

            last_exc: BaseException | None = None
            for attempt in range(1, max_attempts + 1):
                try:
                    return func(*args, **kwargs)
                except never_retry as exc:
                    # Permanent failure — do not retry
                    raise
                except retryable as exc:
                    last_exc = exc
                    if attempt == max_attempts:
                        break
                    delay = base_delay * (2 ** (attempt - 1))
                    logger.warning(
                        f"Retryable error in {func.__qualname__} "
                        f"(attempt {attempt}/{max_attempts}): {exc!r} — "
                        f"retrying in {delay:.1f}s"
                    )
                    time.sleep(delay)
                except Exception:
                    # Any other exception is re-raised immediately
                    raise

            logger.error(
                f"{func.__qualname__} failed after {max_attempts} attempts: {last_exc!r}"
            )
            raise last_exc  # type: ignore[misc]

        return wrapper
    return decorator


def retry_urllib(max_attempts: int = 3, base_delay: float = 1.0):
    """
    Variant of @retry for urllib-based callers (e.g. KrakenDiscovery._get).

    Retries on: urllib.error.URLError, TimeoutError
    Does NOT retry HTTP 429 — callers should handle rate-limit responses themselves.
    """
    import urllib.error

    def decorator(func):
        @functools.wraps(func)
        def wrapper(*args, **kwargs):
            last_exc: BaseException | None = None
            for attempt in range(1, max_attempts + 1):
                try:
                    return func(*args, **kwargs)
                except urllib.error.HTTPError as exc:
                    # Let HTTP errors (including 429) propagate unchanged —
                    # the caller decides what to do with them.
                    raise
                except (urllib.error.URLError, TimeoutError) as exc:
                    last_exc = exc
                    if attempt == max_attempts:
                        break
                    delay = base_delay * (2 ** (attempt - 1))
                    logger.warning(
                        f"Retryable network error in {func.__qualname__} "
                        f"(attempt {attempt}/{max_attempts}): {exc!r} — "
                        f"retrying in {delay:.1f}s"
                    )
                    time.sleep(delay)
                except Exception:
                    raise

            logger.error(
                f"{func.__qualname__} failed after {max_attempts} attempts: {last_exc!r}"
            )
            raise last_exc  # type: ignore[misc]

        return wrapper
    return decorator
