#!/usr/bin/env bash
# uninstall.sh — Uninstaller for claude-launcher-plus
# Usage: bash uninstall.sh
#   Removes the installed binary and offers to clean up related config.

set -euo pipefail

# ------------------------------------------------------------------
# ROOT GUARD
# ------------------------------------------------------------------
if [[ "${EUID:-$(id -u)}" -eq 0 ]]; then
    echo "Error: Do not run with sudo — everything lives in your home directory."
    exit 1
fi

# ------------------------------------------------------------------
# CONFIGURATION
# ------------------------------------------------------------------
PREFIX="$HOME/.local/bin"
SCRIPT_NAME="claude-launcher-plus"
TARGET="$PREFIX/$SCRIPT_NAME"
VERSION_FILE="$HOME/.claude/.clp-version"
PROVIDERS_FILE="$HOME/.claude/providers.json"
SETTINGS_FILE="$HOME/.claude/settings.json"

# ------------------------------------------------------------------
# SHELL DETECTION
# ------------------------------------------------------------------
detect_shell_rc() {
    case "$SHELL" in
        */zsh)  echo "$HOME/.zshrc" ;;
        */bash) echo "$HOME/.bashrc" ;;
        */fish) echo "$HOME/.config/fish/config.fish" ;;
        *)      echo "" ;;
    esac
}

SHELL_RC=$(detect_shell_rc)

# ------------------------------------------------------------------
# CHECK IF INSTALLED
# ------------------------------------------------------------------
if [[ ! -f "$TARGET" ]]; then
    echo "Nothing to uninstall — $TARGET not found."
    exit 0
fi

installed_version="unknown"
if [[ -f "$VERSION_FILE" ]]; then
    installed_version=$(head -n1 "$VERSION_FILE" 2>/dev/null || echo "unknown")
fi
echo "Found claude-launcher-plus v$installed_version at $TARGET"
echo ""

# ------------------------------------------------------------------
# NON-INTERACTIVE CHECK
# ------------------------------------------------------------------
if [[ ! -t 0 ]]; then
    echo "Non-interactive mode — uninstall requires confirmation prompts."
    echo "Run interactively, or manually remove:"
    echo "  rm $TARGET"
    echo "  rm $VERSION_FILE"
    exit 0
fi

# ------------------------------------------------------------------
# TRACKING
# ------------------------------------------------------------------
removed=()
kept=()

# ------------------------------------------------------------------
# CONFIRM BINARY REMOVAL
# ------------------------------------------------------------------
read -rp "Remove $TARGET? [y/N] " answer </dev/tty
if [[ ! "$answer" =~ ^[Yy] ]]; then
    echo "Uninstall cancelled."
    exit 0
fi

rm "$TARGET"
removed+=("$TARGET")

# ------------------------------------------------------------------
# REMOVE VERSION FILE
# ------------------------------------------------------------------
if [[ -f "$VERSION_FILE" ]]; then
    rm "$VERSION_FILE"
    removed+=("$VERSION_FILE")
fi

# ------------------------------------------------------------------
# OFFER PIPENV VIRTUALENV REMOVAL
# ------------------------------------------------------------------
if command -v pipenv &>/dev/null; then
    echo ""
    read -rp "Remove pipenv virtualenv (Python package sandbox)? [y/N] " answer </dev/tty
    if [[ "$answer" =~ ^[Yy] ]]; then
        pipenv --rm 2>/dev/null || true
        removed+=("pipenv virtualenv")
    else
        kept+=("pipenv virtualenv")
    fi
fi

# ------------------------------------------------------------------
# OFFER API-KEY-HELPER REMOVAL
# ------------------------------------------------------------------
KEY_HELPER="$HOME/.claude/api-key-helper.sh"
if [[ -f "$KEY_HELPER" ]]; then
    echo ""
    read -rp "Remove $KEY_HELPER (LM Studio auth helper)? [y/N] " answer </dev/tty
    if [[ "$answer" =~ ^[Yy] ]]; then
        rm "$KEY_HELPER"
        removed+=("$KEY_HELPER")
    else
        kept+=("$KEY_HELPER")
    fi
fi

# ------------------------------------------------------------------
# OFFER PROVIDERS.JSON REMOVAL
# ------------------------------------------------------------------
if [[ -f "$PROVIDERS_FILE" ]]; then
    echo ""
    read -rp "Remove $PROVIDERS_FILE (provider API keys/config)? [y/N] " answer </dev/tty
    if [[ "$answer" =~ ^[Yy] ]]; then
        rm "$PROVIDERS_FILE"
        removed+=("$PROVIDERS_FILE")
    else
        kept+=("$PROVIDERS_FILE")
    fi
fi

# ------------------------------------------------------------------
# OFFER PATH LINE REMOVAL
# ------------------------------------------------------------------
if [[ -n "$SHELL_RC" ]] && [[ -f "$SHELL_RC" ]]; then
    # Remove PATH entry
    if grep -q "# Added by claude-launcher-plus installer" "$SHELL_RC" 2>/dev/null; then
        echo ""
        read -rp "Remove $PREFIX PATH entry from $SHELL_RC? [y/N] " answer </dev/tty
        if [[ "$answer" =~ ^[Yy] ]]; then
            # macOS sed needs '' after -i, Linux does not
            if [[ "$(uname)" == "Darwin" ]]; then
                sed -i '' '/# Added by claude-launcher-plus installer/d' "$SHELL_RC"
                sed -i '' "\|export PATH=\"$PREFIX:\$PATH\"|d" "$SHELL_RC"
                sed -i '' "\|alias clp=\"$TARGET\"|d" "$SHELL_RC"
            else
                sed -i '/# Added by claude-launcher-plus installer/d' "$SHELL_RC"
                sed -i "\|export PATH=\"$PREFIX:\$PATH\"|d" "$SHELL_RC"
                sed -i "\|alias clp=\"$TARGET\"|d" "$SHELL_RC"
            fi
            removed+=("PATH entry in $SHELL_RC")
            removed+=("clp alias in $SHELL_RC")
        else
            kept+=("PATH entry in $SHELL_RC")
        fi
    fi
fi

# ------------------------------------------------------------------
# SUMMARY
# ------------------------------------------------------------------
echo ""
echo "Uninstall complete."
echo ""
for item in "${removed[@]}"; do
    echo "  Removed: $item"
done
for item in "${kept[@]}"; do
    echo "  Kept:    $item"
done
if [[ -f "$SETTINGS_FILE" ]]; then
    echo "  Kept:    $SETTINGS_FILE (managed by Claude Code, not removed)"
fi
echo ""
echo "claude-launcher-plus has been uninstalled."
