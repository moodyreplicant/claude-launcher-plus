"""Launch orchestration and LM Studio client for claude-launcher-plus.

Handles all launch modes (local, cloud, custom), LM Studio API communication,
status display, and the interactive menu.
"""

__all__ = [
    "launch_local",
    "launch_cloud",
    "launch_custom",
    "show_status",
    "list_providers",
    "list_models",
    "interactive_menu",
    "_run_claude",
    "_check_dep",
    "check_lm_studio",
    "get_lm_studio_models",
    "print_lm_studio_status",
    "check_all_deps",
]

import json
import os
import shlex
import shutil
import signal
import subprocess
import sys
import time
import urllib.error
import urllib.request
from typing import Any, Dict, List, Optional, cast

from claude_launcher.config import (
    CLAUDE_SETTINGS,
    KEY_HELPER,
    LM_STUDIO_API_KEY,
    LM_STUDIO_URL,
    PROVIDERS_FILE,
    ensure_onboarding_done,
    load_settings,
    reset_settings,
    save_settings,
)
from claude_launcher.logger import get_logger
from claude_launcher.providers import (
    ProviderConfigError,
    _resolve_provider_cfg,
    load_providers,
)
from claude_launcher.utils import (
    C,
    _is_interactive,
    confirm_launch,
    pick_from_list,
    sanitize_env_var_name,
    sanitize_provider_name,
    sanitize_url,
)

logger = get_logger("launcher")

# -- LM Studio client (stdlib urllib) --------------------------------


def _lm_studio_get(endpoint: str, timeout: int = 5) -> Optional[Dict[str, Any]]:
    """Make a GET request to LM Studio API and return parsed JSON."""
    try:
        req = urllib.request.Request(
            f"{LM_STUDIO_URL}{endpoint}",
            headers={"User-Agent": "claude-launcher-plus"},
        )
        with urllib.request.urlopen(req, timeout=timeout) as r:  # nosec B310
            return cast(Dict[str, Any], json.loads(r.read().decode()))
    except (urllib.error.URLError, OSError, json.JSONDecodeError):
        return None


def check_lm_studio() -> bool:
    """Check if LM Studio is responding at the configured URL."""
    return _lm_studio_get("/api/v1/models", timeout=2) is not None


def get_lm_studio_models() -> List[str]:
    """Return list of loaded LLM model keys from LM Studio."""
    data = _lm_studio_get("/api/v1/models", timeout=5)
    if not data:
        return []
    return [
        m["key"]
        for m in data.get("models", [])
        if m.get("type") == "llm" and len(m.get("loaded_instances", [])) > 0
    ]


def print_lm_studio_status() -> None:
    """Print LM Studio connection status to stdout."""
    if check_lm_studio():
        models = get_lm_studio_models()
        if models:
            print(
                f"  LM Studio:  {C.GREEN}● running{C.NC} at {LM_STUDIO_URL}"
                f" — {len(models)} model(s):"
                f" {C.BOLD}{', '.join(models)}{C.NC}"
            )
        else:
            print(
                f"  LM Studio:  {C.GREEN}● running{C.NC}"
                f" at {LM_STUDIO_URL} — 0 models loaded"
            )
    else:
        print(f"  LM Studio: {C.RED}● offline{C.NC} at {LM_STUDIO_URL}")


# -- Launch helpers --------------------------------------------------


def _wait_for_lm_studio() -> bool:
    """Retry loop — 60s deadline, user can abort."""
    if not _is_interactive():
        print(
            f"  {C.RED}LM Studio not running and stdin is not a TTY."
            f" Aborting.{C.NC}"
        )
        return False
    try:
        answer = input("  Wait and retry? (y/n) ").strip().lower()
    except (EOFError, KeyboardInterrupt):
        return False
    if answer not in ("y", "yes"):
        return False
    print("  Waiting for LM Studio...", end="", flush=True)
    deadline = time.monotonic() + 60
    while time.monotonic() < deadline:
        if check_lm_studio():
            print(f"\n  {C.GREEN}✓ Connected!{C.NC}")
            return True
        time.sleep(1)
        print(".", end="", flush=True)
    print(f"\n  {C.RED}Timed out after 60s. Start LM Studio and try again.{C.NC}")
    return False


