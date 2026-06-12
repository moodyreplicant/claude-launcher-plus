#!/usr/bin/env bash
# install.sh — Installer for claude-launcher-plus (v2 package)
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
PACKAGE_DIR="$SCRIPT_DIR/claude_launcher"

# ------------------------------------------------------------------
# PRE-FLIGHT CHECKS
# ------------------------------------------------------------------
if [[ ! -f "$SOURCE_SCRIPT" ]]; then
    echo "Error: $SCRIPT_NAME.py not found in current directory."
    echo "Run this from the cloned repository."
    exit 1
fi
if [[ ! -d "$PACKAGE_DIR" ]]; then
    echo "Error: claude_launcher/ package directory not found."
    echo "Run this from the cloned repository root."
    exit 1
fi

# ------------------------------------------------------------------
# PYTHON CHECK
# ------------------------------------------------------------------
if ! command -v python3 &>/dev/null; then
    echo "Error: python3 is required but not found in PATH."
    echo "Install Python 3.11+ (via brew, apt, or python.org) and try again."
    exit 1
fi
PYTHON_VERSION=$(python3 -c 'import sys; print(f"{sys.version_info.major}.{sys.version_info.minor}")')
PYTHON_MAJOR=$(echo "$PYTHON_VERSION" | cut -d. -f1)
PYTHON_MINOR=$(echo "$PYTHON_VERSION" | cut -d. -f2)
if [[ "$PYTHON_MAJOR" -lt 3 ]] || { [[ "$PYTHON_MAJOR" -eq 3 ]] && [[ "$PYTHON_MINOR" -lt 11 ]]; }; then
    echo "Error: Python 3.11+ required, found $PYTHON_VERSION."
    exit 1
fi

# ------------------------------------------------------------------
# PIPENV CHECK & INSTALL
# ------------------------------------------------------------------
if ! command -v pipenv &>/dev/null; then
    echo "pipenv not found — installing via pip..."
    python3 -m pip install --user pipenv 2>/dev/null || {
        echo "Error: Failed to install pipenv. Install it manually:"
        echo "  python3 -m pip install --user pipenv"
        exit 1
    }
fi

# ------------------------------------------------------------------
# VERSION EXTRACTION
#   Reads VERSION from claude_launcher/__init__.py
# ------------------------------------------------------------------
SOURCE_VERSION=$(sed -n 's/^VERSION *= *"\([^"]*\)".*/\1/p' "$PACKAGE_DIR/__init__.py" 2>/dev/null || true)
if [[ -z "$SOURCE_VERSION" ]]; then
    echo "Warning: Could not detect version."
    SOURCE_VERSION="unknown"
fi

# ------------------------------------------------------------------
# DETECT INSTALLED VERSION
# ------------------------------------------------------------------
installed_version=""
if [[ -f "$VERSION_FILE" ]]; then
    installed_version=$(head -n1 "$VERSION_FILE" 2>/dev/null || true)
fi

# ------------------------------------------------------------------
# INSTALL / UPGRADE DECISION
# ------------------------------------------------------------------
do_install=true
if [[ -n "$installed_version" ]]; then
    if [[ "$installed_version" == "$SOURCE_VERSION" ]]; then
        echo "claude-launcher-plus v$SOURCE_VERSION is already installed."
        do_install=false
    else
        echo "Upgrading claude-launcher-plus v$installed_version → v$SOURCE_VERSION"
    fi
else
    echo "Installing claude-launcher-plus v$SOURCE_VERSION"
fi

# ------------------------------------------------------------------
# MIGRATION DETECTION (from old single-file launcher)
# ------------------------------------------------------------------
migration_notice=false
if [[ -f "$TARGET" ]]; then
    first_line=$(head -1 "$TARGET" 2>/dev/null || true)
    if [[ "$first_line" == "#!/usr/bin/env bash" ]]; then
        migration_notice=true
    elif [[ "$first_line" == "#!/usr/bin/env python3" ]]; then
        # Old Python single-file version — also a migration target
        migration_notice=true
    fi
fi

# ------------------------------------------------------------------
# INSTALL (if needed)
# ------------------------------------------------------------------
if $do_install; then
    if $migration_notice; then
        echo ""
        echo "  ─── Migrating to v$SOURCE_VERSION (modular package) ───"
        echo "  Your providers.json and settings are preserved."
        echo ""
    fi

    # Install pipenv dependencies
    echo "  Installing Python dependencies via pipenv..."
    cd "$SCRIPT_DIR"
    pipenv install --dev 2>/dev/null || {
        echo "Warning: pipenv install failed — you may need to run it manually."
    }

    # Install launcher wrapper
    mkdir -p "$PREFIX"
    cat > "$TARGET" << 'WRAPPER'
#!/usr/bin/env bash
# claude-launcher-plus wrapper — delegates to pipenv-managed package
set -euo pipefail
DIR="$(cd "$(dirname "$(readlink "$0" || echo "$0")")" && pwd)"
cd "$DIR/.."
exec pipenv run python3 claude-launcher-plus.py "$@"
WRAPPER
    chmod +x "$TARGET"
    mkdir -p "$HOME/.claude"
    echo "$SOURCE_VERSION" > "$VERSION_FILE"

    # Create symlink to repo for pipenv to work
    echo "Installed wrapper to $TARGET"
else
    echo ""
fi

# ------------------------------------------------------------------
# VERSION VERIFICATION
# ------------------------------------------------------------------
echo "  Verifying installation..."
if cd "$SCRIPT_DIR" && pipenv run python3 claude-launcher-plus.py --version &>/dev/null; then
    echo "  $(pipenv run python3 claude-launcher-plus.py --version) — OK"
else
    echo "  Warning: Version check failed. Try running manually:"
    echo "    cd $SCRIPT_DIR && pipenv run python3 claude-launcher-plus.py --version"
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
        echo ""
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
    if [[ -t 0 ]] && [[ -n "$SHELL_RC" ]]; then
        read -rp "Add $PREFIX to your $SHELL_RC PATH? [Y/n] " answer </dev/tty
        if [[ ! "$answer" =~ ^[Nn] ]]; then
            touch "$SHELL_RC"
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
        echo "Add $PREFIX to your PATH to use 'clp' from anywhere:"
        echo "  echo 'export PATH=\"$PREFIX:\$PATH\"' >> $SHELL_RC"
    fi
fi
