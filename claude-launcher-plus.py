#!/usr/bin/env python3
"""claude-launcher-plus v3.1.0 — Enhanced launcher for Claude Code CLI.

This is a thin entry point that delegates to the claude_launcher package.
All logic lives in claude_launcher/ modules.
"""

from claude_launcher.cli import main

if __name__ == "__main__":
    main()
