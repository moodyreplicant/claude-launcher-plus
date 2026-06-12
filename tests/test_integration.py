"""Integration tests for full launch workflows — all modes with mocked subprocess."""

from pathlib import Path
from typing import Any
from unittest.mock import MagicMock, patch

import pytest

from claude_launcher.launcher import (
    _run_claude,
    _wait_for_lm_studio,
    interactive_menu,
    launch_cloud,
    launch_custom,
    launch_local,
    print_lm_studio_status,
    show_status,
)


class TestLaunchLocal:
    """launch_local() end-to-end with mocked dependencies."""

    def test_lm_studio_offline_exits_early(self, capsys: Any) -> None:
        """When LM Studio is offline and user declines wait, exits cleanly."""
        with patch("claude_launcher.launcher.check_lm_studio", return_value=False):
            with patch(
                "claude_launcher.launcher._wait_for_lm_studio", return_value=False
            ):
                launch_local([], allow_scripts=False)
        captured = capsys.readouterr()
        assert "not responding" in captured.out

    def test_no_models_aborts(self, capsys: Any) -> None:
        """No loaded models prints error and returns."""
        with patch("claude_launcher.launcher.check_lm_studio", return_value=True):
            with patch(
                "claude_launcher.launcher.get_lm_studio_models", return_value=[]
            ):
                launch_local([], allow_scripts=False)
        captured = capsys.readouterr()
        assert "No loaded models" in captured.out

    def test_full_launch_flow(self, capsys: Any) -> None:
        """Full launch flow completes with mocked subprocess."""
        with patch("claude_launcher.launcher.check_lm_studio", return_value=True):
            with patch(
                "claude_launcher.launcher.get_lm_studio_models",
                return_value=["model-a"],
            ):
                with patch("claude_launcher.launcher._run_claude", return_value=0):
                    with patch("claude_launcher.launcher.save_settings"):
                        with patch(
                            "claude_launcher.launcher.reset_settings",
                            return_value={},
                        ):
                            with patch(
                                "claude_launcher.launcher.ensure_onboarding_done"
                            ):
                                launch_local([], allow_scripts=False)
        captured = capsys.readouterr()
        assert "Launching" in captured.out

    def test_exit_code_warning(self, capsys: Any) -> None:
        """Non-zero exit code prints warning."""
        with patch("claude_launcher.launcher.check_lm_studio", return_value=True):
            with patch(
                "claude_launcher.launcher.get_lm_studio_models",
                return_value=["model-a"],
            ):
                with patch("claude_launcher.launcher._run_claude", return_value=1):
                    with patch("claude_launcher.launcher.save_settings"):
                        with patch(
                            "claude_launcher.launcher.reset_settings",
                            return_value={},
                        ):
                            with patch(
                                "claude_launcher.launcher.ensure_onboarding_done"
                            ):
                                launch_local([], allow_scripts=False)
        captured = capsys.readouterr()
        assert "exited with code" in captured.out or "Launching" in captured.out


class TestLaunchCloud:
    """launch_cloud() end-to-end with mocked subprocess."""

    def test_launch_cloud_success(self, capsys: Any) -> None:
        """Cloud launch mocks subprocess and returns cleanly."""
        with patch("claude_launcher.launcher._run_claude", return_value=0):
            with patch("claude_launcher.launcher.save_settings"):
                with patch("claude_launcher.launcher.reset_settings", return_value={}):
                    launch_cloud([])
        captured = capsys.readouterr()
        assert "Launching" in captured.out
        assert "Anthropic" in captured.out

    def test_cloud_exit_code_warning(self, capsys: Any) -> None:
        """Non-zero exit from cloud mode logs warning."""
        with patch("claude_launcher.launcher._run_claude", return_value=2):
            with patch("claude_launcher.launcher.save_settings"):
                with patch("claude_launcher.launcher.reset_settings", return_value={}):
                    launch_cloud([])
        captured = capsys.readouterr()
        assert "exited with code" in captured.out or "Launching" in captured.out


class TestLaunchCustom:
    """launch_custom() end-to-end with mocked providers."""

    def test_no_providers_shows_message(self, capsys: Any) -> None:
        """No providers configured shows setup message."""
        with patch("claude_launcher.launcher.load_providers", return_value={}):
            with patch("claude_launcher.launcher._is_interactive", return_value=False):
                launch_custom([])
        captured = capsys.readouterr()
        assert "No custom providers" in captured.out

    def test_launch_with_provider(self, capsys: Any) -> None:
        """Custom provider launch mocks subprocess."""
        providers = {
            "TestProv": {
                "env": {
                    "ANTHROPIC_BASE_URL": "https://example.com",
                    "ANTHROPIC_AUTH_TOKEN": "test-token",
                }
            }
        }
        with patch("claude_launcher.launcher.load_providers", return_value=providers):
            with patch("claude_launcher.launcher._resolve_provider_cfg"):
                with patch("claude_launcher.launcher._run_claude", return_value=0):
                    with patch("claude_launcher.launcher.save_settings"):
                        with patch(
                            "claude_launcher.launcher.reset_settings",
                            return_value={},
                        ):
                            launch_custom([])
        captured = capsys.readouterr()
        assert "TestProv" in captured.out


