"""
Tests for utils/notifications.py — Discord webhook integration.
All tests mock urllib so no real HTTP calls are made.
"""

import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import json
from unittest.mock import patch, MagicMock, call
import pytest

from utils.notifications import Notifier, DISCORD_COLOR_GREEN, DISCORD_COLOR_RED


# ─── Config helpers ───────────────────────────────────────────────────────────

class DiscordConfig:
    """Config with Discord enabled and a dummy webhook URL."""
    PAPER_TRADING = True
    ALERT_ON_ENTRY = True
    ALERT_ON_EXIT = True
    ALERT_ON_STOP = True
    ALERT_ON_ERROR = True
    ALERT_ON_DISCORD = True
    DISCORD_WEBHOOK_URL = 'https://discord.com/api/webhooks/fake/test-webhook'


class NoDiscordConfig:
    """Config with Discord disabled (default state)."""
    PAPER_TRADING = True
    ALERT_ON_ENTRY = True
    ALERT_ON_EXIT = True
    ALERT_ON_STOP = True
    ALERT_ON_ERROR = True
    ALERT_ON_DISCORD = False
    DISCORD_WEBHOOK_URL = ''


class EmptyUrlConfig:
    """Config with Discord enabled but no URL set."""
    PAPER_TRADING = True
    ALERT_ON_ENTRY = True
    ALERT_ON_EXIT = True
    ALERT_ON_STOP = True
    ALERT_ON_ERROR = True
    ALERT_ON_DISCORD = True
    DISCORD_WEBHOOK_URL = ''


# ─── test_discord_disabled_no_send ────────────────────────────────────────────

def test_discord_disabled_no_send():
    """
    When ALERT_ON_DISCORD=False, no HTTP call should be made regardless of
    whether a URL is set.
    """
    notifier = Notifier(NoDiscordConfig())

    with patch('urllib.request.urlopen') as mock_urlopen:
        notifier.alert_entry(
            symbol='BTC/USDT',
            system=1,
            price=50000.0,
            quantity=0.001,
            atr=1000.0,
            stop=48000.0,
        )
        mock_urlopen.assert_not_called()


def test_discord_empty_url_no_send():
    """
    When ALERT_ON_DISCORD=True but DISCORD_WEBHOOK_URL='', no HTTP call.
    """
    notifier = Notifier(EmptyUrlConfig())

    with patch('urllib.request.urlopen') as mock_urlopen:
        notifier.alert_entry(
            symbol='ETH/USDT',
            system=2,
            price=3000.0,
            quantity=0.01,
            atr=50.0,
            stop=2900.0,
        )
        mock_urlopen.assert_not_called()


# ─── test_discord_formats_embed ───────────────────────────────────────────────

def test_discord_formats_embed():
    """
    Mock urllib, capture the payload, verify it's a valid Discord embed structure.
    The embed should contain: title, description, and color.
    """
    notifier = Notifier(DiscordConfig())

    captured_payloads = []

    # We need to capture what Request is called with
    with patch('urllib.request.Request') as mock_request_cls, \
         patch('urllib.request.urlopen') as mock_urlopen:

        # Make urlopen return a context manager mock
        mock_ctx = MagicMock()
        mock_ctx.__enter__ = MagicMock(return_value=MagicMock())
        mock_ctx.__exit__ = MagicMock(return_value=False)
        mock_urlopen.return_value = mock_ctx

        # Capture the data passed to Request
        def capture_request(url, data=None, headers=None, method=None):
            if data:
                payload = json.loads(data.decode('utf-8'))
                captured_payloads.append(payload)
            return MagicMock()

        mock_request_cls.side_effect = capture_request

        notifier.alert_entry(
            symbol='BTC/USDT',
            system=1,
            price=50000.0,
            quantity=0.001,
            atr=1000.0,
            stop=48000.0,
        )

    assert len(captured_payloads) == 1, "Expected exactly one Discord payload"
    payload = captured_payloads[0]

    # Top-level structure
    assert 'embeds' in payload, "Payload must have 'embeds' key"
    assert isinstance(payload['embeds'], list)
    assert len(payload['embeds']) == 1

    embed = payload['embeds'][0]
    assert 'title' in embed, "Embed must have 'title'"
    assert 'description' in embed, "Embed must have 'description'"
    assert 'color' in embed, "Embed must have 'color'"

    # Color should be green for an entry
    assert embed['color'] == DISCORD_COLOR_GREEN

    # Title should mention the symbol
    assert 'BTC/USDT' in embed['title']


