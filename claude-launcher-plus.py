#!/usr/bin/env python3
"""claude-launcher-plus v2.0.0 — Enhanced launcher for Claude Code CLI.

Three modes: local (LM Studio), cloud (Anthropic OAuth), custom provider.
Usage: python3 claude-launcher-plus.py [local|cloud|custom|status|...]
"""

import argparse, json, os, shlex, shutil, signal, subprocess, sys
import tempfile, textwrap, time, urllib.request, urllib.error
from pathlib import Path
from typing import Dict, List, Optional, Tuple

VERSION = "2.0.2"

# -- Configuration --------------------------------------------------
LM_STUDIO_URL = f"http://{os.environ.get('LM_STUDIO_HOST','localhost')}:{os.environ.get('LM_STUDIO_PORT','1234')}"
LM_STUDIO_API_KEY = os.environ.get("LM_STUDIO_API_KEY", "lm-studio")
CLAUDE_JSON = Path.home() / ".claude.json"
CLAUDE_SETTINGS = Path.home() / ".claude" / "settings.json"
PROVIDERS_FILE = Path.home() / ".claude" / "providers.json"
KEY_HELPER = Path.home() / ".claude" / "api-key-helper.sh"
NO_COLOR = "NO_COLOR" in os.environ

LAUNCHER_ENV_KEYS = [
    "ANTHROPIC_BASE_URL", "ANTHROPIC_MODEL", "ANTHROPIC_AUTH_TOKEN",
    "CLAUDE_CODE_DISABLE_NONESSENTIAL_TRAFFIC", "CLAUDE_CODE_ATTRIBUTION_HEADER",
    "CLAUDE_CODE_EFFORT_LEVEL", "ANTHROPIC_DEFAULT_OPUS_MODEL",
    "ANTHROPIC_DEFAULT_SONNET_MODEL", "ANTHROPIC_DEFAULT_HAIKU_MODEL",
    "OPENROUTER_API_KEY",
]

# -- Terminal colors (no-color.org compliant) -----------------------
class C:
    GREEN = "" if NO_COLOR else "\033[0;32m"
    YELLOW = "" if NO_COLOR else "\033[1;33m"
    BLUE = "" if NO_COLOR else "\033[0;34m"
    RED = "" if NO_COLOR else "\033[0;31m"
    BOLD = "" if NO_COLOR else "\033[1m"
    NC = "" if NO_COLOR else "\033[0m"

# -- Atomic file write ----------------------------------------------
def atomic_write(path: Path, data: dict) -> None:
    """Write JSON atomically via tempfile + os.replace (crash-safe)."""
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = None
    try:
        tmp = tempfile.NamedTemporaryFile(
            mode="w", dir=path.parent, delete=False, suffix=".tmp", encoding="utf-8")
        json.dump(data, tmp, indent=2, ensure_ascii=False)
        tmp.write("\n"); tmp.flush(); os.fsync(tmp.fileno()); tmp.close()
        os.replace(tmp.name, str(path))
    except Exception:
        if tmp is not None:
            try: Path(tmp.name).unlink()
            except FileNotFoundError: pass
        raise

# -- Settings management --------------------------------------------
def load_settings() -> dict:
    """Load settings.json. On corruption: back up to .bak, warn, return {}."""
    if not CLAUDE_SETTINGS.exists():
        return {}
    try:
        with open(CLAUDE_SETTINGS, "r", encoding="utf-8") as f:
            return json.load(f)
    except (json.JSONDecodeError, IOError) as e:
        bak = Path(str(CLAUDE_SETTINGS) + ".bak")
        shutil.copy2(CLAUDE_SETTINGS, bak)
        print(f"  {C.YELLOW}Warning: settings.json corrupted ({e}){C.NC}", file=sys.stderr)
        print(f"  Backup saved to {bak}", file=sys.stderr)
        return {}

def reset_settings() -> dict:
    """Remove launcher-managed keys. Returns cleaned dict (does NOT write to disk)."""
    d = load_settings()
    d.pop("apiKeyHelper", None); d.pop("ANTHROPIC_AUTH_TOKEN", None)
    env = d.get("env")
    if isinstance(env, dict):
        for key in LAUNCHER_ENV_KEYS:
            env.pop(key, None)
        if not env:
            d.pop("env", None)
    return d