# -- Launch modes ----------------------------------------------------


def _validate_string_list(val: Any, name: str = "claude_args") -> List[str]:
    """Validate that a value is a list of strings (runtime type guard)."""
    if not isinstance(val, list):
        raise TypeError(f"{name} must be a list, got {type(val).__name__}")
    for i, item in enumerate(val):
        if not isinstance(item, str):
            raise TypeError(f"{name}[{i}] must be a string, got {type(item).__name__}")
    return val


def _run_claude(
    claude_args: List[str],
    timeout: Optional[float] = None,
) -> int:
    """Launch claude subprocess.

    Restores default signal handlers so Ctrl+C reaches the child naturally.
    By default (timeout=None), waits indefinitely for the process to exit.
    Set timeout to a positive number of seconds to prevent hangs.
    """
    signal.signal(signal.SIGINT, signal.SIG_DFL)
    signal.signal(signal.SIGTERM, signal.SIG_DFL)
    cmd = ["claude"] + claude_args
    logger.info("launching claude subprocess: %s (timeout=%s)", cmd, timeout)
    try:
        return subprocess.run(cmd, timeout=timeout).returncode
    except subprocess.TimeoutExpired:
        logger.error("claude subprocess timed out after %s seconds", timeout)
        print(
            f"\n  {C.RED}Claude Code timed out after {timeout} seconds.{C.NC}",
            file=sys.stderr,
        )
        return -1


def _check_dep(name: str) -> bool:
    """Check if a command-line tool is available in PATH."""
    return shutil.which(name) is not None


# Known dependencies: binary name, purpose, install hint.
DEPENDENCIES: list[dict[str, str]] = [
    {
        "binary": "claude",
        "purpose": "Claude Code CLI (required for all launch modes)",
        "install": "https://docs.anthropic.com/en/docs/claude-code",
    },
]


def check_all_deps(show_all: bool = False) -> bool:
    """Check all known dependencies and report missing ones.

    Args:
        show_all: If True, show status for all deps (not just missing).

    Returns:
        True if all required dependencies are found.
    """
    all_found = True
    for dep in DEPENDENCIES:
        name = dep["binary"]
        found = _check_dep(name)
        if not found:
            all_found = False
            print(
                f"  {C.RED}✗ {name}: not found{C.NC}",
                file=sys.stderr,
            )
            print(
                f"    Needed for: {dep['purpose']}",
                file=sys.stderr,
            )
            print(
                f"    Install: {dep['install']}",
                file=sys.stderr,
            )
        elif show_all:
            print(f"  {C.GREEN}✓ {name}: found{C.NC}")
    return all_found


