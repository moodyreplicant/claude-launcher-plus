"""Utility functions for claude-launcher-plus.

Provides terminal color support, atomic file writes, and interactive UI helpers.
"""

__all__ = [
    "C",
    "NO_COLOR",
    "atomic_write",
    "pick_from_list",
    "confirm_launch",
    "sanitize_provider_name",
    "sanitize_env_var_name",
    "sanitize_url",
]

import json
import os
import sys
import tempfile
from pathlib import Path
from typing import Any, Dict, List, Optional

# -- Terminal colors (no-color.org compliant) -----------------------

NO_COLOR = "NO_COLOR" in os.environ


class C:
    """ANSI color codes. Respects the NO_COLOR environment variable."""

    GREEN = "" if NO_COLOR else "\033[0;32m"
    YELLOW = "" if NO_COLOR else "\033[1;33m"
    BLUE = "" if NO_COLOR else "\033[0;34m"
    RED = "" if NO_COLOR else "\033[0;31m"
    BOLD = "" if NO_COLOR else "\033[1m"
    NC = "" if NO_COLOR else "\033[0m"


# -- Atomic file write ----------------------------------------------


def atomic_write(path: Path, data: Dict[str, Any]) -> None:
    """Write JSON atomically via tempfile + os.replace (crash-safe).

    Creates parent directories if they don't exist.
    On failure, cleans up the temp file before re-raising.
    """
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = None
    try:
        tmp = tempfile.NamedTemporaryFile(
            mode="w",
            dir=path.parent,
            delete=False,
            suffix=".tmp",
            encoding="utf-8",
        )
        json.dump(data, tmp, indent=2, ensure_ascii=False)
        tmp.write("\n")
        tmp.flush()
        os.fsync(tmp.fileno())
        tmp.close()
        os.replace(tmp.name, str(path))
    except Exception:
        if tmp is not None:
            try:
                Path(tmp.name).unlink()
            except FileNotFoundError:
                pass
        raise


# -- Interactive UI helpers -----------------------------------------


def _is_interactive() -> bool:
    """Check if stdin is a TTY (interactive terminal)."""
    return sys.stdin.isatty()


# -- Input validation -------------------------------------------------


def sanitize_provider_name(name: str) -> str:
    """Validate and clean a provider name.

    Accepts alphanumeric, spaces, hyphens, underscores, and dots.
    Returns the stripped name, or raises ValueError if invalid.
    """
    stripped = name.strip()
    if not stripped:
        raise ValueError("Provider name cannot be empty")
    if len(stripped) > 64:
        raise ValueError("Provider name too long (max 64 characters)")
    allowed = set("abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789 _-.")
    if not all(c in allowed for c in stripped):
        raise ValueError(
            "Provider name can only contain letters, numbers, spaces, "
            "hyphens, underscores, and dots"
        )
    return stripped


def sanitize_env_var_name(name: str) -> str:
    """Validate an environment variable name (e.g., DEEPSEEK_API_KEY).

    Returns the uppercased, stripped name, or raises ValueError.
    """
    stripped = name.strip().upper()
    if not stripped:
        raise ValueError("Env var name cannot be empty")
    if not stripped.replace("_", "").isalnum():
        raise ValueError(
            "Env var name can only contain uppercase letters, "
            "digits, and underscores"
        )
    if not stripped[0].isalpha():
        raise ValueError("Env var name must start with a letter")
    return stripped


def sanitize_url(url: str) -> str:
    """Basic URL validation — checks structure, not reachability.

    Accepts http/https URLs with a hostname.
    """
    stripped = url.strip().rstrip("/")
    if not stripped.startswith(("http://", "https://")):
        raise ValueError("URL must start with http:// or https://")
    # Ensure there's at least a hostname after the scheme
    rest = stripped.split("://", 1)[1]
    if not rest or "." not in rest and ":" not in rest and rest != "localhost":
        raise ValueError("URL must contain a valid hostname")
    return stripped


def pick_from_list(title: str, items: List[str]) -> Optional[int]:
    """Present a numbered list, return the chosen index.

    Auto-selects when only one item is available.
    Returns None when items is empty.
    """
    if not items:
        return None
    if len(items) == 1:
        print(f"  {title}: {C.BOLD}{items[0]}{C.NC} (auto-selected)")
        return 0
    print(f"\n  {C.BOLD}{title}:{C.NC}")
    for i, item in enumerate(items):
        print(f"  {C.BOLD}{i + 1}){C.NC}  {item}")
    print()
    if not _is_interactive():
        print(f"  Non-interactive — using: {C.BOLD}{items[0]}{C.NC}")
        return 0
    try:
        choice = input(f"  Choose [1-{len(items)}]: ").strip()
        idx = int(choice) - 1
        if 0 <= idx < len(items):
            return idx
    except (ValueError, EOFError, KeyboardInterrupt):
        pass
    print(f"  {C.YELLOW}Invalid choice, using first.{C.NC}")
    return 0


def confirm_launch(title: str, *details: str) -> bool:
    """Display a Y/n confirmation prompt.

    Skips the prompt (returns True) when stdin is not a TTY.
    """
    if not _is_interactive():
        return True
    print(f"\n  {C.BOLD}{C.BLUE}═══ Ready to launch: {title} ═══{C.NC}")
    for line in details:
        print(f"  {line}")
    print()
    try:
        answer = input("  Proceed? [Y/n] ").strip().lower()
    except (EOFError, KeyboardInterrupt):
        return False
    return answer not in ("n", "no")
