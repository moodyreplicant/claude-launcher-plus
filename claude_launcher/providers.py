"""Provider configuration management for claude-launcher-plus.

Handles loading providers.json and resolving $VAR environment variable
references at launch time.
"""

__all__ = [
    "ProviderConfigError",
    "load_providers",
]

import json
import os
import sys
from typing import Any, Dict, cast

from claude_launcher.config import PROVIDERS_FILE
from claude_launcher.utils import C


class ProviderConfigError(Exception):
    """Raised when a provider's env var ($VAR ref) can't be resolved."""


def _resolve_env_value(value: str, provider_name: str) -> str:
    """Resolve $VAR / ${VAR} from the environment.

    Raises ProviderConfigError if the variable is not set.
    Returns the value unchanged if it doesn't start with '$'.
    """
    if not isinstance(value, str) or not value.startswith("$"):
        return value
    var = value[1:].strip("{}")
    if var not in os.environ:
        print(
            f"\n  {C.RED}Env var '{var}' is not set.{C.NC}",
            file=sys.stderr,
        )
        print(
            f"  Required by '{C.BOLD}{provider_name}{C.NC}'.",
            file=sys.stderr,
        )
        print(
            f"  Add 'export {var}=<key>' to your shell config.\n",
            file=sys.stderr,
        )
        raise ProviderConfigError(f"Env var '{var}' is not set")
    return os.environ[var]


def _resolve_provider_cfg(name: str, cfg: Dict[str, Any]) -> None:
    """Resolve $VAR refs in a single provider's env (mutates in place).

    Raises ProviderConfigError if any env var can't be resolved.
    Only called at launch time — not during read-only operations like status.
    """
    if "env" in cfg:
        cfg["env"] = {k: _resolve_env_value(v, name) for k, v in cfg["env"].items()}
    for model in cfg.get("models", []):
        if "env" in model:
            model["env"] = {
                k: _resolve_env_value(v, name) for k, v in model["env"].items()
            }


def load_providers() -> Dict[str, Any]:
    """Load and validate providers.json.

    Supports v1 (plaintext values) and v2 ($VAR references) formats.
    Returns empty dict if the file doesn't exist.
    Exits with code 1 on invalid JSON.
    """
    if not PROVIDERS_FILE.exists():
        return {}
    try:
        data = json.loads(PROVIDERS_FILE.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, IOError) as e:
        print(
            f"  {C.RED}Error: providers.json is invalid: {e}{C.NC}",
            file=sys.stderr,
        )
        sys.exit(1)

    # Version guard: coerce to int, warn on non-integer
    try:
        int(data.get("version", 1))  # validate, but value not yet used
    except (TypeError, ValueError):
        print(
            f"  {C.YELLOW}Warning: providers.json 'version' should be an integer"
            f" — treating as v1.{C.NC}",
            file=sys.stderr,
        )

    providers = data.get("providers", {})
    return cast(Dict[str, Any], providers)
