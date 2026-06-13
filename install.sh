#!/usr/bin/env bash
# install.sh — Installer for claude-launcher-plus
# Usage:
#   bash install.sh              # User install (default, lightweight)
#   bash install.sh --user       # Same as above
#   bash install.sh --dev        # Developer install (includes dev deps, hooks)
#   bash install.sh --dev ~/.local/bin  # Custom prefix

set -euo pipefail

# ------------------------------------------------------------------
# CONFIGURATION
# ------------------------------------------------------------------
PREFIX="${2:-$HOME/.local/bin}"
SCRIPT_NAME="claude-launcher-plus"
TARGET="$PREFIX/$SCRIPT_NAME"
PROVIDERS_TEMPLATE="providers.json"
PROVIDERS_DEST="$HOME/.claude/providers.json"
VERSION_FILE="$HOME/.claude/.clp-version"
INSTALL_MODE="${1:-user}"  # user | dev

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
SOURCE_SCRIPT="$SCRIPT_DIR/$SCRIPT_NAME.py"
PACKAGE_DIR="$SCRIPT_DIR/claude_launcher"

# ------------------------------------------------------------------
# PRE-FLIGHT
# ------------------------------------------------------------------
if [[ ! -f "$SOURCE_SCRIPT" ]] || [[ ! -d "$PACKAGE_DIR" ]]; then
    echo "Error: Run this from the cloned repository root (claude-launcher-plus.py + claude_launcher/)."
    exit 1
fi
if [[ "${EUID:-$(id -u)}" -eq 0 ]]; then
    echo "Error: Do not run with sudo — everything installs to your home directory."
    exit 1
fi

# Normalize install mode argument
case "${1:-}" in
    --dev)     INSTALL_MODE="dev" ;;
    --user|"") INSTALL_MODE="user" ;;
    *)
        echo "Usage: bash install.sh [--user|--dev] [PREFIX]"
        echo "  --user  Install for everyday use (lightweight, no dev tools).  [default]"
        echo "  --dev   Developer install (includes pipenv, pre-commit, tests)."
        echo "  PREFIX  Installation directory (default: ~/.local/bin)"
        exit 1
        ;;
esac

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
# VERSION
# ------------------------------------------------------------------
SOURCE_VERSION=$(sed -n 's/^VERSION *= *"\([^"]*\)".*/\1/p' "$PACKAGE_DIR/__init__.py" 2>/dev/null || true)
SOURCE_VERSION="${SOURCE_VERSION:-unknown}"

# ------------------------------------------------------------------
# STATUS
# ------------------------------------------------------------------
installed_version=""
[[ -f "$VERSION_FILE" ]] && installed_version=$(head -n1 "$VERSION_FILE" 2>/dev/null || true)

do_install=true
if [[ -n "$installed_version" ]]; then
    if [[ "$installed_version" == "$SOURCE_VERSION" ]]; then
        echo "claude-launcher-plus v$SOURCE_VERSION is already installed (version file)."
        do_install=false
    else
        echo "Upgrading claude-launcher-plus v$installed_version → v$SOURCE_VERSION"
    fi
else
    echo "Installing claude-launcher-plus v$SOURCE_VERSION ($INSTALL_MODE install)"
fi

