"""Tests for the logger module — configuration and formatting."""

import json
import logging
import sys
from pathlib import Path
from typing import Any

from claude_launcher.logger import (
    HumanFormatter,
    JsonFormatter,
    configure_logging,
    get_logger,
)


class TestGetLogger:
    """get_logger() returns properly namespaced loggers."""

    def test_root_logger_name(self) -> None:
        """Root logger has the expected namespace."""
        logger = get_logger()
        assert logger.name == "claude-launcher"

    def test_child_logger_name(self) -> None:
        """Child logger follows the claude-launcher.name pattern."""
        logger = get_logger("test")
        assert logger.name == "claude-launcher.test"

    def test_logger_produces_output(self, capsys: Any) -> None:
        """Logger output is captured correctly."""
        configure_logging(verbose=True)
        logger = get_logger("capture-test")
        logger.info("hello from logger")
        captured = capsys.readouterr()
        assert "hello from logger" in captured.out


class TestHumanFormatter:
    """HumanFormatter produces readable output."""

    def test_format_includes_level(self) -> None:
        """Formatted output includes the log level."""
        formatter = HumanFormatter()
        record = logging.LogRecord(
            name="test",
            level=logging.INFO,
            pathname=__file__,
            lineno=10,
            msg="test message",
            args=(),
            exc_info=None,
        )
        output = formatter.format(record)
        assert "INFO" in output
        assert "test message" in output


class TestJsonFormatter:
    """JsonFormatter produces valid JSON lines."""

    def test_format_is_valid_json(self) -> None:
        """Output parses as valid JSON."""
        formatter = JsonFormatter()
        record = logging.LogRecord(
            name="test",
            level=logging.WARNING,
            pathname=__file__,
            lineno=20,
            msg="warn: %s",
            args=("something",),
            exc_info=None,
        )
        output = formatter.format(record)
        data = json.loads(output)
        assert data["level"] == "WARNING"
        assert data["message"] == "warn: something"
        assert data["logger"] == "test"
        assert "timestamp" in data

    def test_format_includes_exception(self) -> None:
        """Exception info is included in JSON output."""
        formatter = JsonFormatter()
        try:
            raise ValueError("test error")
        except ValueError:
            exc_info = sys.exc_info()
            record = logging.LogRecord(
                name="test",
                level=logging.ERROR,
                pathname=__file__,
                lineno=30,
                msg="error occurred",
                args=(),
                exc_info=exc_info,
            )
        output = formatter.format(record)
        data = json.loads(output)
        assert data["level"] == "ERROR"
        assert "exception" in data
        assert "ValueError" in data["exception"]


class TestConfigureLogging:
    """configure_logging() sets up handlers correctly."""

    def test_verbose_sets_debug_level(self) -> None:
        """verbose=True sets logger to DEBUG."""
        configure_logging(verbose=True)
        logger = get_logger("verbose-test")
        assert logger.isEnabledFor(logging.DEBUG) is True

    def test_default_is_info(self) -> None:
        """Default (verbose=False) sets logger to INFO."""
        configure_logging(verbose=False)
        logger = get_logger("info-test")
        assert logger.isEnabledFor(logging.INFO) is True
        assert logger.isEnabledFor(logging.DEBUG) is False

    def test_log_file_creates_file(self, tmp_path: Path) -> None:
        """log_file creates a file at the specified path."""
        log_file = tmp_path / "test.log"
        configure_logging(log_file=log_file)
        logger = get_logger("file-test")
        logger.info("written to file")
        assert log_file.exists()
        content = log_file.read_text()
        assert "written to file" in content

    def test_handlers_cleared_on_reconfigure(self) -> None:
        """Calling configure_logging twice doesn't duplicate handlers."""
        configure_logging()
        logger = get_logger("handler-test")
        initial_count = len(logger.handlers)
        configure_logging()
        assert len(logger.handlers) == initial_count
