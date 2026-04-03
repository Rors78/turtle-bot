"""
Structured logging configuration for Turtle Bot.

Console handler: human-readable colored text (matches the original style).
File handler:    JSON Lines — one JSON object per log record.
"""

import sys
import json
import logging
import logging.handlers
from datetime import datetime, timezone


class JsonFormatter(logging.Formatter):
    """
    Formats each log record as a single JSON Line.

    Each line contains: timestamp, level, logger, message, and any
    extra key/value pairs attached to the LogRecord.
    """

    # Keys present on every LogRecord that are NOT user-supplied extras
    _BUILTIN_KEYS = frozenset({
        'args', 'created', 'exc_info', 'exc_text', 'filename',
        'funcName', 'levelname', 'levelno', 'lineno', 'message',
        'module', 'msecs', 'msg', 'name', 'pathname', 'process',
        'processName', 'relativeCreated', 'stack_info', 'thread',
        'threadName',
    })

    def format(self, record: logging.LogRecord) -> str:
        # Ensure record.message is populated
        record.message = record.getMessage()

        # Collect any user-supplied extras
        extras = {
            k: v for k, v in record.__dict__.items()
            if k not in self._BUILTIN_KEYS
        }

        payload = {
            'timestamp': datetime.fromtimestamp(record.created, tz=timezone.utc).isoformat(),
            'level': record.levelname,
            'logger': record.name,
            'message': record.message,
        }

        if extras:
            payload['extra'] = extras

        if record.exc_info:
            payload['exception'] = self.formatException(record.exc_info)

        return json.dumps(payload)


class _ColorFormatter(logging.Formatter):
    """Human-readable colored console formatter (matches original style)."""

    _COLORS = {
        'DEBUG':    '\033[90m',   # gray
        'INFO':     '\033[97m',   # white
        'WARNING':  '\033[93m',   # yellow
        'ERROR':    '\033[91m',   # red
        'CRITICAL': '\033[95m',   # purple
    }
    _RESET = '\033[0m'

    def format(self, record: logging.LogRecord) -> str:
        color = self._COLORS.get(record.levelname, '')
        formatted = super().format(record)
        return f"{color}{formatted}{self._RESET}"


def setup_logging(log_file: str, log_format: str = 'json') -> None:
    """
    Configure logging for the bot.

    Args:
        log_file:   Path to the log file.
        log_format: 'json' (default) writes JSON Lines to the file;
                    'text' writes plain text to both handlers.
                    The console always uses colored human-readable text.
    """
    root = logging.getLogger()
    root.setLevel(logging.INFO)

    # Remove any handlers that basicConfig or a previous call may have added
    root.handlers.clear()

    # ── Console handler (always colored text) ──────────────────────────────
    console_handler = logging.StreamHandler(sys.stdout)
    console_handler.setLevel(logging.INFO)
    console_fmt = _ColorFormatter(
        fmt='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
        datefmt='%Y-%m-%d %H:%M:%S',
    )
    console_handler.setFormatter(console_fmt)
    root.addHandler(console_handler)

    # ── File handler (JSON Lines or plain text) ─────────────────────────────
    try:
        file_handler = logging.FileHandler(log_file, encoding='utf-8')
        file_handler.setLevel(logging.DEBUG)  # Capture everything to file

        if log_format == 'json':
            file_handler.setFormatter(JsonFormatter())
        else:
            file_handler.setFormatter(logging.Formatter(
                fmt='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
                datefmt='%Y-%m-%d %H:%M:%S',
            ))

        root.addHandler(file_handler)
    except OSError as exc:
        logging.warning(f"Could not open log file '{log_file}': {exc} — file logging disabled")
