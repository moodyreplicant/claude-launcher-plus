"""Configuration management for claude-launcher-plus.

Handles loading and saving settings.json, .claude.json onboarding state,
and defines path constants for all Claude configuration files.
"""

__all__ = [
    "CLAUDE_JSON",
    "CLAUDE_SETTINGS",
    "PROVIDERS_FILE",
    "KEY_HELPER",
    "LM_STUDIO_URL",
    "LM_STUDIO_API_KEY",
    "LAUNCHER_ENV_KEYS",
    "load_settings",
    "reset_settings",
    "save_settings",
    "ensure_onboarding_done",
]

import json
import os
import shutil
import sys
from pathlib import Path
from typing import Any, Dict, cast

from claude_launcher.logger import get_logger
from claude_launcher.utils import C, atomic_write

logger = get_logger("config")

# -- Path constants --------------------------------------------------

CLAUDE_JSON = Path.home() / ".claude.json"
CLAUDE_SETTINGS = Path.home() / ".claude" / "settings.json"
PROVIDERS_FILE = Path.home() / ".claude" / "providers.json"
KEY_HELPER = Path.home() / ".claude" / "api-key-helper.sh"

# -- Environment-based configuration ---------------------------------

LM_STUDIO_HOST = os.environ.get("LM_STUDIO_HOST", "localhost")
LM_STUDIO_PORT = os.environ.get("LM_STUDIO_PORT", "1234")
LM_STUDIO_URL = f"http://{LM_STUDIO_HOST}:{LM_STUDIO_PORT}"
LM_STUDIO_API_KEY = os.environ.get("LM_STUDIO_API_KEY", "lm-studio")

LAUNCHER_ENV_KEYS: list[str] = [
    "ANTHROPIC_BASE_URL",
    "ANTHROPIC_MODEL",
    "ANTHROPIC_AUTH_TOKEN",
    "CLAUDE_CODE_DISABLE_NONESSENTIAL_TRAFFIC",
    "CLAUDE_CODE_ATTRIBUTION_HEADER",
    "CLAUDE_CODE_EFFORT_LEVEL",
    "ANTHROPIC_DEFAULT_OPUS_MODEL",
    "ANTHROPIC_DEFAULT_SONNET_MODEL",
    "ANTHROPIC_DEFAULT_HAIKU_MODEL",
    "OPENROUTER_API_KEY",
]


# -- Settings management ---------------------------------------------


def load_settings() -> Dict[str, Any]:
    """Load settings.json.

    On corruption: backs up to .bak, warns, and returns empty dict.
    Returns empty dict if the file doesn't exist.
    """
    if not CLAUDE_SETTINGS.exists():
        return {}
    try:
        with open(CLAUDE_SETTINGS, "r", encoding="utf-8") as f:
            return cast(Dict[str, Any], json.load(f))
    except (json.JSONDecodeError, IOError) as e:
        bak = Path(str(CLAUDE_SETTINGS) + ".bak")
        shutil.copy2(CLAUDE_SETTINGS, bak)
        logger.warning("settings.json corrupted: %s — backed up to %s", e, bak)
        print(
            f"  {C.YELLOW}Warning: settings.json corrupted ({e}){C.NC}",
            file=sys.stderr,
        )
        print(f"  Backup saved to {bak}", file=sys.stderr)
        return {}


def reset_settings() -> Dict[str, Any]:
    """Remove launcher-managed keys from settings.

    Returns the cleaned dict (does NOT write to disk).
    """
    d = load_settings()
    logger.debug("reset_settings: loaded %d top-level keys", len(d))
    d.pop("apiKeyHelper", None)
    d.pop("ANTHROPIC_AUTH_TOKEN", None)
    env = d.get("env")
    if isinstance(env, dict):
        for key in LAUNCHER_ENV_KEYS:
            env.pop(key, None)
        if not env:
            d.pop("env", None)
    return d


def save_settings(d: Dict[str, Any]) -> None:
    """Write settings dict to settings.json atomically.

    Raises TypeError if d is not a dict (catches programming errors early).
    """
    if not isinstance(d, dict):
        raise TypeError(f"save_settings expects a dict, got {type(d).__name__}")
    logger.info("saving settings (%d keys)", len(d))
    atomic_write(CLAUDE_SETTINGS, d)


def ensure_onboarding_done() -> None:
    """Mark hasCompletedOnboarding so Claude Code skips the first-run wizard."""
    d: Dict[str, Any] = {}
    if CLAUDE_JSON.exists():
        try:
            with open(CLAUDE_JSON, "r", encoding="utf-8") as f:
                d = json.load(f)
        except (json.JSONDecodeError, IOError):
            pass
    d["hasCompletedOnboarding"] = True
    CLAUDE_JSON.parent.mkdir(parents=True, exist_ok=True)
    atomic_write(CLAUDE_JSON, d)