def save_settings(d: dict) -> None:
    atomic_write(CLAUDE_SETTINGS, d)

def ensure_onboarding_done() -> None:
    """Mark hasCompletedOnboarding so Claude Code skips the first-run wizard."""
    d: dict = {}
    if CLAUDE_JSON.exists():
        try:
            with open(CLAUDE_JSON, "r", encoding="utf-8") as f:
                d = json.load(f)
        except (json.JSONDecodeError, IOError): pass
    d["hasCompletedOnboarding"] = True
    CLAUDE_JSON.parent.mkdir(parents=True, exist_ok=True)
    atomic_write(CLAUDE_JSON, d)

# -- Providers management -------------------------------------------
class ProviderConfigError(Exception):
    """Raised when a provider's env var ($VAR ref) can't be resolved."""

def _resolve_env_value(value: str, provider_name: str) -> str:
    """Resolve $VAR / ${VAR} from environment. Raises ProviderConfigError if unset."""
    if not isinstance(value, str) or not value.startswith("$"):
        return value
    var = value[1:].strip("{}")
    if var not in os.environ:
        print(f"\n  {C.RED}Env var '{var}' is not set.{C.NC}", file=sys.stderr)
        print(f"  Required by '{C.BOLD}{provider_name}{C.NC}'.", file=sys.stderr)
        print(f"  Add 'export {var}=<key>' to your shell config.\n", file=sys.stderr)
        raise ProviderConfigError(f"Env var '{var}' is not set")
    return os.environ[var]

def _resolve_provider_cfg(name: str, cfg: dict) -> None:
    """Resolve $VAR refs in a single provider's env (mutates in place).
    Raises ProviderConfigError if any env var can't be resolved.
    Only called at launch time — not during read-only operations like status."""
    if "env" in cfg:
        cfg["env"] = {k: _resolve_env_value(v, name) for k, v in cfg["env"].items()}
    for model in cfg.get("models", []):
        if "env" in model:
            model["env"] = {k: _resolve_env_value(v, name) for k, v in model["env"].items()}

def load_providers() -> dict:
    """Load & validate providers.json. Supports v1 (plaintext) and v2 ($VAR refs)."""
    if not PROVIDERS_FILE.exists():
        return {}
    try:
        data = json.loads(PROVIDERS_FILE.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, IOError) as e:
        print(f"  {C.RED}Error: providers.json is invalid: {e}{C.NC}", file=sys.stderr)
        sys.exit(1)

    # Version guard: coerce to int, warn on non-integer
    try: version = int(data.get("version", 1))
    except (TypeError, ValueError):
        print(f"  {C.YELLOW}Warning: providers.json 'version' should be an integer"
              f" — treating as v1.{C.NC}", file=sys.stderr)
        version = 1

    providers = data.get("providers", {})
    return providers

# -- LM Studio client (stdlib urllib — replaces curl) ---------------
def _lm_studio_get(endpoint: str, timeout: int = 5) -> Optional[dict]:
    try:
        req = urllib.request.Request(
            f"{LM_STUDIO_URL}{endpoint}", headers={"User-Agent": "claude-launcher-plus"})
        with urllib.request.urlopen(req, timeout=timeout) as r:
            return json.loads(r.read().decode())
    except (urllib.error.URLError, OSError, json.JSONDecodeError):
        return None

def check_lm_studio() -> bool:
    return _lm_studio_get("/api/v1/models", timeout=2) is not None

def get_lm_studio_models() -> List[str]:
    data = _lm_studio_get("/api/v1/models", timeout=5)
    if not data: return []
    return [m["key"] for m in data.get("models", [])
            if m.get("type") == "llm" and len(m.get("loaded_instances", [])) > 0]

def print_lm_studio_status() -> None:
    if check_lm_studio():
        models = get_lm_studio_models()
        if models:
            print(f"  LM Studio:  {C.GREEN}● running{C.NC} at {LM_STUDIO_URL}"
                  f" — {len(models)} model(s): {C.BOLD}{', '.join(models)}{C.NC}")
        else:
            print(f"  LM Studio:  {C.GREEN}● running{C.NC} at {LM_STUDIO_URL} — 0 models loaded")
    else:
        print(f"  LM Studio: {C.RED}● offline{C.NC} at {LM_STUDIO_URL}")

