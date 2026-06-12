"""Logging configuration for claude-launcher-plus.

Provides structured (JSON) and human-readable logging with optional
log file output and rotation. Call ``configure_logging()`` at startup
to set up the root logger.
"""

__all__ = [
    "configure_logging",
    "LOGGER_NAME",
    "SecretRedactionFilter",
]

import json
import logging
import logging.handlers
import re
import sys
from pathlib import Path
from typing import Any, List, Optional

LOGGER_NAME = "claude-launcher"
LOG_DIR = Path.home() / ".claude" / "logs"


class JsonFormatter(logging.Formatter):
    """Format log records as JSON lines for machine parsing.

    Produces one JSON object per line with keys: timestamp, level,
    logger, message, and optional exception_info.
    """

    def format(self, record: logging.LogRecord) -> str:
        """Format a log record as a JSON string."""
        data: dict[str, Any] = {
            "timestamp": self.formatTime(record, datefmt="%Y-%m-%dT%H:%M:%S"),
            "level": record.levelname,
            "logger": record.name,
            "message": record.getMessage(),
        }
        if (
            record.exc_info
            and record.exc_info[0]
            and not isinstance(record.exc_info, bool)
        ):
            data["exception"] = self.formatException(record.exc_info)
        return json.dumps(data, ensure_ascii=False)


class HumanFormatter(logging.Formatter):
    """Format log records as human-readable lines."""

    def format(self, record: logging.LogRecord) -> str:
        """Format with timestamp, level, and message."""
        return (
            f"{self.formatTime(record, datefmt='%H:%M:%S')} "
            f"{record.levelname:<5} {record.getMessage()}"
        )


# Patterns for values that should never appear in logs.
# These match common API key and auth token formats.
_SECRET_PATTERNS: List[re.Pattern[str]] = [
    re.compile(r"\bsk-[A-Za-z0-9]{20,}\b"),  # Anthropic API keys
    re.compile(r"\b[A-Za-z0-9+/=]{40,}\b"),  # base64-like tokens (40+ chars)
    re.compile(
        r"(?i)(api[_-]?key|auth[_-]?token|secret)" r"\s*[:=]\s*\S+"
    ),  # inline key assignments
]

# The replacement for any matched secret.
_REDACTED = "[REDACTED]"


class SecretRedactionFilter(logging.Filter):
    """Logging filter that redacts sensitive information from log records.

    Attach to any handler that might log messages containing API keys,
    auth tokens, or other secrets. Redaction happens on the formatted
    message before output.
    """

    def __init__(self, name: str = "") -> None:
        super().__init__(name)

    def filter(self, record: logging.LogRecord) -> bool:
        """Redact secrets from the log message in-place."""
        if isinstance(record.msg, str):
            for pattern in _SECRET_PATTERNS:
                record.msg = pattern.sub(_REDACTED, record.msg)
        # Also redact args that might contain secrets
        if record.args:
            sanitized: List[Any] = []
            for arg in record.args:
                if isinstance(arg, str):
                    for pattern in _SECRET_PATTERNS:
                        arg = pattern.sub(_REDACTED, arg)
                sanitized.append(arg)
            record.args = tuple(sanitized)
        return True  # always pass the record through


def configure_logging(
    verbose: bool = False,
    log_file: Optional[Path] = None,
    json_output: bool = False,
) -> None:
    """Configure the root logger.

    Args:
        verbose: Enable DEBUG-level logging (default: INFO).
        log_file: Path to an optional log file. If not provided, logs
            go to stdout only. Log files automatically rotate at 5 MB.
        json_output: If True, emit JSON-formatted log lines instead of
            human-readable text.
    """
    logger = logging.getLogger(LOGGER_NAME)
    logger.setLevel(logging.DEBUG if verbose else logging.INFO)
    logger.handlers.clear()

    # Always log to stdout
    stdout_handler = logging.StreamHandler(sys.stdout)
    stdout_handler.setLevel(logging.DEBUG if verbose else logging.INFO)
    stdout_handler.setFormatter(JsonFormatter() if json_output else HumanFormatter())
    stdout_handler.addFilter(SecretRedactionFilter())
    logger.addHandler(stdout_handler)

    # Optional file handler with rotation
    if log_file is not None:
        log_file.parent.mkdir(parents=True, exist_ok=True)
        file_handler = logging.handlers.RotatingFileHandler(
            log_file,
            maxBytes=5 * 1024 * 1024,  # 5 MB
            backupCount=3,
            encoding="utf-8",
        )
        file_handler.setLevel(logging.DEBUG)  # always capture everything
        file_handler.setFormatter(JsonFormatter())
        file_handler.addFilter(SecretRedactionFilter())
        logger.addHandler(file_handler)


def get_logger(name: Optional[str] = None) -> logging.Logger:
    """Return a child logger of the claude-launcher namespace.

    Usage::

        logger = get_logger(__name__)
        logger.info("launching %s", mode)
    """
    if name:
        return logging.getLogger(f"{LOGGER_NAME}.{name}")
    return logging.getLogger(LOGGER_NAME)
