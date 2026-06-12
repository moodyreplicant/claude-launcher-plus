"""Logging configuration for claude-launcher-plus."""

import logging
import sys


def configure_logging(verbose: bool = False) -> None:
    """Configure logging with optional verbose (DEBUG) mode.

    Phase 3 will enhance this with structured JSON output and log rotation.
    """
    level = logging.DEBUG if verbose else logging.INFO
    logging.basicConfig(
        level=level,
        format="%(asctime)s %(levelname)s: %(message)s",
        stream=sys.stdout,
        force=True,
    )