# -- Interactive UI helpers -----------------------------------------
def _is_interactive() -> bool:
    return sys.stdin.isatty()

def pick_from_list(title: str, items: List[str]) -> Optional[int]:
    """Present numbered list, return chosen index. Auto-pick when single item."""
    if not items: return None
    if len(items) == 1:
        print(f"  {title}: {C.BOLD}{items[0]}{C.NC} (auto-selected)")
        return 0
    print(f"\n  {C.BOLD}{title}:{C.NC}")
    for i, item in enumerate(items):
        print(f"  {C.BOLD}{i+1}){C.NC}  {item}")
    print()
    if not _is_interactive():
        print(f"  Non-interactive — using: {C.BOLD}{items[0]}{C.NC}")
        return 0
    try:
        choice = input(f"  Choose [1-{len(items)}]: ").strip()
        idx = int(choice) - 1
        if 0 <= idx < len(items): return idx
    except (ValueError, EOFError, KeyboardInterrupt): pass
    print(f"  {C.YELLOW}Invalid choice, using first.{C.NC}")
    return 0

def confirm_launch(title: str, *details: str) -> bool:
    """Y/n confirmation. Skips when stdin is not a TTY."""
    if not _is_interactive(): return True
    print(f"\n  {C.BOLD}{C.BLUE}═══ Ready to launch: {title} ═══{C.NC}")
    for line in details: print(f"  {line}")
    print()
    try: answer = input("  Proceed? [Y/n] ").strip().lower()
    except (EOFError, KeyboardInterrupt): return False
    return answer not in ("n", "no")

def _wait_for_lm_studio() -> bool:
    """Retry loop — 60s deadline, user can abort."""
    if not _is_interactive():
        print(f"  {C.RED}LM Studio not running and stdin is not a TTY. Aborting.{C.NC}")
        return False
    try: answer = input("  Wait and retry? (y/n) ").strip().lower()
    except (EOFError, KeyboardInterrupt): return False
    if answer not in ("y", "yes"): return False
    print("  Waiting for LM Studio...", end="", flush=True)
    deadline = time.monotonic() + 60
    while time.monotonic() < deadline:
        if check_lm_studio():
            print(f"\n  {C.GREEN}✓ Connected!{C.NC}"); return True
        time.sleep(1); print(".", end="", flush=True)
    print(f"\n  {C.RED}Timed out after 60s. Start LM Studio and try again.{C.NC}")
    return False

# -- Launch modes ---------------------------------------------------
def launch_local(claude_args: List[str]) -> None:
    """Launch Claude Code against a local LM Studio instance."""
    print(f"{C.BLUE}{C.BOLD}🖥  Local Mode (LM Studio){C.NC}\n")
    if not check_lm_studio():
        print(f"{C.RED}✗ LM Studio not responding at {LM_STUDIO_URL}{C.NC}")
        print("  Make sure LM Studio is running and the server is started.")
        if not _wait_for_lm_studio(): return
    print(f"{C.GREEN}✓ LM Studio is running{C.NC}\n")

    ensure_onboarding_done(); CLAUDE_SETTINGS.parent.mkdir(parents=True, exist_ok=True)

    models = get_lm_studio_models()
    if not models:
        print(f"{C.RED}No loaded models found — aborting.{C.NC}"); return
    idx = pick_from_list("Available LM Studio models", models)
    if idx is None:
        print(f"{C.RED}No loaded models found — aborting.{C.NC}"); return
    chosen = models[idx]
    print(f"  Model: {C.BOLD}{chosen}{C.NC}")

    if not confirm_launch("Local Mode (LM Studio)",
                          f"  Model:  {C.BOLD}{chosen}{C.NC}",
                          f"  URL:    {LM_STUDIO_URL}"):
        return

    # Write apiKeyHelper — shell-quoted, owner-only, no TOCTOU window
    KEY_HELPER.parent.mkdir(parents=True, exist_ok=True)
    content = f"#!/bin/bash\necho {shlex.quote(LM_STUDIO_API_KEY)}\n"
    fd = os.open(str(KEY_HELPER), os.O_CREAT | os.O_WRONLY | os.O_TRUNC, 0o700)
    try: os.write(fd, content.encode())
    finally: os.close(fd)

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
        print(f"\n  {C.YELLOW}Claude Code exited with code {exit_code}.{C.NC}")

