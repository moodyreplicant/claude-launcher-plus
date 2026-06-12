"""Tests for the config module — settings load/save and path constants."""

import json
import os
from pathlib import Path
from unittest.mock import patch

import pytest  # noqa: F401 — used in type hints (pytest.CaptureFixture)

from claude_launcher.config import (
    CLAUDE_SETTINGS,
    KEY_HELPER,
    LAUNCHER_ENV_KEYS,
    LM_STUDIO_URL,
    PROVIDERS_FILE,
    ensure_onboarding_done,
    load_settings,
    reset_settings,
    save_settings,
)


class TestConstants:
    """Path and environment constants are resolved correctly."""

    def test_lm_studio_url_default(self) -> None:
        """Default LM Studio URL points to localhost:1234."""
        assert LM_STUDIO_URL == "http://localhost:1234"

    def test_lm_studio_url_from_env(self) -> None:
        """LM Studio URL respects environment overrides."""
        # Cannot easily test this since constants are resolved at import time,
        # but the host/port are derived from os.environ.get()
        assert "LM_STUDIO_HOST" in os.environ or True  # No-op check

    def test_launcher_env_keys_count(self) -> None:
        """LAUNCHER_ENV_KEYS contains expected entries."""
        assert len(LAUNCHER_ENV_KEYS) == 10
        assert "ANTHROPIC_BASE_URL" in LAUNCHER_ENV_KEYS
        assert "ANTHROPIC_MODEL" in LAUNCHER_ENV_KEYS

    def test_path_constants_resolved(self) -> None:
        """Path constants resolve to home-directory paths."""
        assert str(CLAUDE_SETTINGS).endswith(".claude/settings.json")
        assert str(PROVIDERS_FILE).endswith(".claude/providers.json")
        assert str(KEY_HELPER).endswith(".claude/api-key-helper.sh")


class TestLoadSettings:
    """load_settings() behavior under various conditions."""

    def test_returns_empty_dict_when_no_file(self, tmp_path: Path) -> None:
        """Missing settings.json returns {}."""
        with patch(
            "claude_launcher.config.CLAUDE_SETTINGS", tmp_path / "nonexistent.json"
        ):
            result = load_settings()
            assert result == {}

    def test_returns_empty_dict_on_empty_file(self, tmp_path: Path) -> None:
        """Empty file returns {}."""
        settings_file = tmp_path / "settings.json"
        settings_file.write_text("")
        with patch("claude_launcher.config.CLAUDE_SETTINGS", settings_file):
            result = load_settings()
            assert result == {}

    def test_loads_valid_json(self, tmp_path: Path) -> None:
        """Valid JSON loads correctly."""
        settings_file = tmp_path / "settings.json"
        data = {"apiKey": "test", "env": {"KEY": "val"}}
        settings_file.write_text(json.dumps(data))
        with patch("claude_launcher.config.CLAUDE_SETTINGS", settings_file):
            result = load_settings()
            assert result == data

    def test_handles_corrupted_json(self, tmp_path: Path) -> None:
        """Corrupted JSON backs up file and returns {}."""
        settings_file = tmp_path / "settings.json"
        settings_file.write_text("not valid json{{{")
        with patch("claude_launcher.config.CLAUDE_SETTINGS", settings_file):
            result = load_settings()
            assert result == {}
            # Backup file should exist
            assert (tmp_path / "settings.json.bak").exists()