def launch_local(claude_args: List[str], allow_scripts: bool = False) -> None:
    """Launch Claude Code against a local LM Studio instance."""
    logger.info("local mode selected (allow_scripts=%s)", allow_scripts)
    print(f"{C.BLUE}{C.BOLD}🖥  Local Mode (LM Studio){C.NC}\n")
    if not check_lm_studio():
        print(f"{C.RED}✗ LM Studio not responding at {LM_STUDIO_URL}{C.NC}")
        print("  Make sure LM Studio is running and the server is started.")
        if not _wait_for_lm_studio():
            return
    print(f"{C.GREEN}✓ LM Studio is running{C.NC}\n")

    ensure_onboarding_done()
    CLAUDE_SETTINGS.parent.mkdir(parents=True, exist_ok=True)

    models = get_lm_studio_models()
    if not models:
        print(f"{C.RED}No loaded models found — aborting.{C.NC}")
        return
    idx = pick_from_list("Available LM Studio models", models)
    if idx is None:
        print(f"{C.RED}No loaded models found — aborting.{C.NC}")
        return
    chosen = models[idx]
    print(f"  Model: {C.BOLD}{chosen}{C.NC}")

    if not confirm_launch(
        "Local Mode (LM Studio)",
        f"  Model:  {C.BOLD}{chosen}{C.NC}",
        f"  URL:    {LM_STUDIO_URL}",
    ):
        return

    # Write apiKeyHelper — only if user opted in via --allow-scripts
    if allow_scripts:
        KEY_HELPER.parent.mkdir(parents=True, exist_ok=True)
        content = f"#!/bin/bash\necho {shlex.quote(LM_STUDIO_API_KEY)}\n"
        fd = os.open(str(KEY_HELPER), os.O_CREAT | os.O_WRONLY | os.O_TRUNC, 0o700)
        try:
            os.write(fd, content.encode())
        finally:
            os.close(fd)
    else:
        logger.info("--allow-scripts not set; skipping apiKeyHelper write")
        print(
            f"  {C.YELLOW}Note: --allow-scripts not set."
            f" Local mode key helper not written.{C.NC}"
        )

    os.environ["ANTHROPIC_MODEL"] = chosen
    os.environ["ANTHROPIC_BASE_URL"] = LM_STUDIO_URL
    os.environ["CLAUDE_CODE_DISABLE_NONESSENTIAL_TRAFFIC"] = "1"

    settings = reset_settings()
    settings["apiKeyHelper"] = str(KEY_HELPER)
    settings.setdefault("env", {})["CLAUDE_CODE_ATTRIBUTION_HEADER"] = "0"
    save_settings(settings)

    print(f"\n  {C.GREEN}Launching Claude Code → LM Studio{C.NC}")
    print("  ─────────────────────────────────")
    exit_code = _run_claude(claude_args)
    if exit_code != 0:
        logger.warning("Claude Code exited with code %d", exit_code)
        print(f"\n  {C.YELLOW}Claude Code exited with code {exit_code}.{C.NC}")


def launch_cloud(claude_args: List[str]) -> None:
    """Launch Claude Code against Anthropic's API (OAuth)."""
    logger.info("cloud mode selected")
    print(f"{C.BLUE}{C.BOLD}☁️  Cloud Mode (Anthropic){C.NC}\n")
    if not confirm_launch(
        "Cloud Mode (Anthropic)",
        "  Provider: Anthropic API",
        "  Auth:     OAuth / Anthropic account",
    ):
        return
    save_settings(reset_settings())
    print(f"  {C.GREEN}Launching Claude Code → Anthropic API{C.NC}")
    print("  ─────────────────────────────────────")
    exit_code = _run_claude(claude_args)
    if exit_code != 0:
        logger.warning("Claude Code exited with code %d", exit_code)
        print(f"\n  {C.YELLOW}Claude Code exited with code {exit_code}.{C.NC}")


def launch_custom(claude_args: List[str]) -> None:
    """Launch Claude Code against a custom provider from providers.json."""
    logger.info("custom provider mode selected")
    print(f"{C.BLUE}{C.BOLD}🔧 Custom Provider Mode{C.NC}\n")
    providers = load_providers()
    if not providers:
        print(f"{C.RED}No custom providers configured.{C.NC}")
        print(f"  Expected config at: {C.BOLD}{PROVIDERS_FILE}{C.NC}\n")
        print(
            "  cp providers.json ~/.claude/providers.json"
            "  # then add your API keys\n"
        )
        if _is_interactive():
            try:
                answer = input("  Set one up now? [y/N] ").strip().lower()
            except (EOFError, KeyboardInterrupt):
                return
            if answer in ("y", "yes"):
                _first_run_wizard()
                providers = load_providers()
                if not providers:
                    return
        return

    # Provider picker
    names = sorted(providers.keys(), key=str.lower)
    idx = pick_from_list("Available providers", names)
    if idx is None:
        return
    name, cfg = names[idx], providers[names[idx]]

    # Resolve $VAR refs at launch time (not eagerly at load time)
    try:
        _resolve_provider_cfg(name, cfg)
    except ProviderConfigError:
        return

    # Model picker (if provider defines models)
    chosen_model = ""
    model_env: Dict[str, Any] = {}
    models = cfg.get("models", [])
    if models:
        model_names = [m["name"] for m in models]
        mi = pick_from_list(f"Models for {C.BOLD}{name}{C.NC}", model_names)
        if mi is None:
            return
        chosen_model = models[mi]["name"]
        model_env = models[mi].get("env", {})

    # Merge env: provider -> model override
    merged = dict(cfg.get("env", {}))
    merged.update(model_env)

    details = [f"  Provider: {C.BOLD}{name}{C.NC}"]
    if chosen_model:
        details.append(f"  Model:    {C.BOLD}{chosen_model}{C.NC}")
    if not confirm_launch(f"Custom Provider ({name})", *details):
        return

    for k, v in merged.items():
        os.environ[k] = str(v)
    settings = reset_settings()
    settings.setdefault("env", {}).update({k: str(v) for k, v in merged.items()})
    save_settings(settings)

    print(f"  {C.GREEN}Launched with custom provider: {name}{C.NC}")
    print("  ─────────────────────────────────────")
    exit_code = _run_claude(claude_args)
    if exit_code != 0:
        logger.warning("Claude Code exited with code %d", exit_code)
        print(f"\n  {C.YELLOW}Claude Code exited with code {exit_code}.{C.NC}")


