"""
Tests for utils/analytics.py — pure functions, no side effects, no network calls.
"""

import sys
import os
import math
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import pytest
from utils.analytics import (
    sharpe_ratio,
    sortino_ratio,
    calmar_ratio,
    profit_factor,
    max_drawdown,
    monthly_returns,
    expectancy,
)


# ─── sharpe_ratio ─────────────────────────────────────────────────────────────

def test_sharpe_ratio_positive():
    """
    Known daily returns that produce a positive Sharpe.
    returns = [0.01] * 252  → mean=0.01, std=0, but add variance:
    Use alternating 0.02 / 0.00 for a clean known result.

    With uniform returns = [0.005]*260, mean=0.005, std≈0 so use non-uniform.
    Use 10 returns where mean > 0 and std is known.
    """
    # returns with mean=0.01, std=0.005
    import statistics
    returns = [0.01, 0.015, 0.005, 0.012, 0.008, 0.011, 0.009, 0.013, 0.007, 0.010]
    mean_r = sum(returns) / len(returns)
    std_r = statistics.stdev(returns)

    expected_sharpe = (mean_r / std_r) * math.sqrt(252)
    result = sharpe_ratio(returns, risk_free_rate=0.0)

    assert result > 0.0
    assert abs(result - expected_sharpe) < 1e-6


def test_sharpe_ratio_zero_std():
    """All returns identical → std = 0 → return 0.0 (no divide-by-zero)."""
    returns = [0.005] * 20
    result = sharpe_ratio(returns)
    assert result == 0.0


def test_sharpe_ratio_insufficient_data():
    """Less than 2 returns → return 0.0."""
    assert sharpe_ratio([]) == 0.0
    assert sharpe_ratio([0.01]) == 0.0


def test_sharpe_ratio_negative():
    """Negative mean returns → negative Sharpe."""
    returns = [-0.01, -0.02, -0.015, -0.01, -0.012]
    result = sharpe_ratio(returns)
    assert result < 0.0


# ─── sortino_ratio ────────────────────────────────────────────────────────────

def test_sortino_ratio():
    """
    Returns with mixed positive/negative — Sortino should differ from Sharpe
    because it only penalises downside deviations.
    """
    # Mix of wins and losses; Sortino > 0 since mean is positive
    returns = [0.02, -0.01, 0.03, -0.005, 0.015, 0.01, -0.002, 0.025]
    result = sortino_ratio(returns)

    # Mean is positive, so Sortino should be positive
    mean_r = sum(returns) / len(returns)
    assert mean_r > 0
    assert result > 0.0


def test_sortino_ratio_no_downside():
    """All positive returns → downside std = 0 → return 0.0 (safe)."""
    returns = [0.01, 0.02, 0.015, 0.01, 0.012]
    result = sortino_ratio(returns)
    # All returns are above 0 (rf=0), downside_sq all = 0
    assert result == 0.0


# ─── calmar_ratio ─────────────────────────────────────────────────────────────

def test_calmar_ratio_basic():
    """total_return=0.30, max_dd=0.15, years=1 → calmar should be approx 2.0."""
    # annualised_return = (1.30)^(1/1) - 1 = 0.30
    result = calmar_ratio(total_return=0.30, max_drawdown=0.15, years=1.0)
    assert abs(result - 0.30 / 0.15) < 1e-6   # = 2.0

def test_calmar_ratio_zero_drawdown():
    """max_drawdown=0 → return 0.0 (guard against divide-by-zero)."""
    result = calmar_ratio(total_return=0.20, max_drawdown=0.0, years=1.0)
    assert result == 0.0


# ─── profit_factor ────────────────────────────────────────────────────────────

def test_profit_factor():
    """Gross profit = 300, gross loss = 200 → PF = 1.5."""
    wins = [100.0, 150.0, 50.0]
    losses = [-80.0, -70.0, -50.0]
    result = profit_factor(wins, losses)
    assert abs(result - (300.0 / 200.0)) < 1e-9