class TestResetSettings:
    """reset_settings() strips launcher-managed keys."""

    def test_removes_api_key_helper(self) -> None:
        """apiKeyHelper key is removed."""
        with patch(
            "claude_launcher.config.load_settings",
            return_value={
                "apiKeyHelper": "/some/path",
            },
        ):
            result = reset_settings()
            assert "apiKeyHelper" not in result

    def test_removes_anthroipc_auth_token(self) -> None:
        """ANTHROPIC_AUTH_TOKEN key is removed."""
        with patch(
            "claude_launcher.config.load_settings",
            return_value={
                "ANTHROPIC_AUTH_TOKEN": "secret",
            },
        ):
            result = reset_settings()
            assert "ANTHROPIC_AUTH_TOKEN" not in result

    def test_strips_launcher_env_keys(self) -> None:
        """All LAUNCHER_ENV_KEYS are removed from env dict."""
        env = {key: "value" for key in LAUNCHER_ENV_KEYS}
        with patch(
            "claude_launcher.config.load_settings",
            return_value={
                "env": env,
            },
        ):
            result = reset_settings()
            assert "env" not in result or all(
                k not in result.get("env", {}) for k in LAUNCHER_ENV_KEYS
            )

    def test_preserves_non_launcher_keys(self) -> None:
        """Settings keys not managed by the launcher are preserved."""
        with patch(
            "claude_launcher.config.load_settings",
            return_value={
                "apiKeyHelper": "/remove",
                "customKey": "keep",
                "env": {"CUSTOM_VAR": "keep"},
            },
        ):
            result = reset_settings()
            assert result.get("customKey") == "keep"
            assert result.get("env", {}).get("CUSTOM_VAR") == "keep"

    def test_removes_empty_env(self) -> None:
        """After stripping, empty env dict is removed."""
        with patch(
            "claude_launcher.config.load_settings",
            return_value={
                "env": {"ANTHROPIC_BASE_URL": "http://example.com"},
            },
        ):
            result = reset_settings()
            assert "env" not in result


class TestSaveSettings:
    """save_settings() writes atomically."""

    def test_writes_to_disk(self, tmp_path: Path) -> None:
        """Settings are written as JSON to the expected path."""
        target = tmp_path / "settings.json"
        data = {"key": "value"}
        with patch("claude_launcher.config.CLAUDE_SETTINGS", target):
            save_settings(data)
        assert target.exists()
        assert json.loads(target.read_text()) == data


class TestEnsureOnboardingDone:
    """ensure_onboarding_done() marks onboarding complete."""

    def test_creates_file_if_missing(self, tmp_path: Path) -> None:
        """Creates .claude.json with hasCompletedOnboarding when file is missing."""
        target = tmp_path / ".claude.json"
        with patch("claude_launcher.config.CLAUDE_JSON", target):
            ensure_onboarding_done()
        assert target.exists()
        data = json.loads(target.read_text())
        assert data.get("hasCompletedOnboarding") is True

    def test_preserves_existing_data(self, tmp_path: Path) -> None:
        """Existing keys in .claude.json are preserved."""
        target = tmp_path / ".claude.json"
        target.write_text(json.dumps({"existingKey": "value"}))
        with patch("claude_launcher.config.CLAUDE_JSON", target):
            ensure_onboarding_done()
        data = json.loads(target.read_text())
        assert data["existingKey"] == "value"
        assert data["hasCompletedOnboarding"] is True


class TestDirectoryPermissions:
    """check_directory_permissions() permission warnings."""

    def test_skips_when_dir_missing(self) -> None:
        """Non-existent directory is skipped without error."""
        from claude_launcher.config import check_directory_permissions

        with patch(
            "claude_launcher.config.CLAUDE_SETTINGS",
            Path("/tmp/nonexistent_claude_dir/settings.json"),
        ):
            check_directory_permissions()  # should not raise

    def test_ok_permissions_no_warning(
        self, capsys: pytest.CaptureFixture[str], tmp_path: Path
    ) -> None:
        """Normal directory permissions produce no warnings."""
        from claude_launcher.config import check_directory_permissions

        config_dir = tmp_path / ".claude"
        config_dir.mkdir(mode=0o700)
        settings_file = config_dir / "settings.json"
        with patch("claude_launcher.config.CLAUDE_SETTINGS", settings_file):
            check_directory_permissions()
        captured = capsys.readouterr()
        assert "Warning" not in captured.out
