"""
Market Regime Detection
Uses ADX (Average Directional Index) to classify market conditions.
"""

import logging
from typing import Any, Dict, List, Optional, Tuple

logger = logging.getLogger(__name__)


class RegimeDetector:
    """
    Detects market regime (trending vs ranging) using ADX.

    ADX > 25  → trending
    ADX < 20  → ranging
    20-25     → transitional

    Strength labels:
      ADX > 40 → strong
      25-40    → moderate
      < 25     → weak
    """

    def __init__(self, config: Any) -> None:
        self.config = config
        self.adx_period = getattr(config, 'REGIME_ADX_PERIOD', 14)
        self.min_adx = getattr(config, 'REGIME_MIN_ADX', 25.0)

    def calculate_adx(self, ohlc_data: List[Dict], period: int = 14) -> Optional[float]:
        """
        Calculate Average Directional Index (ADX) from OHLC data.

        Standard Wilder ADX:
          +DM = max(high - prev_high, 0) if > max(prev_low - low, 0) else 0
          -DM = max(prev_low - low,  0) if > max(high - prev_high, 0) else 0
          TR  = max(high-low, |high-prev_close|, |low-prev_close|)
          DX  = 100 * |+DI - -DI| / (+DI + -DI)
          ADX = smoothed average of DX over period

        Args:
            ohlc_data: List of OHLC dicts with 'high', 'low', 'close' keys.
            period: Smoothing period (default 14).

        Returns:
            ADX value (0-100) or None if insufficient data.
        """
        # Need at least 2*period + 1 candles for a reliable ADX
        if len(ohlc_data) < period + 1:
            return None

        plus_dm_list: List[float] = []
        minus_dm_list: List[float] = []
        tr_list: List[float] = []

        for i in range(1, len(ohlc_data)):
            curr = ohlc_data[i]
            prev = ohlc_data[i - 1]

            high = curr.get('high', 0)
            low = curr.get('low', 0)
            close = curr.get('close', 0)
            prev_high = prev.get('high', 0)
            prev_low = prev.get('low', 0)
            prev_close = prev.get('close', 0)

            # Skip invalid candles
            if any(x <= 0 for x in [high, low, close, prev_high, prev_low, prev_close]):
                continue

            # Directional movement
            up_move = high - prev_high
            down_move = prev_low - low

            plus_dm = up_move if (up_move > down_move and up_move > 0) else 0.0
            minus_dm = down_move if (down_move > up_move and down_move > 0) else 0.0

            # True Range
            tr = max(
                high - low,
                abs(high - prev_close),
                abs(low - prev_close),
            )

            plus_dm_list.append(plus_dm)
            minus_dm_list.append(minus_dm)
            tr_list.append(tr)

        if len(tr_list) < period:
            return None

        # Wilder smoothing: first value = sum of first `period` values
        # subsequent: smooth = prev_smooth - (prev_smooth / period) + current
        def _wilder_smooth(values: List[float], n: int) -> List[float]:
            if len(values) < n:
                return []
            smoothed = [sum(values[:n])]
            for val in values[n:]:
                smoothed.append(smoothed[-1] - smoothed[-1] / n + val)
            return smoothed

        smooth_tr = _wilder_smooth(tr_list, period)
        smooth_plus = _wilder_smooth(plus_dm_list, period)
        smooth_minus = _wilder_smooth(minus_dm_list, period)

        if not smooth_tr:
            return None

        # Calculate DX values
        dx_list: List[float] = []
        for s_tr, s_plus, s_minus in zip(smooth_tr, smooth_plus, smooth_minus):
            if s_tr <= 0:
                continue
            plus_di = 100.0 * s_plus / s_tr
            minus_di = 100.0 * s_minus / s_tr
            di_sum = plus_di + minus_di
            if di_sum == 0:
                dx_list.append(0.0)
            else:
                dx_list.append(100.0 * abs(plus_di - minus_di) / di_sum)

        if len(dx_list) < period:
            return None

        # ADX = Wilder smooth of DX
        adx_smooth = _wilder_smooth(dx_list, period)
        if not adx_smooth:
            return None

        return adx_smooth[-1]

    def detect_regime(self, ohlc_data: List[Dict]) -> Dict:
        """
        Classify the current market regime.

        Returns:
            {
              'regime':   'trending' | 'ranging' | 'unknown',
              'adx':      float | None,
              'strength': 'strong' | 'moderate' | 'weak' | 'unknown',
            }
        """
        adx = self.calculate_adx(ohlc_data, period=self.adx_period)

        if adx is None:
            return {'regime': 'unknown', 'adx': None, 'strength': 'unknown'}

        if adx > 25:
            regime = 'trending'
        elif adx < 20:
            regime = 'ranging'
        else:
            regime = 'transitional'

        if adx > 40:
            strength = 'strong'
        elif adx >= 25:
            strength = 'moderate'
        else:
            strength = 'weak'

        return {'regime': regime, 'adx': adx, 'strength': strength}

    def should_enter(self, ohlc_data: List[Dict]) -> Tuple[bool, str]:
        """
        Determine whether entries are permitted given current market regime.

        Returns:
            (True,  "ADX 32.5 — trending")
            (False, "ADX 15.2 — ranging, skip entry")
        """
        result = self.detect_regime(ohlc_data)
        adx = result['adx']

        if adx is None:
            return False, "ADX unknown — insufficient data, skip entry"

        adx_str = f"{adx:.1f}"

        if adx >= self.min_adx:
            return True, f"ADX {adx_str} — {result['regime']}"
        else:
            return False, f"ADX {adx_str} — {result['regime']}, skip entry"
