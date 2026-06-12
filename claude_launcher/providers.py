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
from typing import Any, Dict

from claude_launcher.config import PROVIDERS_FILE
from claude_launcher.logger import get_logger
from claude_launcher.utils import C

logger = get_logger("providers")


class ProviderConfigError(Exception):
    """Raised when a provider's env var ($VAR ref) can't be resolved."""


def _validate_provider_structure(data: Any) -> Dict[str, Any]:
    """Validate that loaded provider data has the expected shape.

    Ensures the top-level structure is a dict with a 'providers' key
    containing a dict of provider name to config. Returns the providers
    dict on success, raises TypeError on invalid structure.
    """
    if not isinstance(data, dict):
        raise TypeError(
            f"providers.json root must be a dict, got {type(data).__name__}"
        )
    providers = data.get("providers", {})
    if not isinstance(providers, dict):
        raise TypeError(
            f"providers.json 'providers' must be a dict, "
            f"got {type(providers).__name__}"
        )
    return providers


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
    logger.debug("resolving provider config: %s", name)
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
        logger.debug("providers.json not found, returning empty")
        return {}
    logger.debug("loading providers from %s", PROVIDERS_FILE)
    try:
        data = json.loads(PROVIDERS_FILE.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, IOError) as e:
        print(
            f"  {C.RED}Error: providers.json is invalid: {e}{C.NC}",
            file=sys.stderr,
        )
        sys.exit(1)

    # Validate top-level structure before accessing fields
    try:
        providers = _validate_provider_structure(data)
    except TypeError as e:
        print(
            f"  {C.RED}Error: providers.json structure is invalid: {e}{C.NC}",
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

    return providers
