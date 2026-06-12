"""Tests for the CLI entry point — argument parsing and dispatch."""

import sys
from unittest.mock import patch

import pytest

from claude_launcher.cli import main


class TestCliParsing:
    """Argument parsing smoke tests."""

    def test_version_flag(self) -> None:
        """--version prints version and exits."""
        with patch.object(sys, "argv", ["claude-launcher-plus", "--version"]):
            with pytest.raises(SystemExit) as exc:
                main()
            assert exc.value.code == 0

    def test_version_flag_short(self) -> None:
        """-V prints version and exits."""
        with patch.object(sys, "argv", ["claude-launcher-plus", "-V"]):
            with pytest.raises(SystemExit) as exc:
                main()
            assert exc.value.code == 0

    def test_dry_run_local(self, capsys: pytest.CaptureFixture[str]) -> None:
        """--dry-run local runs validation without launching."""
        with patch.object(sys, "argv", ["claude-launcher-plus", "--dry-run", "local"]):
            main()
        captured = capsys.readouterr()
        assert "Dry-run validation" in captured.out

    def test_dry_run_cloud(self, capsys: pytest.CaptureFixture[str]) -> None:
        """--dry-run cloud runs validation."""
        with patch.object(sys, "argv", ["claude-launcher-plus", "--dry-run", "cloud"]):
            main()
        captured = capsys.readouterr()
        assert "Dry-run validation" in captured.out

    def test_dry_run_custom(self, capsys: pytest.CaptureFixture[str]) -> None:
        """--dry-run custom runs validation including providers check."""
        with patch.object(sys, "argv", ["claude-launcher-plus", "--dry-run", "custom"]):
            main()
        captured = capsys.readouterr()
        assert "Dry-run validation" in captured.out

    def test_status_command(self, capsys: pytest.CaptureFixture[str]) -> None:
        """'status' command produces output."""
        with patch.object(sys, "argv", ["claude-launcher-plus", "status"]):
            main()
        captured = capsys.readouterr()
        assert "Status" in captured.out

    def test_help(self, capsys: pytest.CaptureFixture[str]) -> None:
        """--help prints usage information."""
        with patch.object(sys, "argv", ["claude-launcher-plus", "--help"]):
            with pytest.raises(SystemExit) as exc:
                main()
            assert exc.value.code == 0
        captured = capsys.readouterr()
        assert "usage:" in captured.out

    def test_invalid_mode(self) -> None:
        """Invalid mode exits with code 2 (argparse error)."""
        with patch.object(sys, "argv", ["claude-launcher-plus", "invalid-mode"]):
            with pytest.raises(SystemExit) as exc:
                main()
            assert exc.value.code == 2

    def test_allow_scripts_flag(self, capsys: pytest.CaptureFixture[str]) -> None:
        """--allow-scripts flag is accepted without error."""
        with patch.object(
            sys, "argv", ["claude-launcher-plus", "--allow-scripts", "status"]
        ):
            main()
        captured = capsys.readouterr()
        assert "Status" in captured.out

    def test_non_interactive_flag(self, capsys: pytest.CaptureFixture[str]) -> None:
        """--non-interactive flag is accepted."""
        # Reset first
        import claude_launcher.utils as u
        from claude_launcher.utils import _is_interactive, set_non_interactive

        u.FORCE_NON_INTERACTIVE = False
        set_non_interactive()
        assert _is_interactive() is False
        u.FORCE_NON_INTERACTIVE = False

    def test_help_shows_allow_scripts(self) -> None:
        """--help output mentions --allow-scripts."""
        with patch.object(sys, "argv", ["claude-launcher-plus", "--help"]):
            with pytest.raises(SystemExit) as exc:
                main()
            assert exc.value.code == 0
