#!/usr/bin/env bash
# install.sh — Installer for claude-launcher-plus
# Usage: bash install.sh [PREFIX]
#   PREFIX: installation directory (default: $HOME/.local/bin)

set -euo pipefail

PREFIX="${1:-$HOME/.local/bin}"
SCRIPT="claude-launcher-plus"
TARGET="$PREFIX/$SCRIPT"
PROVIDERS_TEMPLATE="providers.json"
PROVIDERS_DEST="$HOME/.claude/providers.json"

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"

if [[ ! -f "$SCRIPT_DIR/$SCRIPT.sh" ]]; then
    echo "Error: $SCRIPT.sh not found in current directory."
    echo "Run this from the cloned repository."
    exit 1
fi

mkdir -p "$PREFIX"
cp "$SCRIPT_DIR/$SCRIPT.sh" "$TARGET"
chmod +x "$TARGET"

if [[ ! -f "$PROVIDERS_DEST" ]]; then
    if [[ -f "$SCRIPT_DIR/$PROVIDERS_TEMPLATE" ]]; then
        mkdir -p "$HOME/.claude"
        cp "$SCRIPT_DIR/$PROVIDERS_TEMPLATE" "$PROVIDERS_DEST"
        echo "Template providers.json created at $PROVIDERS_DEST"
        echo "Edit it to add your API keys before using custom provider mode."
    fi
else
    echo "Existing providers.json found at $PROVIDERS_DEST — left unchanged."
fi

echo ""
echo "Claude Code Launcher Plus installed to $TARGET"

if [[ ":$PATH:" != *":$PREFIX:"* ]]; then
    echo ""
    echo "Add $PREFIX to your PATH to run 'claude-launcher-plus' from anywhere:"
    echo "  echo 'export PATH=\"\$HOME/.local/bin:\$PATH\"' >> ~/.zshrc   # zsh"
    echo "  echo 'export PATH=\"\$HOME/.local/bin:\$PATH\"' >> ~/.bashrc  # bash"
fi
