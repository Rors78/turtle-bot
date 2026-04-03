"""
Tests for Config — defaults, validation, credentials.
All tests patch environment variables rather than touching .env files.
"""

import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from unittest.mock import patch
import pytest


def _make_config(**overrides):
    """
    Create a Config instance with a clean environment.
    overrides are extra env vars to set (values must be strings).
    """
    base_env = {
        'ACCOUNT_SIZE': '130',
        'PAPER_TRADING': 'True',
        'SYSTEM_1_ENABLED': 'True',
        'SYSTEM_2_ENABLED': 'True',
        'RISK_PER_TRADE': '0.02',
        'MAX_TOTAL_RISK': '0.20',
        'EMERGENCY_STOP_LOSS': '0.30',
        'MIN_ACCOUNT_BALANCE': '100',
        # Clear API keys so live-trading check is not triggered
        'KRAKEN_API_KEY': '',
        'KRAKEN_API_SECRET': '',
    }
    base_env.update(overrides)

    with patch.dict(os.environ, base_env, clear=True):
        from config import Config
        return Config()


# ─── Defaults ────────────────────────────────────────────────────────────────

def test_defaults_load():
    """Create Config with minimal env, verify sensible defaults."""
    cfg = _make_config()
    assert cfg.ACCOUNT_SIZE == 130.0
    assert cfg.PAPER_TRADING is True
    assert cfg.ATR_PERIOD == 20
    assert cfg.RISK_PER_TRADE == 0.02
    assert cfg.MAX_COINS == 10
    assert cfg.SYSTEM_1_ENTRY == 20
    assert cfg.SYSTEM_2_ENTRY == 55
    assert cfg.STOP_DISTANCE == 2.0
    assert cfg.PYRAMID_INCREMENT == 0.5


# ─── Validation ───────────────────────────────────────────────────────────────

def test_validate_catches_zero_account():
    """ACCOUNT_SIZE=0 must produce a validation error."""
    cfg = _make_config(ACCOUNT_SIZE='0')
    errors = cfg.validate()
    assert any('ACCOUNT_SIZE' in e for e in errors), f"Expected ACCOUNT_SIZE error, got: {errors}"


def test_validate_catches_no_systems():
    """Both systems disabled must produce an error."""
    cfg = _make_config(SYSTEM_1_ENABLED='False', SYSTEM_2_ENABLED='False')
    errors = cfg.validate()
    assert any('system' in e.lower() or 'System' in e for e in errors), (
        f"Expected system error, got: {errors}"
    )


def test_validate_catches_bad_risk():
    """RISK_PER_TRADE=0.5 (50%) is above the 10% cap and must produce an error."""
    cfg = _make_config(RISK_PER_TRADE='0.5')
    errors = cfg.validate()
    assert any('RISK_PER_TRADE' in e for e in errors), f"Expected RISK_PER_TRADE error, got: {errors}"


def test_validate_passes_good_config():
    """Default config must pass validation with no errors."""
    cfg = _make_config()
    errors = cfg.validate()
    assert errors == [], f"Expected no errors, got: {errors}"


# ─── API Credentials ─────────────────────────────────────────────────────────

def test_api_credentials():
    """Set env vars, verify get_api_credentials() returns them."""
    cfg = _make_config(KRAKEN_API_KEY='test_key_123', KRAKEN_API_SECRET='test_secret_456')
    creds = cfg.get_api_credentials()
    assert creds['api_key'] == 'test_key_123'
    assert creds['api_secret'] == 'test_secret_456'
