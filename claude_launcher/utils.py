"""Utility functions for claude-launcher-plus.

Provides terminal color support, atomic file writes, and interactive UI helpers.
"""

__all__ = [
    "C",
    "NO_COLOR",
    "c",
    "strip_ansi",
    "atomic_write",
    "safe_read",
    "pick_from_list",
    "confirm_launch",
    "sanitize_provider_name",
    "sanitize_env_var_name",
    "sanitize_url",
]

import contextlib
import hashlib
import json
import os
import sys
import tempfile
import time
from pathlib import Path
from typing import Any, Dict, Iterator, List, Optional, cast

# Advisory file locking — available on POSIX (macOS/Linux), no-op elsewhere.
try:
    import fcntl

    HAS_FCNTL = True
except ImportError:
    HAS_FCNTL = False

# -- Terminal colors (no-color.org compliant) -----------------------

import re

NO_COLOR = "NO_COLOR" in os.environ

# On Windows, initialize colorama for ANSI escape support.
# Silently skipped if colorama is not installed or on non-Windows.
if os.name == "nt":
    try:
        import colorama

        colorama.init()
    except ImportError:
        pass


class C:
    """ANSI color codes. Respects the NO_COLOR environment variable."""

    GREEN = "" if NO_COLOR else "\033[0;32m"
    YELLOW = "" if NO_COLOR else "\033[1;33m"
    BLUE = "" if NO_COLOR else "\033[0;34m"
    RED = "" if NO_COLOR else "\033[0;31m"
    BOLD = "" if NO_COLOR else "\033[1m"
    NC = "" if NO_COLOR else "\033[0m"


# -- Color helpers ---------------------------------------------------

_ANSI_RE = re.compile(r"\033\[[0-9;]*m")


def c(color: str, msg: str) -> str:
    """Wrap *msg* in an ANSI color code, then reset.

    Falls back to plain *msg* when ``NO_COLOR`` is set or in non-TTY
    environments.  Usage::

        print(c(C.GREEN, "✓ Ok"))
        print(f"{c(C.BOLD, 'Status:')} ready")
    """
    if NO_COLOR:
        return msg
    return f"{color}{msg}{C.NC}"


def strip_ansi(text: str) -> str:
    """Remove all ANSI escape sequences from *text*.

    Useful for logging, file output, or comparison in tests.
    """
    return _ANSI_RE.sub("", text)


# -- Advisory file locking ------------------------------------------


@contextlib.contextmanager
def FileLock(lock_path: Path, timeout: float = 5.0) -> Iterator[None]:
    """Advisory file lock context manager.

    Uses ``fcntl.flock`` on POSIX systems; on platforms without fcntl
    (e.g. Windows without Cygwin) the lock is a no-op.

    Args:
        lock_path: Path to the lock file (created if it doesn't exist).
        timeout: Maximum seconds to wait for the lock (default 5.0).

    Raises:
        TimeoutError: If the lock cannot be acquired within *timeout*.
    """
    if not HAS_FCNTL:
        yield
        return

    lock_fd = os.open(str(lock_path), os.O_CREAT | os.O_RDWR, 0o600)
    deadline = time.monotonic() + timeout
    locked = False
    try:
        while True:
            try:
                fcntl.flock(lock_fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
                locked = True
                break  # lock acquired
            except (IOError, OSError):
                if time.monotonic() >= deadline:
                    raise TimeoutError(
                        f"Could not acquire lock for {lock_path} " f"within {timeout}s"
                    )
                time.sleep(0.05)
        yield
    finally:
        if locked:
            fcntl.flock(lock_fd, fcntl.LOCK_UN)
        os.close(lock_fd)


# -- Atomic file write ----------------------------------------------


def _check_writable(path: Path) -> None:
    """Check that the parent directory is writable before writing.

    Raises PermissionError if the directory doesn't allow write access.
    """
    parent = path.parent
    if not parent.exists():
        return  # will be created by atomic_write
    if not os.access(str(parent), os.W_OK):
        raise PermissionError(f"No write permission for directory: {parent}")


def _write_checksum(path: Path, content: str) -> None:
    """Write a SHA-256 checksum file alongside *path*.

    The companion file is ``path.name + ".sha256"`` and contains the
    hex digest of *content*.  Used by ``safe_read()`` to detect
    corruption after the fact.
    """
    digest = hashlib.sha256(content.encode("utf-8")).hexdigest()
    cs_path = path.with_suffix(path.suffix + ".sha256")
    cs_path.write_text(digest, encoding="utf-8")
    os.chmod(str(cs_path), 0o600)


def _verify_checksum(path: Path, content: str) -> bool:
    """Verify *content* against the stored checksum.

    Returns True if the checksum matches or no checksum file exists.
    Returns False if the checksum differs (indicating corruption).
    """
    cs_path = path.with_suffix(path.suffix + ".sha256")
    if not cs_path.exists():
        return True  # no checksum file = no corruption check
    stored = cs_path.read_text(encoding="utf-8").strip()
    actual = hashlib.sha256(content.encode("utf-8")).hexdigest()
    return stored == actual


def atomic_write(
    path: Path,
    data: Dict[str, Any],
    set_perms: bool = True,
    write_checksum: bool = True,
) -> None:
    """Write JSON atomically via tempfile + os.replace (crash-safe).

    Creates parent directories if they don't exist.
    Sets restrictive permissions (0o600) by default.
    Optionally writes a SHA-256 checksum for corruption detection.
    On failure, cleans up the temp file before re-raising.
    """
    _check_writable(path)
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
        if set_perms:
            os.chmod(str(path), 0o600)
        if write_checksum:
            content = json.dumps(data, indent=2, ensure_ascii=False) + "\n"
            _write_checksum(path, content)
    except Exception:
        if tmp is not None:
            try:
                Path(tmp.name).unlink()
            except FileNotFoundError:
                pass
        raise


def safe_read(path: Path, verify: bool = True) -> Dict[str, Any]:
    """Read a JSON file and optionally verify its checksum.

    Returns the parsed data on success.
    Raises ValueError if the checksum (when present) doesn't match.
    Raises FileNotFoundError if the file doesn't exist.
    Raises json.JSONDecodeError if the content is not valid JSON.
    """
    content = path.read_text(encoding="utf-8")
    if verify and not _verify_checksum(path, content):
        raise ValueError(f"Checksum mismatch for {path} — file may be corrupted")
    return cast(Dict[str, Any], json.loads(content))


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