# -- First-run wizard ------------------------------------------------


def _first_run_wizard() -> None:
    """Interactively build a minimal providers.json v2."""
    print(f"\n  {C.BOLD}── First-run provider setup ──{C.NC}\n")
    try:
        raw_name = input("  Provider name (e.g. Deepseek): ").strip()
        if not raw_name:
            print("  Aborted.")
            return
        try:
            name = sanitize_provider_name(raw_name)
        except ValueError as e:
            print(f"  {C.RED}{e}{C.NC}")
            return

        raw_base = input(
            "  API base URL [https://api.deepseek.com/anthropic]: "
        ).strip()
        if not raw_base:
            base = "https://api.deepseek.com/anthropic"
        else:
            try:
                base = sanitize_url(raw_base)
            except ValueError as e:
                print(f"  {C.RED}{e}{C.NC}")
                return

        raw_key = input("  Env var for API key [DEEPSEEK_API_KEY]: ").strip()
        if not raw_key:
            key_var = "DEEPSEEK_API_KEY"
        else:
            try:
                key_var = sanitize_env_var_name(raw_key)
            except ValueError as e:
                print(f"  {C.RED}{e}{C.NC}")
                return

        model = input("  Default model [deepseek-v4-pro[1m]]: ").strip()
        if not model:
            model = "deepseek-v4-pro[1m]"
    except (EOFError, KeyboardInterrupt):
        print("\n  Aborted.")
        return

    data = {
        "version": 2,
        "providers": {
            name: {
                "env": {
                    "ANTHROPIC_BASE_URL": base,
                    "ANTHROPIC_AUTH_TOKEN": f"${key_var}",
                    "ANTHROPIC_MODEL": model,
                    "CLAUDE_CODE_DISABLE_NONESSENTIAL_TRAFFIC": "1",
                }
            }
        },
    }
    PROVIDERS_FILE.parent.mkdir(parents=True, exist_ok=True)
    from claude_launcher.utils import atomic_write

    atomic_write(PROVIDERS_FILE, data)
    print(f"\n  {C.GREEN}✓ Created {PROVIDERS_FILE}{C.NC}")
    print(f"  Export your key: {C.BOLD}export {key_var}=<your-key>{C.NC}\n")


# -- Status & discovery ----------------------------------------------


