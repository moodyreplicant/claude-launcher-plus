"""Tests for the utils module — atomic write, safe read, file locking, permissions."""

import json
import os
import stat
from pathlib import Path
from unittest.mock import patch

import pytest

from claude_launcher.utils import (
    FileLock,
    _check_writable,
    _verify_checksum,
    _write_checksum,
    atomic_write,
    safe_read,
)


class TestAtomicWrite:
    """atomic_write() file output."""

    def test_writes_json_file(self, tmp_path: Path) -> None:
        """Basic write creates a valid JSON file."""
        target = tmp_path / "test.json"
        data = {"key": "value", "num": 42}
        atomic_write(target, data)
        assert target.exists()
        assert json.loads(target.read_text()) == data

    def test_sets_restrictive_permissions(self, tmp_path: Path) -> None:
        """Written file has 0o600 permissions."""
        target = tmp_path / "perms.json"
        atomic_write(target, {"a": 1})
        mode = stat.S_IMODE(os.stat(str(target)).st_mode)
        assert mode == 0o600

    def test_skips_permissions_when_disabled(self, tmp_path: Path) -> None:
        """set_perms=False skips chmod."""
        target = tmp_path / "noperms.json"
        atomic_write(target, {"a": 1}, set_perms=False)
        # File should still exist without explicit restriction
        assert target.exists()

    def test_creates_parent_directories(self, tmp_path: Path) -> None:
        """Parent directories are created automatically."""
        target = tmp_path / "sub" / "dir" / "nested.json"
        atomic_write(target, {"hello": "world"})
        assert target.exists()

    def test_overwrites_existing_file(self, tmp_path: Path) -> None:
        """Existing file is replaced atomically."""
        target = tmp_path / "overwrite.json"
        target.write_text(json.dumps({"old": "data"}))
        atomic_write(target, {"new": "data"})
        assert json.loads(target.read_text()) == {"new": "data"}

    def test_creates_checksum_file(self, tmp_path: Path) -> None:
        """Checksum file is created alongside the JSON file."""
        target = tmp_path / "checksum_test.json"
        data = {"key": "value"}
        atomic_write(target, data, write_checksum=True)
        cs_path = target.with_suffix(target.suffix + ".sha256")
        assert cs_path.exists()
        assert len(cs_path.read_text().strip()) == 64  # SHA-256 hex digest

    def test_skips_checksum_when_disabled(self, tmp_path: Path) -> None:
        """write_checksum=False skips checksum file creation."""
        target = tmp_path / "nocs.json"
        atomic_write(target, {"a": 1}, write_checksum=False)
        cs_path = target.with_suffix(target.suffix + ".sha256")
        assert not cs_path.exists()

    def test_cleanup_on_failure(self, tmp_path: Path) -> None:
        """Temp file is cleaned up if the write fails."""
        target = tmp_path / "fail.json"
        # Force a write to a non-writable directory
        with patch.object(Path, "mkdir", side_effect=PermissionError("Denied")):
            with pytest.raises(PermissionError):
                atomic_write(target, {"data": "value"})
        # Target should not exist
        assert not target.exists()


class TestSafeRead:
    """safe_read() read-back with checksum verification."""

    def test_reads_valid_json(self, tmp_path: Path) -> None:
        """Normal JSON file is read correctly."""
        target = tmp_path / "data.json"
        data = {"hello": "world", "num": 42}
        atomic_write(target, data)
        result = safe_read(target)
        assert result == data

    def test_raises_on_missing_file(self, tmp_path: Path) -> None:
        """Non-existent file raises FileNotFoundError."""
        with pytest.raises(FileNotFoundError):
            safe_read(tmp_path / "nonexistent.json")

    def test_raises_on_invalid_json(self, tmp_path: Path) -> None:
        """Invalid JSON content raises JSONDecodeError."""
        target = tmp_path / "invalid.json"
        target.write_text("{bad json")
        with pytest.raises(json.JSONDecodeError):
            safe_read(target)

    def test_raises_on_checksum_mismatch(self, tmp_path: Path) -> None:
        """Corrupted data with checksum raises ValueError."""
        target = tmp_path / "corrupt.json"
        atomic_write(target, {"original": "data"})
        # Tamper with the file content
        target.write_text(json.dumps({"tampered": "data"}))
        with pytest.raises(ValueError, match="Checksum mismatch"):
            safe_read(target)

    def test_skips_checksum_when_no_file(self, tmp_path: Path) -> None:
        """No checksum file means no verification (silent pass)."""
        target = tmp_path / "nocs.json"
        target.write_text(json.dumps({"key": "val"}))
        result = safe_read(target)
        assert result == {"key": "val"}


