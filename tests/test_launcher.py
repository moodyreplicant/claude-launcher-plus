"""Tests for the launcher module — LM Studio client, launch helpers, status."""

from pathlib import Path
from unittest.mock import patch

import pytest

from claude_launcher.launcher import (
    _check_dep,
    _lm_studio_get,
    check_lm_studio,
    get_lm_studio_models,
    list_models,
    list_providers,
    show_status,
)


class TestCheckDep:
    """_check_dep() dependency detection."""

    def test_finds_existing_binary(self) -> None:
        """Known existing binary returns True."""
        # python3 should always be in PATH on the test runner
        assert _check_dep("python3") is True

    def test_returns_false_for_missing(self) -> None:
        """Non-existent binary returns False."""
        assert _check_dep("this-binary-does-not-exist-12345") is False


class TestLMStudioGet:
    """_lm_studio_get() HTTP client."""

    def test_returns_none_on_connection_error(self) -> None:
        """Connection refused returns None (not an exception)."""
        result = _lm_studio_get("/api/v1/models", timeout=1)
        assert result is None

    def test_check_lm_studio_offline(self) -> None:
        """check_lm_studio returns False when LM Studio is not running."""
        assert check_lm_studio() is False

    def test_get_models_empty_when_offline(self) -> None:
        """get_lm_studio_models returns empty list when offline."""
        assert get_lm_studio_models() == []


class TestStatus:
    """Status display functions produce output."""

    def test_show_status_runs(self, capsys: pytest.CaptureFixture[str]) -> None:
        """show_status() runs without error and produces output."""
        # Patch PROVIDERS_FILE to point to a non-existent path so status
        # doesn't depend on the real providers.json
        with patch(
            "claude_launcher.launcher.PROVIDERS_FILE",
            Path("/tmp/nonexistent_providers.json"),
        ):
            show_status()
        captured = capsys.readouterr()
        assert "Claude Code Launcher" in captured.out

    def test_list_providers_empty(self) -> None:
        """list_providers exits with code 1 when no providers."""
        with patch("claude_launcher.launcher.load_providers", return_value={}):
            with pytest.raises(SystemExit) as exc:
                list_providers()
            assert exc.value.code == 1

    def test_list_providers_with_data(self, capsys: pytest.CaptureFixture[str]) -> None:
        """list_providers prints provider names."""
        with patch(
            "claude_launcher.launcher.load_providers",
            return_value={
                "ProviderA": {},
                "ProviderB": {},
            },
        ):
            list_providers()
        captured = capsys.readouterr()
        assert "ProviderA" in captured.out
        assert "ProviderB" in captured.out

    def test_list_models_no_provider_exits(self) -> None:
        """list_models without provider name exits with code 1."""
        with pytest.raises(SystemExit) as exc:
            list_models("")
        assert exc.value.code == 1

    def test_list_models_missing_provider_exits(self) -> None:
        """list_models with unknown provider exits with code 1."""
        with patch("claude_launcher.launcher.load_providers", return_value={}):
            with pytest.raises(SystemExit) as exc:
                list_models("Nonexistent")
            assert exc.value.code == 1

    def test_list_models_with_data(self, capsys: pytest.CaptureFixture[str]) -> None:
        """list_models prints model info for a provider."""
        with patch(
            "claude_launcher.launcher.load_providers",
            return_value={
                "TestProvider": {
                    "models": [
                        {"name": "Model1", "env": {"ANTHROPIC_MODEL": "model-1"}},
                        {"name": "Model2", "env": {"ANTHROPIC_MODEL": "model-2"}},
                    ],
                },
            },
        ):
            list_models("TestProvider")
        captured = capsys.readouterr()
        assert "Model1" in captured.out
        assert "model-1" in captured.out
        assert "Model2" in captured.out
        assert "model-2" in captured.out


class TestLaunchHelpers:
    """Launch helper functions."""

    def test_launch_local_requires_no_connection(self) -> None:
        """launch_local returns cleanly when LM Studio is offline (no crash)."""
        from claude_launcher.launcher import launch_local

        # LM Studio is offline, so launch_local should print error and return
        # without blocking. We just verify it doesn't crash.
        launch_local([])


class TestCheckAllDeps:
    """check_all_deps() dependency reporting."""

    def test_returns_true_when_found(self) -> None:
        """check_all_deps returns True when all deps found."""
        from claude_launcher.launcher import check_all_deps

        result = check_all_deps(show_all=False)
        assert result is True

    def test_launch_cloud_requires_no_connection(self) -> None:
        """launch_cloud returns cleanly (confirmation skipped in non-TTY)."""
        from claude_launcher.launcher import launch_cloud

        # Non-TTY stdin means confirm_launch returns True automatically,
        # but then _run_claude will fail because 'claude' isn't available.
        # We mock _run_claude to prevent actual subprocess calls.
        with patch("claude_launcher.launcher._run_claude", return_value=0):
            with patch("claude_launcher.launcher.save_settings"):
                with patch("claude_launcher.launcher.reset_settings", return_value={}):
                    launch_cloud([])