def show_status() -> None:
    """Display current configuration and health status."""
    print(f"{C.BLUE}{C.BOLD}📊 Claude Launcher Plus — Status{C.NC}\n")
    print_lm_studio_status()

    base = os.environ.get("ANTHROPIC_BASE_URL", "")
    if base:
        print(f"  Base URL:   {C.YELLOW}{base}{C.NC}")
    else:
        print(f"  Base URL:   {C.GREEN}Anthropic default (cloud){C.NC}")

    from claude_launcher.config import CLAUDE_JSON

    if CLAUDE_JSON.exists():
        try:
            cj = json.loads(CLAUDE_JSON.read_text())
        except (json.JSONDecodeError, IOError):
            cj = {}
        if cj.get("hasCompletedOnboarding"):
            print(f"  Onboarding: {C.GREEN}✓ bypassed{C.NC}")
        else:
            print(f"  Onboarding: {C.YELLOW}not set{C.NC}")
    else:
        print(f"  Onboarding: {C.YELLOW}not set{C.NC}")

    print(f"\n  {C.BOLD}Custom Providers:{C.NC}")
    if PROVIDERS_FILE.exists():
        try:
            providers = load_providers()
            if not providers:
                print("    (no providers defined)")
            for pname, cfg in sorted(providers.items()):
                mc = len(cfg.get("models", []))
                url = cfg.get("env", {}).get("ANTHROPIC_BASE_URL", "not set")
                print(f"    {pname}  →  {url}" + (f"  ({mc} models)" if mc else ""))
        except ProviderConfigError:
            pass
    else:
        print(f"    {C.YELLOW}none configured{C.NC}" f"  (create {PROVIDERS_FILE})")

    settings = load_settings()
    if "apiKeyHelper" in settings:
        print(f"  Auth:       {C.YELLOW}apiKeyHelper (local mode){C.NC}")
    elif os.environ.get("ANTHROPIC_AUTH_TOKEN"):
        print(
            f"  Auth:       {C.YELLOW}ANTHROPIC_AUTH_TOKEN" f" (custom provider){C.NC}"
        )
    else:
        print(f"  Auth:       {C.GREEN}OAuth / Anthropic account{C.NC}")
    if CLAUDE_SETTINGS.exists():
        print(f"  Settings:   {C.GREEN}✓ exists{C.NC}")
    else:
        print(f"  Settings:   {C.YELLOW}not found{C.NC}")


def list_providers() -> None:
    """Print all configured provider names."""
    providers = load_providers()
    if not providers:
        print("No custom providers configured.")
        sys.exit(1)
    for name in sorted(providers.keys()):
        print(name)


def list_models(provider_name: Optional[str] = None) -> None:
    """Print model names for a specific provider."""
    if not provider_name:
        print(
            "Usage: claude-launcher-plus list-models <provider>",
            file=sys.stderr,
        )
        sys.exit(1)
    providers = load_providers()
    if not providers:
        print("No custom providers configured.")
        sys.exit(1)
    p = providers.get(provider_name)
    if not p:
        print(f"Provider '{provider_name}' not found.")
        sys.exit(1)
    models = p.get("models", [])
    if not models:
        print(f"{provider_name}: no models defined" f" (uses provider-level env only)")
        return
    for m in models:
        mid = m.get("env", {}).get("ANTHROPIC_MODEL", "no ANTHROPIC_MODEL set")
        print(f"{m.get('name', 'unknown')}  ->  {mid}")


# -- Interactive menu ------------------------------------------------


def interactive_menu() -> None:
    """Main loop. Returns after each Claude session exits."""
    if not _is_interactive():
        print(
            f"{C.RED}Interactive menu requires a TTY."
            f" Use 'local', 'cloud', or 'custom' subcommands.{C.NC}",
            file=sys.stderr,
        )
        sys.exit(1)
    while True:
        try:
            print(f"\n{C.BOLD}┌─────────────────────────────────────┐{C.NC}")
            print(f"{C.BOLD}│      Claude Launcher Plus 🚀       │{C.NC}")
            print(f"{C.BOLD}└─────────────────────────────────────┘{C.NC}\n")
            print_lm_studio_status()
            print(f"\n  {C.BOLD}1){C.NC}  🖥  Local mode (LM Studio)")
            print(f"  {C.BOLD}2){C.NC}  ☁️  Cloud mode (Anthropic)")
            print(f"  {C.BOLD}3){C.NC}  🔧 Custom provider")
            print(f"  {C.BOLD}4){C.NC}  📊 Status")
            print(f"  {C.BOLD}q){C.NC}  Exit\n")
            try:
                choice = input("  Choose [1/2/3/4/q]: ").strip()
            except (EOFError, KeyboardInterrupt):
                print()
                sys.exit(0)

            if choice == "1":
                launch_local([])
            elif choice == "2":
                launch_cloud([])
            elif choice == "3":
                launch_custom([])
            elif choice == "4":
                show_status()
            elif choice.lower() == "q":
                print(f"  {C.GREEN}Goodbye!{C.NC}")
                sys.exit(0)
            else:
                print(f"  {C.RED}Invalid choice{C.NC}")
        except KeyboardInterrupt:
            print()
            sys.exit(0)
