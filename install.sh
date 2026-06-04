#!/usr/bin/env bash
# install.sh — Installer for claude-launcher-plus
# Usage: bash install.sh [PREFIX]
#   PREFIX: installation directory (default: $HOME/.local/bin)

set -euo pipefail

# ------------------------------------------------------------------
# ROOT GUARD
# ------------------------------------------------------------------
if [[ "${EUID:-$(id -u)}" -eq 0 ]]; then
    echo "Error: Do not run with sudo — everything installs to your home directory."
    exit 1
fi

# ------------------------------------------------------------------
# CONFIGURATION
# ------------------------------------------------------------------
PREFIX="${1:-$HOME/.local/bin}"
SCRIPT_NAME="claude-launcher-plus"
TARGET="$PREFIX/$SCRIPT_NAME"
PROVIDERS_TEMPLATE="providers.json"
PROVIDERS_DEST="$HOME/.claude/providers.json"
VERSION_FILE="$HOME/.claude/.clp-version"

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
SOURCE_SCRIPT="$SCRIPT_DIR/$SCRIPT_NAME.py"

# ------------------------------------------------------------------
# PRE-FLIGHT CHECKS
# ------------------------------------------------------------------
if [[ ! -f "$SOURCE_SCRIPT" ]]; then
    echo "Error: $SCRIPT_NAME.sh not found in current directory."
    echo "Run this from the cloned repository."
    exit 1
fi

# ------------------------------------------------------------------
# PYTHON CHECK
# ------------------------------------------------------------------
if ! command -v python3 &>/dev/null; then
    echo "Error: python3 is required but not found in PATH."
    echo "Install Python 3.6+ and try again."
    exit 1
fi
PYTHON_VERSION=$(python3 -c 'import sys; print(f"{sys.version_info.major}.{sys.version_info.minor}")')
PYTHON_MAJOR=$(echo "$PYTHON_VERSION" | cut -d. -f1)
PYTHON_MINOR=$(echo "$PYTHON_VERSION" | cut -d. -f2)
if [[ "$PYTHON_MAJOR" -lt 3 ]] || { [[ "$PYTHON_MAJOR" -eq 3 ]] && [[ "$PYTHON_MINOR" -lt 6 ]]; }; then
    echo "Error: Python 3.6+ required, found $PYTHON_VERSION."
    exit 1
fi

# ------------------------------------------------------------------
# VERSION EXTRACTION
#   Handles both bash (VERSION="X.Y.Z") and Python (VERSION = "X.Y.Z")
# ------------------------------------------------------------------
SOURCE_VERSION=$(sed -n 's/^VERSION *= *"\([^"]*\)".*/\1/p' "$SOURCE_SCRIPT")
if [[ -z "$SOURCE_VERSION" ]]; then
    echo "Warning: Could not detect version in $SOURCE_SCRIPT"
    SOURCE_VERSION="unknown"
fi

# ------------------------------------------------------------------
# DETECT INSTALLED VERSION
#   Primary: ~/.claude/.clp-version
#   Fallback: grep VERSION= from installed binary (via sed for portability)
# ------------------------------------------------------------------
installed_version=""
if [[ -f "$VERSION_FILE" ]]; then
    installed_version=$(head -n1 "$VERSION_FILE" 2>/dev/null || true)
fi
if [[ -z "$installed_version" ]] && [[ -f "$TARGET" ]]; then
    installed_version=$(sed -n 's/^VERSION="\([^"]*\)".*/\1/p' "$TARGET" 2>/dev/null || echo "unknown")
fi

# ------------------------------------------------------------------
# INSTALL / UPGRADE DECISION
# ------------------------------------------------------------------
do_install=true
if [[ -n "$installed_version" ]]; then
    if [[ "$installed_version" == "$SOURCE_VERSION" ]]; then
        echo "claude-launcher-plus v$SOURCE_VERSION is already up to date at $TARGET."
        do_install=false
    else
        echo "Upgrading claude-launcher-plus v$installed_version → v$SOURCE_VERSION"
    fi
else
    echo "Installing claude-launcher-plus v$SOURCE_VERSION"
fi