def test_profit_factor_no_losses():
    """No losing trades → return infinity (or at least a very large number)."""
    wins = [100.0, 200.0]
    losses: list = []
    result = profit_factor(wins, losses)
    assert result == float('inf')


def test_profit_factor_no_wins():
    """No winning trades → return 0.0."""
    wins: list = []
    losses = [-50.0, -30.0]
    result = profit_factor(wins, losses)
    assert result == 0.0


# ─── max_drawdown ─────────────────────────────────────────────────────────────

def test_max_drawdown_basic():
    """
    Equity: 100, 120, 90, 110, 80.
    Peak at index 1 (120), trough at index 4 (80).
    Max drawdown = (120-80)/120 = 33.33%.
    """
    curve = [100.0, 120.0, 90.0, 110.0, 80.0]
    dd, peak_idx, trough_idx = max_drawdown(curve)

    expected_dd = (120.0 - 80.0) / 120.0
    assert abs(dd - expected_dd) < 1e-9
    assert peak_idx == 1
    assert trough_idx == 4


def test_max_drawdown_monotone_up():
    """Monotonically increasing equity → drawdown = 0."""
    curve = [100.0, 110.0, 120.0, 130.0]
    dd, peak_idx, trough_idx = max_drawdown(curve)
    assert dd == 0.0


def test_max_drawdown_single_element():
    """Single element → (0.0, 0, 0)."""
    dd, p, t = max_drawdown([100.0])
    assert dd == 0.0
    assert p == 0
    assert t == 0


# ─── monthly_returns ──────────────────────────────────────────────────────────

def test_monthly_returns_two_months():
    """
    Build an equity curve spanning two months.
    January: 100 → 110 (+10%)
    February: 110 → 99 (-10%)
    """
    curve = [
        {'date': '2024-01-01', 'equity': 100.0},
        {'date': '2024-01-15', 'equity': 105.0},
        {'date': '2024-01-31', 'equity': 110.0},
        {'date': '2024-02-15', 'equity': 104.5},
        {'date': '2024-02-29', 'equity': 99.0},
    ]
    result = monthly_returns(curve)

    assert '2024-01' in result
    assert '2024-02' in result
    # Jan: 110/100 - 1 = 0.1
    assert abs(result['2024-01'] - 0.10) < 1e-9
    # Feb: 99/110 - 1 ≈ -0.10
    assert abs(result['2024-02'] - (99.0 / 110.0 - 1.0)) < 1e-9


def test_monthly_returns_empty():
    """Empty curve → empty dict."""
    assert monthly_returns([]) == {}


# ─── expectancy ───────────────────────────────────────────────────────────────

def test_expectancy_basic():
    """
    win_rate=0.4, avg_win=$200, avg_loss=-$100.
    expectancy = 0.4*200 - 0.6*100 = 80 - 60 = $20.
    """
    result = expectancy(avg_win=200.0, avg_loss=-100.0, win_rate=0.4)
    assert abs(result - 20.0) < 1e-9


def test_expectancy_negative():
    """Losing strategy: low win rate + small wins → negative expectancy."""
    result = expectancy(avg_win=50.0, avg_loss=-200.0, win_rate=0.3)
    # 0.3*50 - 0.7*200 = 15 - 140 = -125
    assert result < 0
    assert abs(result - (0.3 * 50 - 0.7 * 200)) < 1e-9


def test_expectancy_handles_positive_avg_loss():
    """avg_loss passed as positive value — abs() is taken internally."""
    result_pos = expectancy(avg_win=200.0, avg_loss=100.0, win_rate=0.4)
    result_neg = expectancy(avg_win=200.0, avg_loss=-100.0, win_rate=0.4)
    assert abs(result_pos - result_neg) < 1e-9


# ─── Sanity / regression tests (added to guard against known bug regressions) ──

def test_max_drawdown_never_exceeds_100():
    """
    Equity drops from 100 to 1 — a 99% loss.
    Drawdown must be <= 1.0 (i.e. <= 100%).  It should never exceed 1.0 even
    when the equity curve contains very small positive values near zero.
    """
    curve = [100.0, 80.0, 50.0, 20.0, 5.0, 1.0]
    dd, _, _ = max_drawdown(curve)
    assert dd <= 1.0, f"Drawdown exceeded 100%: {dd}"
    expected = (100.0 - 1.0) / 100.0
    assert abs(dd - expected) < 1e-9