class TestCheckWritable:
    """_check_writable() pre-write permission check."""

    def test_writable_directory_passes(self, tmp_path: Path) -> None:
        """Writable directory doesn't raise."""
        _check_writable(tmp_path / "test.json")  # should not raise

    def test_raises_on_non_writable(self, tmp_path: Path) -> None:
        """Read-only directory raises PermissionError."""
        readonly = tmp_path / "readonly"
        readonly.mkdir(mode=0o444)
        with pytest.raises(PermissionError):
            _check_writable(readonly / "test.json")


class TestVerifyChecksum:
    """_verify_checksum() corruption detection."""

    def test_missing_checksum_file_returns_true(self, tmp_path: Path) -> None:
        """No checksum file = no corruption check = True."""
        result = _verify_checksum(tmp_path / "nonexistent.json", "content")
        assert result is True

    def test_valid_checksum_returns_true(self, tmp_path: Path) -> None:
        """Matching checksum returns True."""
        target = tmp_path / "valid.json"
        target.write_text("hello")
        _write_checksum(target, "hello")
        assert _verify_checksum(target, "hello") is True

    def test_invalid_checksum_returns_false(self, tmp_path: Path) -> None:
        """Mismatched checksum returns False."""
        target = tmp_path / "invalid.json"
        target.write_text("original content")
        _write_checksum(target, "original content")
        assert _verify_checksum(target, "different content") is False


class TestFileLock:
    """FileLock context manager."""

    def test_lock_acquire_and_release(self, tmp_path: Path) -> None:
        """Lock can be acquired and released without error."""
        lock_path = tmp_path / "test.lock"
        with FileLock(lock_path, timeout=1.0):
            assert lock_path.exists()
        # After the context manager exits, the lock file remains (os.open
        # creates it), but the lock is released.

    def test_timeout_raises(self, tmp_path: Path) -> None:
        """Lock timeout raises TimeoutError."""
        lock_path = tmp_path / "timeout.lock"
        # Acquire the lock in an outer block
        fd = os.open(str(lock_path), os.O_CREAT | os.O_RDWR, 0o600)
        try:
            import fcntl

            fcntl.flock(fd, fcntl.LOCK_EX)
            # Try to acquire the already-held lock with a short timeout
            with pytest.raises(TimeoutError):
                with FileLock(lock_path, timeout=0.1):
                    pass
        finally:
            fcntl.flock(fd, fcntl.LOCK_UN)
            os.close(fd)


class TestColorHelpers:
    """c() and strip_ansi() color helpers."""

    def test_c_wraps_in_color(self) -> None:
        """c() wraps message in color when NO_COLOR is not set."""
        from claude_launcher.utils import C, c

        result = c(C.GREEN, "hello")
        assert result.startswith("\033[")
        assert result.endswith(C.NC)
        assert "hello" in result

    def test_c_strips_color_when_no_color(self) -> None:
        """c() returns plain message when NO_COLOR is set."""
        from claude_launcher.utils import c

        with patch.dict("os.environ", {"NO_COLOR": "1"}):
            # Need to re-evaluate NO_COLOR; simulate by clearing cached value
            import claude_launcher.utils as u

            orig = u.NO_COLOR
            u.NO_COLOR = True
            try:
                result = c("", "plain")
                assert result == "plain"
            finally:
                u.NO_COLOR = orig

    def test_strip_ansi_removes_escapes(self) -> None:
        """strip_ansi() removes all ANSI sequences."""
        from claude_launcher.utils import strip_ansi

        colored = "\033[0;32mhello\033[0m"
        assert strip_ansi(colored) == "hello"

    def test_strip_ansi_passes_plain_text(self) -> None:
        """strip_ansi() leaves plain text unchanged."""
        from claude_launcher.utils import strip_ansi

        assert strip_ansi("hello world") == "hello world"