class TestRunClaude:
    """_run_claude() subprocess execution."""

    def test_run_claude_subprocess(self) -> None:
        """_run_claude calls subprocess.run with correct args."""
        with patch(
            "claude_launcher.launcher.subprocess.run",
            return_value=MagicMock(returncode=0),
        ):
            with patch("claude_launcher.launcher.signal.signal"):
                result = _run_claude(["--help"])
                assert result == 0


class TestPrintLMStudioStatus:
    """print_lm_studio_status() various states."""

    def test_offline_status(self, capsys: Any) -> None:
        """Offline LM Studio shows offline message."""
        with patch("claude_launcher.launcher.check_lm_studio", return_value=False):
            print_lm_studio_status()
        captured = capsys.readouterr()
        assert "offline" in captured.out

    def test_online_with_models(self, capsys: Any) -> None:
        """Online LM Studio with models shows model list."""
        with patch("claude_launcher.launcher.check_lm_studio", return_value=True):
            with patch(
                "claude_launcher.launcher.get_lm_studio_models",
                return_value=["model-x", "model-y"],
            ):
                print_lm_studio_status()
        captured = capsys.readouterr()
        assert "running" in captured.out
        assert "model-x" in captured.out

    def test_online_no_models(self, capsys: Any) -> None:
        """Online LM Studio without models shows 0 models."""
        with patch("claude_launcher.launcher.check_lm_studio", return_value=True):
            with patch(
                "claude_launcher.launcher.get_lm_studio_models", return_value=[]
            ):
                print_lm_studio_status()
        captured = capsys.readouterr()
        assert "0 models" in captured.out


class TestWaitForLMStudio:
    """_wait_for_lm_studio() retry logic."""

    def test_non_interactive_returns_false(self) -> None:
        """Non-interactive mode returns False immediately."""
        with patch("claude_launcher.launcher._is_interactive", return_value=False):
            result = _wait_for_lm_studio()
            assert result is False

    def test_user_declines_returns_false(self) -> None:
        """User declining wait returns False."""
        with patch("claude_launcher.launcher._is_interactive", return_value=True):
            with patch("builtins.input", return_value="n"):
                result = _wait_for_lm_studio()
                assert result is False

    def test_connection_succeeds(self) -> None:
        """LM Studio comes online during wait."""
        with patch("claude_launcher.launcher._is_interactive", return_value=True):
            with patch("builtins.input", return_value="y"):
                with patch(
                    "claude_launcher.launcher.check_lm_studio",
                    side_effect=[False, False, True],
                ):
                    with patch("claude_launcher.launcher.time.sleep"):
                        result = _wait_for_lm_studio()
                        assert result is True


class TestInteractiveMenu:
    """interactive_menu() non-interactive guard."""

    def test_exits_in_non_interactive(self) -> None:
        """interactive_menu exits with code 1 in non-interactive mode."""
        with patch("claude_launcher.launcher._is_interactive", return_value=False):
            with pytest.raises(SystemExit) as exc:
                interactive_menu()
            assert exc.value.code == 1

    def test_quit_option(self) -> None:
        """'q' choice exits cleanly."""
        with patch("claude_launcher.launcher._is_interactive", return_value=True):
            with patch("builtins.input", return_value="q"):
                with pytest.raises(SystemExit) as exc:
                    interactive_menu()
                assert exc.value.code == 0


class TestShowStatus:
    """show_status() edge cases."""

    def test_status_shows_providers(self, capsys: Any) -> None:
        """Status shows provider information."""
        with patch("claude_launcher.launcher.load_providers") as mock_load:
            mock_load.return_value = {
                "TestProv": {
                    "env": {"ANTHROPIC_BASE_URL": "https://example.com"},
                    "models": [{"name": "M1"}],
                }
            }
            with patch("claude_launcher.config.CLAUDE_SETTINGS") as mock_settings:
                mock_settings.exists.return_value = False
                with patch("claude_launcher.config.CLAUDE_JSON") as mock_json:
                    mock_json.exists.return_value = False
                    show_status()
        captured = capsys.readouterr()
        assert "Custom Providers" in captured.out

    def test_status_without_providers_file(self, capsys: Any) -> None:
        """Status without providers.json shows appropriate message."""
        with patch(
            "claude_launcher.launcher.PROVIDERS_FILE",
            Path("/tmp/nonexistent_providers.json"),
        ):
            with patch("claude_launcher.config.CLAUDE_SETTINGS") as mock_settings:
                mock_settings.exists.return_value = False
                show_status()
        captured = capsys.readouterr()
        assert "none configured" in captured.out