def launch_cloud(claude_args: List[str]) -> None:
    """Launch Claude Code against Anthropic's API (OAuth)."""
    print(f"{C.BLUE}{C.BOLD}☁️  Cloud Mode (Anthropic){C.NC}\n")
    if not confirm_launch("Cloud Mode (Anthropic)",
                          "  Provider: Anthropic API",
                          "  Auth:     OAuth / Anthropic account"):
        return
    save_settings(reset_settings())
    print(f"  {C.GREEN}Launching Claude Code → Anthropic API{C.NC}")
    print("  ─────────────────────────────────────")
    exit_code = _run_claude(claude_args)
    if exit_code != 0:
        print(f"\n  {C.YELLOW}Claude Code exited with code {exit_code}.{C.NC}")

def launch_custom(claude_args: List[str]) -> None:
    """Launch Claude Code against a custom provider from providers.json."""
    print(f"{C.BLUE}{C.BOLD}🔧 Custom Provider Mode{C.NC}\n")
    providers = load_providers()
    if not providers:
        print(f"{C.RED}No custom providers configured.{C.NC}")
        print(f"  Expected config at: {C.BOLD}{PROVIDERS_FILE}{C.NC}\n")
        print("  cp providers.json ~/.claude/providers.json  # then add your API keys\n")
        if _is_interactive():
            try: answer = input("  Set one up now? [y/N] ").strip().lower()
            except (EOFError, KeyboardInterrupt): return
            if answer in ("y", "yes"):
                _first_run_wizard()
                providers = load_providers()
                if not providers: return
        return

    # Provider picker
    names = sorted(providers.keys(), key=str.lower)
    idx = pick_from_list("Available providers", names)
    if idx is None: return
    name, cfg = names[idx], providers[names[idx]]

    # Resolve $VAR refs at launch time (not eagerly at load time)
    try:
        _resolve_provider_cfg(name, cfg)
    except ProviderConfigError:
        return

    # Model picker (if provider defines models)
    chosen_model = ""
    model_env: dict = {}
    models = cfg.get("models", [])
    if models:
        model_names = [m["name"] for m in models]
        mi = pick_from_list(f"Models for {C.BOLD}{name}{C.NC}", model_names)
        if mi is None: return
        chosen_model = models[mi]["name"]
        model_env = models[mi].get("env", {})

    # Merge env: provider → model override
    merged = dict(cfg.get("env", {})); merged.update(model_env)

    details = [f"  Provider: {C.BOLD}{name}{C.NC}"]
    if chosen_model: details.append(f"  Model:    {C.BOLD}{chosen_model}{C.NC}")
    if not confirm_launch(f"Custom Provider ({name})", *details): return

    for k, v in merged.items(): os.environ[k] = str(v)
    settings = reset_settings()
    settings.setdefault("env", {}).update({k: str(v) for k, v in merged.items()})
    save_settings(settings)

    print(f"  {C.GREEN}Launched with custom provider: {name}{C.NC}")
    print("  ─────────────────────────────────────")
    exit_code = _run_claude(claude_args)
    if exit_code != 0:
        print(f"\n  {C.YELLOW}Claude Code exited with code {exit_code}.{C.NC}")

# -- First-run wizard -----------------------------------------------
def _first_run_wizard() -> None:
    """Interactively build a minimal providers.json v2."""
    print(f"\n  {C.BOLD}── First-run provider setup ──{C.NC}\n")
    try:
        name = input("  Provider name (e.g. Deepseek): ").strip()
        if not name: print("  Aborted."); return
        base = input("  API base URL [https://api.deepseek.com/anthropic]: ").strip()
        if not base: base = "https://api.deepseek.com/anthropic"
        key_var = input("  Env var for API key [DEEPSEEK_API_KEY]: ").strip()
        if not key_var: key_var = "DEEPSEEK_API_KEY"
        model = input("  Default model [deepseek-v4-pro[1m]]: ").strip()
        if not model: model = "deepseek-v4-pro[1m]"
    except (EOFError, KeyboardInterrupt): print("\n  Aborted."); return

    data = {"version": 2, "providers": {name: {"env": {
        "ANTHROPIC_BASE_URL": base, "ANTHROPIC_AUTH_TOKEN": f"${key_var}",
        "ANTHROPIC_MODEL": model, "CLAUDE_CODE_DISABLE_NONESSENTIAL_TRAFFIC": "1"}}}}
    PROVIDERS_FILE.parent.mkdir(parents=True, exist_ok=True)
    atomic_write(PROVIDERS_FILE, data)
    print(f"\n  {C.GREEN}✓ Created {PROVIDERS_FILE}{C.NC}")
    print(f"  Export your key: {C.BOLD}export {key_var}=<your-key>{C.NC}\n")

