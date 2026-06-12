"""Command-line entry point for claude-launcher-plus.

Parses arguments and dispatches to the appropriate launch mode or command.
"""

__all__ = ["main"]

import argparse
import sys
import textwrap
from typing import Callable

from claude_launcher import VERSION
from claude_launcher.config import LM_STUDIO_URL, PROVIDERS_FILE, load_settings
from claude_launcher.launcher import (
    _check_dep,
    check_all_deps,
    interactive_menu,
    launch_cloud,
    launch_custom,
    launch_local,
    list_models,
    list_providers,
    show_status,
)
from claude_launcher.logger import configure_logging, get_logger
from claude_launcher.providers import load_providers
from claude_launcher.utils import C

logger = get_logger("cli")


def main() -> None:
    """Parse arguments and dispatch to the selected mode."""
    parser = argparse.ArgumentParser(
        prog="claude-launcher-plus",
        description=(
            "Enhanced launcher for Claude Code CLI"
            " — local, cloud, or custom provider."
        ),
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
              claude-launcher-plus check-deps          # Check dependencies
        """),
    )
    parser.add_argument(
        "mode",
        nargs="?",
        choices=[
            "local",
            "cloud",
            "custom",
            "status",
            "list-providers",
            "list-models",
            "check-deps",
        ],
        help="Launch mode or discovery command (omit for interactive menu)",
    )
    parser.add_argument(
        "provider",
        nargs="?",
        help="Provider name (for list-models)",
    )
    parser.add_argument(
        "--version",
        "-V",
        action="version",
        version=f"claude-launcher-plus v{VERSION}",
    )
    parser.add_argument(
        "--verbose",
        "-v",
        action="store_true",
        help="Enable DEBUG-level logging",
    )
    parser.add_argument(
        "--allow-scripts",
        action="store_true",
        help="Allow writing api-key-helper.sh (required for local mode key helper)",
    )
    parser.add_argument(
        "--non-interactive",
        action="store_true",
        help="Skip all interactive prompts (use defaults, exit on ambiguity)",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Validate configuration without launching Claude Code",
    )
    parser.add_argument(
        "claude_args",
        nargs=argparse.REMAINDER,
        help="Arguments passed through to 'claude' (use -- to separate)",
    )
    args = parser.parse_args()

    configure_logging(verbose=args.verbose)
    logger.debug("started with args: %s", sys.argv[1:])

    if args.non_interactive:
        from claude_launcher.utils import set_non_interactive

        set_non_interactive()
        logger.debug("non-interactive mode enabled")

    from claude_launcher.config import check_directory_permissions

    check_directory_permissions()

    if args.mode in ("local", "cloud", "custom", None) and not _check_dep("claude"):
        print(
            f"{C.RED}Error: 'claude' not found in PATH.{C.NC}"
            f"  Install: https://docs.anthropic.com/en/docs/claude-code",
            file=sys.stderr,
        )
        sys.exit(1)

    if args.dry_run:
        dry_run_ok = True
        print(f"{C.BLUE}{C.BOLD}🔍 Dry-run validation{C.NC}\n")

        # 1. Mode and execution plan
        mode = args.mode or "interactive"
        print(f"  Mode:       {C.BOLD}{mode}{C.NC}")
        if mode == "local":
            from claude_launcher.launcher import check_lm_studio, get_lm_studio_models

            print(f"  LM Studio:  {LM_STUDIO_URL}")
            if check_lm_studio():
                models = get_lm_studio_models()
                print(f"  Models:     {len(models)} available")
            else:
                print(f"  LM Studio:  {C.YELLOW}offline — will prompt to wait{C.NC}")
        elif mode == "cloud":
            print("  Provider:   Anthropic API (OAuth)")
            print("  Auth:       OAuth / Anthropic account")
        elif mode == "custom":
            if PROVIDERS_FILE.exists():
                providers = load_providers()
                print(
                    f"  providers.json: {C.GREEN}✓ valid{C.NC}"
                    f" ({len(providers)} provider(s))"
                )
                for pname in sorted(providers.keys()):
                    print(f"    - {pname}")
            else:
                print(f"  providers.json: {C.YELLOW}not found{C.NC}")

        # 2. Configuration files
        print()
        s = load_settings()
        if s:
            print(f"  settings.json: {C.GREEN}✓ exists{C.NC} ({len(s)} keys)")
        else:
            print(f"  settings.json: {C.YELLOW}empty or not found{C.NC}")

        if not _check_dep("claude"):
            print(f"  claude:      {C.RED}✗ not found in PATH{C.NC}")
            dry_run_ok = False
        else:
            print(f"  claude:      {C.GREEN}✓ found{C.NC}")

        # 3. Claude args pass-through
        ca = args.claude_args
        if ca and ca[0] == "--":
            ca = ca[1:]
        if ca:
            print(f"  Pass-through args: {ca}")

        # Outcome
        print()
        if dry_run_ok:
            print(f"  {C.GREEN}Validation passed.{C.NC}")
        else:
            print(f"  {C.RED}Validation failed — correct the issues above.{C.NC}")
        sys.exit(0 if dry_run_ok else 1)
        return

    # Strip leading '--' separator if present
    ca = args.claude_args
    if ca and ca[0] == "--":
        ca = ca[1:]

    dispatch: dict[str, Callable[[], None]] = {
        "local": lambda: launch_local(ca, allow_scripts=args.allow_scripts),
        "cloud": lambda: launch_cloud(ca),
        "custom": lambda: launch_custom(ca),
        "status": show_status,
        "list-providers": list_providers,
        "list-models": lambda: list_models(args.provider),
        "check-deps": lambda: (
            sys.exit(0) if check_all_deps(show_all=True) else sys.exit(1)
        ),
    }
    action = dispatch.get(args.mode, interactive_menu)
    action()


if __name__ == "__main__":
    main()
