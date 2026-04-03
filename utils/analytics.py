"""
Analytics Module
Pure functions for computing trading performance metrics.
Used by both the backtester and live bot (via BotState.get_summary).
"""

import math
from typing import Dict, List, Optional, Tuple


def sharpe_ratio(returns: List[float], risk_free_rate: float = 0.0) -> float:
    """
    Annualised Sharpe ratio using daily returns.

    Formula: (mean(returns) - rf_daily) / std(returns) * sqrt(252)

    Args:
        returns: List of daily return fractions (e.g. 0.01 = 1%)
        risk_free_rate: Annual risk-free rate (e.g. 0.05 = 5%). Converted to daily internally.

    Returns:
        Annualised Sharpe ratio, or 0.0 if std is zero or insufficient data.
    """
    if len(returns) < 2:
        return 0.0

    rf_daily = risk_free_rate / 252.0
    mean_r = sum(returns) / len(returns)
    variance = sum((r - mean_r) ** 2 for r in returns) / (len(returns) - 1)
    std_r = math.sqrt(variance)

    if std_r == 0.0:
        return 0.0

    return (mean_r - rf_daily) / std_r * math.sqrt(252)


def sortino_ratio(returns: List[float], risk_free_rate: float = 0.0) -> float:
    """
    Annualised Sortino ratio — like Sharpe but uses only downside deviation.

    Formula: (mean(returns) - rf_daily) / downside_std * sqrt(252)
    Downside deviation uses only returns below the risk-free rate target.

    Args:
        returns: List of daily return fractions
        risk_free_rate: Annual risk-free rate

    Returns:
        Annualised Sortino ratio, or 0.0 if downside std is zero.
    """
    if len(returns) < 2:
        return 0.0

    rf_daily = risk_free_rate / 252.0
    mean_r = sum(returns) / len(returns)

    # Only negative deviations below the target
    downside_sq = [(min(r - rf_daily, 0.0)) ** 2 for r in returns]
    downside_variance = sum(downside_sq) / len(downside_sq)
    downside_std = math.sqrt(downside_variance)

    if downside_std == 0.0:
        return 0.0

    return (mean_r - rf_daily) / downside_std * math.sqrt(252)


def calmar_ratio(total_return: float, max_drawdown: float, years: float) -> float:
    """
    Calmar ratio: annualised return divided by max drawdown.

    Args:
        total_return: Total return as a fraction (e.g. 0.25 = 25%)
        max_drawdown: Max drawdown as a positive fraction (e.g. 0.15 = 15%)
        years: Duration of the period in years

    Returns:
        Calmar ratio, or 0.0 if inputs are invalid.
    """
    if years <= 0 or max_drawdown <= 0:
        return 0.0

    annualised_return = (1 + total_return) ** (1.0 / years) - 1
    return annualised_return / max_drawdown


def profit_factor(winning_pnls: List[float], losing_pnls: List[float]) -> float:
    """
    Profit factor: gross profit / gross loss.

    Args:
        winning_pnls: List of positive P&L values from winning trades
        losing_pnls: List of negative (or zero) P&L values from losing trades

    Returns:
        Profit factor. Returns float('inf') if there are no losses.
        Returns 0.0 if there are no wins.
    """
    gross_profit = sum(p for p in winning_pnls if p > 0)
    gross_loss = abs(sum(p for p in losing_pnls if p < 0))

    if gross_loss == 0:
        return float('inf') if gross_profit > 0 else 0.0

    return gross_profit / gross_loss


def max_drawdown(equity_curve: List[float]) -> Tuple[float, int, int]:
    """
    Calculate maximum peak-to-trough drawdown from an equity curve.

    Args:
        equity_curve: List of equity values (in order)

    Returns:
        Tuple of (max_drawdown_pct, peak_index, trough_index)
        max_drawdown_pct is a positive fraction (e.g. 0.20 = 20% drawdown)
    """
    if len(equity_curve) < 2:
        return (0.0, 0, 0)

    max_dd = 0.0
    peak_idx = 0
    trough_idx = 0
    current_peak = equity_curve[0]
    current_peak_idx = 0

    for i, equity in enumerate(equity_curve):
        if equity > current_peak:
            current_peak = equity
            current_peak_idx = i
        else:
            dd = (current_peak - equity) / current_peak if current_peak > 0 else 0.0
            if dd > max_dd:
                max_dd = dd
                peak_idx = current_peak_idx
                trough_idx = i

    return (max_dd, peak_idx, trough_idx)


def monthly_returns(equity_curve: List[Dict]) -> Dict[str, float]:
    """
    Calculate monthly returns from a daily equity curve.

    Args:
        equity_curve: List of dicts with 'date' (str, YYYY-MM-DD) and 'equity' (float)

    Returns:
        Dict mapping "YYYY-MM" to monthly return fraction (e.g. {"2024-01": 0.023})
    """
    if not equity_curve:
        return {}

    # Group equity snapshots by month
    monthly: Dict[str, List[float]] = {}
    for point in equity_curve:
        date_str = point.get('date', '')
        equity_val = point.get('equity', 0.0)
        if not date_str or len(date_str) < 7:
            continue
        month_key = date_str[:7]  # "YYYY-MM"
        if month_key not in monthly:
            monthly[month_key] = []
        monthly[month_key].append(equity_val)

    if not monthly:
        return {}

    # Build sorted month list
    sorted_months = sorted(monthly.keys())
    result: Dict[str, float] = {}

    # Find the equity at the start of each month (first snapshot in month)
    # and end of each month (last snapshot in month)
    # Return for month = (end / start) - 1
    prev_end: Optional[float] = None

    for month_key in sorted_months:
        values = monthly[month_key]
        start_eq = prev_end if prev_end is not None else values[0]
        end_eq = values[-1]

        if start_eq and start_eq > 0:
            result[month_key] = (end_eq / start_eq) - 1.0
        else:
            result[month_key] = 0.0

        prev_end = end_eq

    return result


def expectancy(avg_win: float, avg_loss: float, win_rate: float) -> float:
    """
    Trade expectancy: expected P&L per trade.

    Formula: (win_rate * avg_win) - ((1 - win_rate) * abs(avg_loss))

    Args:
        avg_win: Average winning trade P&L (positive)
        avg_loss: Average losing trade P&L (negative or positive — abs is taken)
        win_rate: Win rate as a fraction (e.g. 0.40 = 40%)

    Returns:
        Expectancy in same currency as avg_win / avg_loss
    """
    return (win_rate * avg_win) - ((1.0 - win_rate) * abs(avg_loss))