def test_discord_embed_exit_loss_is_red():
    """
    An exit with a losing P&L should use the red color code.
    """
    notifier = Notifier(DiscordConfig())
    captured_payloads = []

    with patch('urllib.request.Request') as mock_request_cls, \
         patch('urllib.request.urlopen') as mock_urlopen:

        mock_ctx = MagicMock()
        mock_ctx.__enter__ = MagicMock(return_value=MagicMock())
        mock_ctx.__exit__ = MagicMock(return_value=False)
        mock_urlopen.return_value = mock_ctx

        def capture_request(url, data=None, headers=None, method=None):
            if data:
                payload = json.loads(data.decode('utf-8'))
                captured_payloads.append(payload)
            return MagicMock()

        mock_request_cls.side_effect = capture_request

        notifier.alert_exit(
            symbol='ETH/USDT',
            reason='STOP_HIT',
            price=2800.0,
            pnl=-150.0,       # loss
            pnl_pct=-0.05,
        )

    assert len(captured_payloads) == 1
    embed = captured_payloads[0]['embeds'][0]
    assert embed['color'] == DISCORD_COLOR_RED


# ─── test_discord_failure_doesnt_crash ────────────────────────────────────────

def test_discord_failure_doesnt_crash():
    """
    Mock urllib.request.urlopen to raise an exception.
    Verify that alert_entry() still completes without raising.
    """
    notifier = Notifier(DiscordConfig())

    with patch('urllib.request.urlopen', side_effect=Exception("Connection refused")):
        # Must NOT raise — Discord failure should be swallowed
        try:
            notifier.alert_entry(
                symbol='SOL/USDT',
                system=1,
                price=150.0,
                quantity=1.0,
                atr=5.0,
                stop=140.0,
            )
        except Exception as e:
            pytest.fail(f"alert_entry() raised an exception when Discord failed: {e}")


def test_discord_request_failure_doesnt_crash():
    """
    Mock urllib.request.Request to raise — same guarantee.
    """
    notifier = Notifier(DiscordConfig())

    with patch('urllib.request.Request', side_effect=OSError("Network error")):
        try:
            notifier.alert_stop_hit(
                symbol='ADA/USDT',
                price=0.40,
                stop=0.38,
                market_value=40.0,
            )
        except Exception as e:
            pytest.fail(f"alert_stop_hit() raised when Discord failed: {e}")


def test_discord_pyramid_uses_blue():
    """
    Pyramid alert should send the blue color code to Discord.
    """
    from utils.notifications import DISCORD_COLOR_BLUE
    notifier = Notifier(DiscordConfig())
    captured = []

    with patch('urllib.request.Request') as mock_req, \
         patch('urllib.request.urlopen') as mock_open:

        mock_ctx = MagicMock()
        mock_ctx.__enter__ = MagicMock(return_value=MagicMock())
        mock_ctx.__exit__ = MagicMock(return_value=False)
        mock_open.return_value = mock_ctx

        def capture(url, data=None, headers=None, method=None):
            if data:
                captured.append(json.loads(data.decode('utf-8')))
            return MagicMock()

        mock_req.side_effect = capture

        notifier.alert_pyramid(symbol='BTC/USDT', unit_num=2, price=52000.0, quantity=0.001)

    assert len(captured) == 1
    assert captured[0]['embeds'][0]['color'] == DISCORD_COLOR_BLUE


def test_discord_error_uses_orange():
    """
    Error alert should send the orange color code to Discord.
    """
    from utils.notifications import DISCORD_COLOR_ORANGE
    notifier = Notifier(DiscordConfig())
    captured = []

    with patch('urllib.request.Request') as mock_req, \
         patch('urllib.request.urlopen') as mock_open:

        mock_ctx = MagicMock()
        mock_ctx.__enter__ = MagicMock(return_value=MagicMock())
        mock_ctx.__exit__ = MagicMock(return_value=False)
        mock_open.return_value = mock_ctx

        def capture(url, data=None, headers=None, method=None):
            if data:
                captured.append(json.loads(data.decode('utf-8')))
            return MagicMock()

        mock_req.side_effect = capture

        notifier.alert_error("Something went wrong", Exception("test error"))

    assert len(captured) == 1
    assert captured[0]['embeds'][0]['color'] == DISCORD_COLOR_ORANGE
