"""Utility functions for claude-launcher-plus.

Provides terminal color support, atomic file writes, and interactive UI helpers.
"""

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