# ------------------------------------------------------------------
# MIGRATION DETECTION
# ------------------------------------------------------------------
migration_notice=false
if [[ -f "$TARGET" ]]; then
    # Check if installed version is the old bash launcher (no .py extension)
    first_line=$(head -1 "$TARGET" 2>/dev/null || true)
    if [[ "$first_line" == "#!/usr/bin/env bash" ]]; then
        migration_notice=true
    fi
fi

# ------------------------------------------------------------------
# INSTALL (if needed)
# ------------------------------------------------------------------
if $do_install; then
    if $migration_notice; then
        echo ""
        echo "  ─── Migrating from bash-based launcher to Python v$SOURCE_VERSION ───"
        echo "  Your providers.json and settings are preserved."
        echo ""
    fi
    mkdir -p "$PREFIX"
    cp "$SOURCE_SCRIPT" "$TARGET"
    chmod +x "$TARGET"
    mkdir -p "$HOME/.claude"
    echo "$SOURCE_VERSION" > "$VERSION_FILE"
    echo "Installed to $TARGET"
else
    echo ""
fi

# ------------------------------------------------------------------
# PROVIDERS TEMPLATE
# ------------------------------------------------------------------
if [[ ! -f "$PROVIDERS_DEST" ]]; then
    if [[ -f "$SCRIPT_DIR/$PROVIDERS_TEMPLATE" ]]; then
        mkdir -p "$HOME/.claude"
        cp "$SCRIPT_DIR/$PROVIDERS_TEMPLATE" "$PROVIDERS_DEST"
        echo "Template providers.json created at $PROVIDERS_DEST"
        echo "Edit it to add your API keys before using custom provider mode."
    fi
else
    if $do_install; then
        echo "Existing providers.json found at $PROVIDERS_DEST — left unchanged."
    fi
fi

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
# ALIAS SETUP
# ------------------------------------------------------------------
if [[ -t 0 ]] && [[ -n "$SHELL_RC" ]]; then
    if grep -q "alias clp=" "$SHELL_RC" 2>/dev/null; then
        echo "clp alias already exists in $SHELL_RC"
    else
        read -rp "Add 'clp' alias to $SHELL_RC? [Y/n] " answer </dev/tty
        if [[ ! "$answer" =~ ^[Nn] ]]; then
            touch "$SHELL_RC"
            {
                echo ""
                echo "# Added by claude-launcher-plus installer ($(date +%Y-%m-%d))"
                echo "alias clp=\"$TARGET\""
            } >> "$SHELL_RC"
            source "$SHELL_RC" 2>/dev/null || true
            echo "Added clp alias to $SHELL_RC and applied."
        fi
    fi
fi
echo ""

# ------------------------------------------------------------------
# PATH CHECK & OFFER
# ------------------------------------------------------------------
if [[ ":$PATH:" == *":$PREFIX:"* ]]; then
    echo "$PREFIX is already in your PATH."
else
    echo ""

    # Interactive mode only
    if [[ -t 0 ]] && [[ -n "$SHELL_RC" ]]; then
        read -rp "Add $PREFIX to your $SHELL_RC PATH? [Y/n] " answer </dev/tty
        if [[ ! "$answer" =~ ^[Nn] ]]; then
            # Ensure rc file exists
            touch "$SHELL_RC"
            # Append with a marker comment so uninstall.sh can find it
            {
                echo ""
                echo "# Added by claude-launcher-plus installer ($(date +%Y-%m-%d))"
                echo "export PATH=\"$PREFIX:\$PATH\""
            } >> "$SHELL_RC"
            source "$SHELL_RC" 2>/dev/null || true
            echo "Added to $SHELL_RC and applied."
        else
            echo "To add manually later:"
            echo "  echo 'export PATH=\"$PREFIX:\$PATH\"' >> $SHELL_RC"
        fi
    elif [[ -z "$SHELL_RC" ]]; then
        echo "Could not detect your shell. Add $PREFIX to your PATH to use 'clp' from anywhere."
    else
        # Non-interactive (piped) — print instructions
        echo "Add $PREFIX to your PATH to use 'clp' from anywhere:"
        echo "  echo 'export PATH=\"$PREFIX:\$PATH\"' >> $SHELL_RC"
    fi
fi
