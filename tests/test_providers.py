"""Tests for the providers module — schema validation, loading, and VAR resolution."""

import json
from pathlib import Path
from typing import Any
from unittest.mock import patch

import jsonschema
import pytest

from claude_launcher.providers import (
    ProviderConfigError,
    _resolve_env_value,
    _validate_env_value,
    _validate_provider_structure,
    _validate_with_schema,
    load_providers,
)


class TestValidateProviderStructure:
    """_validate_provider_structure() shape validation."""

    def test_valid_structure(self) -> None:
        """Normal provider data passes validation."""
        result = _validate_provider_structure(
            {"providers": {"Deepseek": {"env": {"KEY": "val"}}}}
        )
        assert result == {"Deepseek": {"env": {"KEY": "val"}}}

    def test_empty_providers(self) -> None:
        """Empty providers dict is valid."""
        result = _validate_provider_structure({"providers": {}})
        assert result == {}

    def test_no_providers_key(self) -> None:
        """Missing providers key returns empty dict."""
        result = _validate_provider_structure({})
        assert result == {}

    def test_root_not_dict(self) -> None:
        """Non-dict root raises TypeError."""
        with pytest.raises(TypeError, match="root must be a dict"):
            _validate_provider_structure([])

    def test_providers_not_dict(self) -> None:
        """Non-dict providers key raises TypeError."""
        with pytest.raises(TypeError, match="'providers' must be a dict"):
            _validate_provider_structure({"providers": []})


class TestValidateEnvValue:
    """_validate_env_value() suspicious character detection."""

    def test_clean_value(self) -> None:
        """Normal values pass validation."""
        assert _validate_env_value("sk-abc123") is True

    def test_semicolon_suspicious(self) -> None:
        """Semicolons are flagged."""
        result = _validate_env_value("key; rm -rf /", context="test")
        assert result is False

    def test_backtick_suspicious(self) -> None:
        """Backticks are flagged."""
        result = _validate_env_value("`malicious`", context="test")
        assert result is False

    def test_pipe_suspicious(self) -> None:
        """Pipes are flagged."""
        result = _validate_env_value("key|other", context="test")
        assert result is False


class TestResolveEnvValue:
    """_resolve_env_value() environment variable resolution."""

    def test_plain_value_returned_as_is(self) -> None:
        """Values not starting with $ are returned unchanged."""
        assert _resolve_env_value("hello", "test") == "hello"

    def test_resolves_env_var(self) -> None:
        """$VAR is resolved from the environment."""
        with patch.dict("os.environ", {"TEST_VAR": "resolved_value"}):
            assert _resolve_env_value("$TEST_VAR", "test") == "resolved_value"

    def test_missing_var_raises(self) -> None:
        """Missing $VAR raises ProviderConfigError."""
        with pytest.raises(ProviderConfigError):
            _resolve_env_value("$NONEXISTENT_VAR_12345", "test")


class TestResolveProviderCfg:
    """_resolve_provider_cfg() end-to-end."""

    def test_resolves_with_models(self) -> None:
        """Provider with models has env vars resolved."""
        from claude_launcher.providers import _resolve_provider_cfg

        cfg: dict[str, Any] = {
            "env": {"BASE_URL": "https://example.com"},
            "models": [
                {"name": "M1", "env": {"MODEL": "m1"}},
                {"name": "M2"},
            ],
        }
        with patch.dict("os.environ", {}, clear=True):
            # Without env vars, it should fail for $VAR refs
            # But with plain values, it should pass
            _resolve_provider_cfg("test", cfg)
            assert cfg["env"]["BASE_URL"] == "https://example.com"
            assert cfg["models"][0]["env"]["MODEL"] == "m1"


class TestValidateWithSchema:
    """_validate_with_schema() JSON Schema compliance."""

    def test_valid_provider_data_passes(self) -> None:
        """Valid v2 provider data passes schema validation."""
        data = {
            "version": 2,
            "providers": {
                "TestProvider": {
                    "env": {
                        "ANTHROPIC_BASE_URL": "https://api.example.com",
                        "ANTHROPIC_AUTH_TOKEN": "$API_KEY",
                    }
                }
            },
        }
        # Should not raise
        _validate_with_schema(data)

    def test_missing_providers_fails(self) -> None:
        """Missing 'providers' key fails schema validation."""
        data = {"version": 2}
        with pytest.raises(jsonschema.ValidationError):
            _validate_with_schema(data)

    def test_missing_env_fails(self) -> None:
        """Provider without 'env' key fails schema validation."""
        data = {
            "version": 2,
            "providers": {"TestProvider": {}},
        }
        with pytest.raises(jsonschema.ValidationError):
            _validate_with_schema(data)

    def test_invalid_version_fails(self) -> None:
        """Non-integer version fails schema validation."""
        data = {
            "version": "three",
            "providers": {"TestProvider": {"env": {"KEY": "val"}}},
        }
        with pytest.raises(jsonschema.ValidationError):
            _validate_with_schema(data)

    def test_numeric_env_values_passes(self) -> None:
        """Env values that are numeric strings are valid."""
        data = {
            "version": 2,
            "providers": {
                "TestProvider": {
                    "env": {
                        "TIMEOUT": "30",
                        "RETRIES": "3",
                    }
                }
            },
        }
        _validate_with_schema(data)

    def test_skips_when_schema_missing(self) -> None:
        """Missing schema file skips validation silently."""
        with patch(
            "claude_launcher.providers._SCHEMA_PATH",
            Path("/tmp/nonexistent_schema.json"),
        ):
            _validate_with_schema({"providers": {}})  # should not raise

    def test_models_with_env_passes(self) -> None:
        """Provider with models array passes validation."""
        data = {
            "version": 2,
            "providers": {
                "TestProvider": {
                    "env": {"BASE_URL": "https://example.com"},
                    "models": [
                        {"name": "Model A", "env": {"MODEL": "a"}},
                        {"name": "Model B"},
                    ],
                }
            },
        }
        _validate_with_schema(data)


class TestLoadProviders:
    """load_providers() end-to-end."""

    def test_returns_empty_when_no_file(self) -> None:
        """Missing providers.json returns empty dict."""
        with patch(
            "claude_launcher.providers.PROVIDERS_FILE",
            Path("/tmp/nonexistent_providers.json"),
        ):
            result = load_providers()
            assert result == {}

    def test_loads_valid_file(self, tmp_path: Path) -> None:
        """Valid providers.json loads successfully."""
        providers_file = tmp_path / "providers.json"
        providers_file.write_text(
            json.dumps(
                {
                    "version": 2,
                    "providers": {
                        "TestProvider": {
                            "env": {"KEY": "value"},
                        }
                    },
                }
            )
        )
        with patch("claude_launcher.providers.PROVIDERS_FILE", providers_file):
            result = load_providers()
            assert "TestProvider" in result
            assert result["TestProvider"]["env"]["KEY"] == "value"

    def test_invalid_json_exits(self, tmp_path: Path) -> None:
        """Invalid JSON causes sys.exit(1)."""
        providers_file = tmp_path / "providers.json"
        providers_file.write_text("not valid json{{{")
        with patch("claude_launcher.providers.PROVIDERS_FILE", providers_file):
            with pytest.raises(SystemExit) as exc:
                load_providers()
            assert exc.value.code == 1