# -- Status & discovery ---------------------------------------------
def show_status() -> None:
    print(f"{C.BLUE}{C.BOLD}📊 Claude Code Launcher — Status{C.NC}\n")
    print_lm_studio_status()

    base = os.environ.get("ANTHROPIC_BASE_URL", "")
    print(f"  Base URL:   {C.YELLOW}{base}{C.NC}" if base else
          f"  Base URL:   {C.GREEN}Anthropic default (cloud){C.NC}")

    if CLAUDE_JSON.exists():
        try: cj = json.loads(CLAUDE_JSON.read_text())
        except (json.JSONDecodeError, IOError): cj = {}
        print(f"  Onboarding: {C.GREEN}✓ bypassed{C.NC}" if cj.get("hasCompletedOnboarding")
              else f"  Onboarding: {C.YELLOW}not set{C.NC}")
    else:
        print(f"  Onboarding: {C.YELLOW}not set{C.NC}")

    print(f"\n  {C.BOLD}Custom Providers:{C.NC}")
    if PROVIDERS_FILE.exists():
        try:
            providers = load_providers()
            if not providers: print("    (no providers defined)")
            for pname, cfg in sorted(providers.items()):
                mc = len(cfg.get("models", []))
                url = cfg.get("env", {}).get("ANTHROPIC_BASE_URL", "not set")
                print(f"    {pname}  →  {url}" + (f"  ({mc} models)" if mc else ""))
        except ProviderConfigError:
            # env var resolution failed — _resolve_env_value already printed
            # the error; degrade gracefully so status display continues
            pass
    else:
        print(f"    {C.YELLOW}none configured{C.NC}  (create {PROVIDERS_FILE})")

    settings = load_settings()
    if "apiKeyHelper" in settings:
        print(f"  Auth:       {C.YELLOW}apiKeyHelper (local mode){C.NC}")
    elif os.environ.get("ANTHROPIC_AUTH_TOKEN"):
        print(f"  Auth:       {C.YELLOW}ANTHROPIC_AUTH_TOKEN (custom provider){C.NC}")
    else:
        print(f"  Auth:       {C.GREEN}OAuth / Anthropic account{C.NC}")
    print(f"  Settings:   {C.GREEN}✓ exists{C.NC}" if CLAUDE_SETTINGS.exists() else
          f"  Settings:   {C.YELLOW}not found{C.NC}")

def list_providers() -> None:
    providers = load_providers()
    if not providers: print("No custom providers configured."); sys.exit(1)
    for name in sorted(providers.keys()): print(name)

def list_models(provider_name: str) -> None:
    if not provider_name:
        print("Usage: claude-launcher-plus list-models <provider>", file=sys.stderr); sys.exit(1)
    providers = load_providers()
    if not providers: print("No custom providers configured."); sys.exit(1)
    p = providers.get(provider_name)
    if not p: print(f"Provider '{provider_name}' not found."); sys.exit(1)
    models = p.get("models", [])
    if not models:
        print(f"{provider_name}: no models defined (uses provider-level env only)"); return
    for m in models:
        mid = m.get("env", {}).get("ANTHROPIC_MODEL", "no ANTHROPIC_MODEL set")
        print(f"{m.get('name','unknown')}  ->  {mid}")