def test_max_drawdown_equity_to_zero():
    """
    Equity curve hits exactly 0.  Drawdown must equal 1.0 (100%), not exceed it.
    Without the zero-clamp fix, a negative equity value could push dd > 1.0.
    """
    curve = [100.0, 60.0, 0.0]
    dd, peak_idx, trough_idx = max_drawdown(curve)
    assert dd == 1.0, f"Expected 1.0 for equity-to-zero, got {dd}"
    assert peak_idx == 0
    assert trough_idx == 2


def test_max_drawdown_negative_equity_clamped():
    """
    If negative equity values are passed (e.g. from a bugged backtester before
    the emergency-stop fix), max_drawdown must still cap the result at 1.0.
    """
    # Peak 130, then equity goes negative — without the clamp this would be
    # (130 - (-5)) / 130 = 1.038, i.e. 103.8%
    curve = [130.0, 100.0, 50.0, -5.0]
    dd, _, _ = max_drawdown(curve)
    assert dd <= 1.0, f"Drawdown with negative equity exceeded 100%: {dd}"
    assert dd == 1.0


def test_sharpe_negative_on_losing_strategy():
    """
    Daily returns that produce a net loss must yield a negative Sharpe ratio.
    Uses a realistic mix: mostly flat days + a few losses (mimics sparse trading).
    """
    # 160 flat days, 20 losing days — clearly a losing strategy
    returns = [0.0] * 160 + [-0.015] * 20
    result = sharpe_ratio(returns)
    assert result < 0.0, f"Sharpe must be negative on a losing strategy, got {result}"


def test_sharpe_zero_std_returns_zero():
    """All returns identical → std = 0 → return 0.0 (no divide-by-zero or inf/nan)."""
    returns = [0.003] * 30
    result = sharpe_ratio(returns)
    assert result == 0.0
    assert not math.isnan(result)
    assert not math.isinf(result)


def test_sortino_near_zero_downside():
    """
    Returns mostly zero with only a tiny loss.  Without the 1e-8 guard, the
    downside std would be so small that Sortino explodes to 12+ or similar.
    Verify the result is finite and not absurdly large.
    """
    # 179 flat days + 1 tiny loss
    returns = [0.0] * 179 + [-0.001]
    result = sortino_ratio(returns)
    # With only 1 loss day out of 180, the downside_std is near-zero.
    # The guard should return 0.0 in this situation.
    assert math.isfinite(result), f"Sortino must be finite, got {result}"
    # It should not be an absurd number like 12 or higher
    assert abs(result) < 5.0, f"Sortino is unreasonably large: {result}"


def test_monthly_returns_match_total():
    """
    Equity goes from 130 to 92.42 over 6 months.
    Compounding the monthly returns must approximately equal -28.91% total return.
    """
    # Build a synthetic 6-month equity curve: 130 -> 92.42 linearly with end-of-month points
    curve = [
        {'date': '2024-01-31', 'equity': 120.0},
        {'date': '2024-02-29', 'equity': 115.0},
        {'date': '2024-03-31', 'equity': 108.0},
        {'date': '2024-04-30', 'equity': 100.0},
        {'date': '2024-05-31', 'equity': 96.0},
        {'date': '2024-06-30', 'equity': 92.42},
    ]
    monthly = monthly_returns(curve)

    assert len(monthly) == 6

    # Compound all monthly returns: product of (1 + r) for each month
    compounded = 1.0
    for r in monthly.values():
        compounded *= (1.0 + r)
    total = compounded - 1.0

    # Expected total: (92.42 - 120) / 120 = -22.98%  (first entry is start of curve)
    expected_total = (92.42 / 120.0) - 1.0
    assert abs(total - expected_total) < 1e-6, (
        f"Compounded monthly returns ({total:.4f}) don't match expected ({expected_total:.4f})"
    )