# Detect migration from old version
migration_notice=false
if [[ -f "$TARGET" ]]; then
    first_line=$(head -1 "$TARGET" 2>/dev/null || true)
    [[ "$first_line" =~ ^#!/usr/bin/env\ (bash|python3) ]] && migration_notice=true
fi

# ==================================================================
# USER INSTALL — lightweight, no dev dependencies
# ==================================================================
do_user_install() {
    if $migration_notice; then
        echo ""
        echo "  ─── Migrating to v$SOURCE_VERSION ───"
        echo "  Your providers.json and settings are preserved."
        echo ""
    fi

    # Target directory for the package
    INSTALL_DIR="$HOME/.local/share/claude-launcher-plus"
    mkdir -p "$INSTALL_DIR"

    # Copy package and entry point
    cp -r "$PACKAGE_DIR" "$INSTALL_DIR/"
    cp "$SOURCE_SCRIPT" "$INSTALL_DIR/"

    # Install runtime Python dependency
    echo "  Installing runtime dependency (jsonschema)..."
    python3 -m pip install --user jsonschema 2>/dev/null || \
    python3 -m pip install --break-system-packages --user jsonschema 2>/dev/null || {
        echo "  ⚠  jsonschema install failed — install manually: pip3 install --user jsonschema"
    }

    # Create wrapper script
    mkdir -p "$PREFIX"
    cat > "$TARGET" << WRAPPER
#!/usr/bin/env bash
# claude-launcher-plus wrapper — user install
exec python3 "$INSTALL_DIR/$SCRIPT_NAME.py" "\$@"
WRAPPER
    chmod +x "$TARGET"

    mkdir -p "$HOME/.claude"
    chmod 700 "$HOME/.claude"
    echo "$SOURCE_VERSION" > "$VERSION_FILE"

    # Verify
    if "$TARGET" --version &>/dev/null; then
        echo "  ✓ $("$TARGET" --version) installed to $TARGET"
    else
        echo "  ⚠  Installed but version check failed."
    fi
}

# ==================================================================
# DEV INSTALL — pipenv, pre-commit, full environment
# ==================================================================
do_dev_install() {
    # Ensure pipenv
    if ! command -v pipenv &>/dev/null; then
        echo "  Installing pipenv..."
        python3 -m pip install --user pipenv 2>/dev/null || {
            echo "Error: pipenv install failed. Install manually: pip install --user pipenv"
            exit 1
        }
    fi

    if $migration_notice; then
        echo ""
        echo "  ─── Migrating to v$SOURCE_VERSION (modular package) ───"
        echo "  Your providers.json and settings are preserved."
        echo ""
    fi

    # Install Python dependencies
    echo "  Installing Python dependencies via pipenv..."
    cd "$SCRIPT_DIR"
    if pipenv install --dev 2>/dev/null; then
        echo "  ✓ pipenv environment ready"
    else
        echo "  ⚠  pipenv install had issues — run 'pipenv install --dev' manually."
    fi

    # Install pre-commit hooks
    if pipenv run pre-commit install 2>/dev/null; then
        echo "  ✓ pre-commit hooks installed"
    else
        echo "  ⚠  pre-commit install failed — run 'pipenv run pre-commit install' later."
    fi

    # Create wrapper script
    mkdir -p "$PREFIX"
    cat > "$TARGET" << 'WRAPPER'
#!/usr/bin/env bash
# claude-launcher-plus wrapper — dev install (pipenv)
set -euo pipefail
DIR="$(cd "$(dirname "$(readlink "$0" || echo "$0")")" && pwd)"
cd "$DIR/.."
exec pipenv run python3 claude-launcher-plus.py "$@"
WRAPPER
    chmod +x "$TARGET"

    mkdir -p "$HOME/.claude"
    chmod 700 "$HOME/.claude"
    echo "$SOURCE_VERSION" > "$VERSION_FILE"

    # Verify
    if cd "$SCRIPT_DIR" && pipenv run python3 claude-launcher-plus.py --version &>/dev/null; then
        echo "  ✓ $(pipenv run python3 claude-launcher-plus.py --version) — OK"
    else
        echo "  ⚠  Version check failed. Try: cd $SCRIPT_DIR && pipenv run python3 claude-launcher-plus.py --version"
    fi
}

# ==================================================================
# EXECUTE
# ==================================================================
if $do_install; then
    if [[ "$INSTALL_MODE" == "dev" ]]; then
        do_dev_install
    else
        do_user_install
    fi
fi

# ==================================================================
# PROVIDERS TEMPLATE
# ==================================================================
if [[ ! -f "$PROVIDERS_DEST" ]]; then
    if [[ -f "$SCRIPT_DIR/$PROVIDERS_TEMPLATE" ]]; then
        mkdir -p "$HOME/.claude"
    chmod 700 "$HOME/.claude"
        cp "$SCRIPT_DIR/$PROVIDERS_TEMPLATE" "$PROVIDERS_DEST"
        echo "Template providers.json → $PROVIDERS_DEST"
        echo "  Edit it to add your API keys before using custom provider mode."
    fi
else
    $do_install && echo "Existing providers.json left unchanged."
fi

# ==================================================================
# SHELL RC DETECTION
# ==================================================================
detect_shell_rc() {
    case "${SHELL:-}" in
        */zsh)  echo "$HOME/.zshrc" ;;
        */bash) echo "$HOME/.bashrc" ;;
        */fish) echo "$HOME/.config/fish/config.fish" ;;
        *)      echo "" ;;
    esac
}
SHELL_RC=$(detect_shell_rc)

# ==================================================================
# ALIAS SETUP
# ==================================================================
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
            echo "  ✓ clp alias added to $SHELL_RC"
        fi
    fi
fi
echo ""

# ==================================================================
# PATH CHECK
# ==================================================================
if [[ ":$PATH:" == *":$PREFIX:"* ]]; then
    echo "$PREFIX is already in your PATH."
else
    if [[ -t 0 ]] && [[ -n "$SHELL_RC" ]]; then
        echo ""
        read -rp "Add $PREFIX to your $SHELL_RC PATH? [Y/n] " answer </dev/tty
        if [[ ! "$answer" =~ ^[Nn] ]]; then
            touch "$SHELL_RC"
            {
                echo ""
                echo "# Added by claude-launcher-plus installer ($(date +%Y-%m-%d))"
                echo "export PATH=\"$PREFIX:\$PATH\""
            } >> "$SHELL_RC"
            source "$SHELL_RC" 2>/dev/null || true
            echo "  ✓ $PREFIX added to PATH in $SHELL_RC"
        else
            echo "  To add later: echo 'export PATH=\"$PREFIX:\$PATH\"' >> $SHELL_RC"
        fi
    elif [[ -z "$SHELL_RC" ]]; then
        echo "Could not detect your shell. Add $PREFIX to PATH manually."
    else
        echo "Add $PREFIX to PATH: echo 'export PATH=\"$PREFIX:\$PATH\"' >> $SHELL_RC"
    fi
fi

echo ""
echo "Done. Run 'clp' to start."
