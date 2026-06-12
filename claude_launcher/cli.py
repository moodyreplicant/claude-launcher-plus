"""Command-line entry point for claude-launcher-plus.

Parses arguments and dispatches to the appropriate launch mode or command.
"""

__all__ = ["main"]

import argparse
import sys
import textwrap
from typing import Callable

from claude_launcher import VERSION
from claude_launcher.config import PROVIDERS_FILE, load_settings
from claude_launcher.launcher import (
    _check_dep,
    check_all_deps,
    interactive_menu,
    launch_cloud,
    launch_custom,
    launch_local,
    list_models,
    list_providers,
    print_lm_studio_status,
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
        print(f"{C.BLUE}{C.BOLD}🔍 Dry-run validation{C.NC}\n")
        if args.mode in (None, "local"):
            print_lm_studio_status()
        if args.mode in (None, "custom"):
            if PROVIDERS_FILE.exists():
                try:
                    providers = load_providers()
                    print(
                        f"  providers.json: {C.GREEN}✓ valid{C.NC}"
                        f" ({len(providers)} provider(s))"
                    )
                except SystemExit:
                    pass
            else:
                print(f"  providers.json: {C.YELLOW}not found{C.NC}")
        s = load_settings()
        if s:
            print(f"  settings.json: {C.GREEN}✓ exists{C.NC}")
        else:
            print(f"  settings.json: {C.YELLOW}empty or not found{C.NC}")
        print(f"\n  {C.GREEN}Validation complete.{C.NC}")
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