# -- Interactive menu -----------------------------------------------
def interactive_menu() -> None:
    """Main loop. Returns after each Claude session exits (subprocess.run, not exec)."""
    while True:
        try:
            print(f"\n{C.BOLD}┌─────────────────────────────────────┐{C.NC}")
            print(f"{C.BOLD}│     Claude Code Launcher  🚀        │{C.NC}")
            print(f"{C.BOLD}└─────────────────────────────────────┘{C.NC}\n")
            print_lm_studio_status()
            print(f"\n  {C.BOLD}1){C.NC}  🖥  Local mode (LM Studio)")
            print(f"  {C.BOLD}2){C.NC}  ☁️  Cloud mode (Anthropic)")
            print(f"  {C.BOLD}3){C.NC}  🔧 Custom provider")
            print(f"  {C.BOLD}4){C.NC}  📊 Status")
            print(f"  {C.BOLD}q){C.NC}  Exit\n")
            try: choice = input("  Choose [1/2/3/4/q]: ").strip()
            except (EOFError, KeyboardInterrupt): print(); sys.exit(0)
            {"1": lambda: launch_local([]), "2": lambda: launch_cloud([]),
             "3": lambda: launch_custom([]), "4": show_status}.get(
                choice, lambda: None if choice.lower() != "q" else (
                    print(f"  {C.GREEN}Goodbye!{C.NC}"), sys.exit(0))[1])()
            if choice not in ("1","2","3","4","q","Q"):
                print(f"  {C.RED}Invalid choice{C.NC}")
        except KeyboardInterrupt: print(); sys.exit(0)

# -- CLI entry point ------------------------------------------------
def _run_claude(claude_args: List[str]) -> int:
    """Launch claude subprocess. Restores default signal handlers so
    Ctrl+C reaches the child process naturally."""
    signal.signal(signal.SIGINT, signal.SIG_DFL)
    signal.signal(signal.SIGTERM, signal.SIG_DFL)
    return subprocess.run(["claude"] + claude_args).returncode

def _check_dep(name: str) -> bool:
    return shutil.which(name) is not None

def main() -> None:
    parser = argparse.ArgumentParser(
        prog="claude-launcher-plus",
        description="Enhanced launcher for Claude Code CLI — local, cloud, or custom provider.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=textwrap.dedent("""\
            examples:
              claude-launcher-plus local              # LM Studio mode
              claude-launcher-plus cloud              # Anthropic OAuth
              claude-launcher-plus custom             # Custom provider
              claude-launcher-plus status             # Show configuration
              claude-launcher-plus list-providers     # List providers
              claude-launcher-plus list-models Deepseek  # List models
              claude-launcher-plus --dry-run custom   # Validate only
        """))
    parser.add_argument("mode", nargs="?", choices=[
        "local","cloud","custom","status","list-providers","list-models"],
        help="Launch mode or discovery command (omit for interactive menu)")
    parser.add_argument("provider", nargs="?", help="Provider name (for list-models)")
    parser.add_argument("--version","-V", action="version",
                        version=f"claude-launcher-plus v{VERSION}")
    parser.add_argument("--dry-run", action="store_true",
                        help="Validate configuration without launching Claude Code")
    parser.add_argument("claude_args", nargs=argparse.REMAINDER,
                        help="Arguments passed through to 'claude' (use -- to separate)")
    args = parser.parse_args()

    if args.mode in ("local","cloud","custom",None) and not _check_dep("claude"):
        print(f"{C.RED}Error: 'claude' not found in PATH.{C.NC}"
              f"  Install: https://docs.anthropic.com/en/docs/claude-code", file=sys.stderr)
        sys.exit(1)

    if args.dry_run:
        print(f"{C.BLUE}{C.BOLD}🔍 Dry-run validation{C.NC}\n")
        if args.mode in (None, "local"): print_lm_studio_status()
        if args.mode in (None, "custom"):
            if PROVIDERS_FILE.exists():
                try:
                    providers = load_providers()
                    print(f"  providers.json: {C.GREEN}✓ valid{C.NC}"
                          f" ({len(providers)} provider(s))")
                except SystemExit: pass
            else: print(f"  providers.json: {C.YELLOW}not found{C.NC}")
        s = load_settings()
        print(f"  settings.json: {C.GREEN}✓ exists{C.NC}" if s else
              f"  settings.json: {C.YELLOW}empty or not found{C.NC}")
        print(f"\n  {C.GREEN}Validation complete.{C.NC}"); return

    # Strip leading '--' separator if present
    ca = args.claude_args
    if ca and ca[0] == "--": ca = ca[1:]

    dispatch = {
        "local": lambda: launch_local(ca), "cloud": lambda: launch_cloud(ca),
        "custom": lambda: launch_custom(ca), "status": show_status,
        "list-providers": list_providers, "list-models": lambda: list_models(args.provider),
    }
    action = dispatch.get(args.mode, interactive_menu)
    action()

if __name__ == "__main__":
    main()
