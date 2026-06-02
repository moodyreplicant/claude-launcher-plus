# Install/Uninstall Script Improvements — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Rewrite `install.sh` with version tracking, upgrade detection, interactive PATH setup, and root guard. Create `uninstall.sh` with safe confirmations and cleanup.

**Architecture:** Two standalone bash scripts. `install.sh` extracts the version from the launcher script via `sed`, tracks installed version in `~/.claude/.clp-version`, and offers to add the install prefix to the user's shell config. `uninstall.sh` reverses these steps with confirmation prompts, defaulting to "no" for safety.

**Tech Stack:** bash 3.2+ (macOS compatible), sed, no external dependencies beyond what the project already uses.

---

### Task 1: Rewrite install.sh

**Files:**
- Modify: `install.sh` (complete rewrite)

- [ ] **Step 1: Write the new install.sh**

```bash
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
SOURCE_SCRIPT="$SCRIPT_DIR/$SCRIPT_NAME.sh"

# ------------------------------------------------------------------
# PRE-FLIGHT CHECKS
# ------------------------------------------------------------------
if [[ ! -f "$SOURCE_SCRIPT" ]]; then
    echo "Error: $SCRIPT_NAME.sh not found in current directory."
    echo "Run this from the cloned repository."
    exit 1
fi

# ------------------------------------------------------------------
# VERSION EXTRACTION
#   Uses sed (not grep -P) for macOS/Linux portability
# ------------------------------------------------------------------
SOURCE_VERSION=$(sed -n 's/^VERSION="\([^"]*\)".*/\1/p' "$SOURCE_SCRIPT")
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
# INSTALL (if needed)
# ------------------------------------------------------------------
if $do_install; then
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
            echo "Added to $SHELL_RC. Run 'source $SHELL_RC' to apply now."
        else
            echo "To add manually later:"
            echo "  echo 'export PATH=\"$PREFIX:\$PATH\"' >> $SHELL_RC"
        fi
    elif [[ -z "$SHELL_RC" ]]; then
        echo "Could not detect your shell. Add $PREFIX to your PATH to use 'claude-launcher-plus' from anywhere."
    else
        # Non-interactive (piped) — print instructions
        echo "Add $PREFIX to your PATH to use 'claude-launcher-plus' from anywhere:"
        echo "  echo 'export PATH=\"$PREFIX:\$PATH\"' >> $SHELL_RC"
    fi
fi
```

- [ ] **Step 2: Verify the existing install.sh is backed up in git history**

```bash
git -C /Users/elero/Desktop/claude-launcher-plus log --oneline -1 -- install.sh
```

- [ ] **Step 3: Commit**

```bash
git add install.sh
git commit -m "feat: rewrite install.sh with version tracking, upgrade detection, and interactive PATH setup

- Root guard: refuses to run as root/sudo
- Version-aware: reads ~/.claude/.clp-version, skips if same version
- Upgrade detection: reports old→new version on upgrade
- Interactive PATH offer: asks before adding to shell rc
- Shell detection: supports zsh, bash, fish
- Safe non-interactive mode: skips prompts, prints instructions
- macOS-portable: uses sed instead of grep -P

Co-Authored-By: Claude Opus 4.8 <noreply@anthropic.com>"
```

---

### Task 2: Create uninstall.sh

**Files:**
- Create: `uninstall.sh`

- [ ] **Step 1: Write uninstall.sh**

```bash
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

installed_version=$(sed -n 's/^VERSION="\([^"]*\)".*/\1/p' "$TARGET" 2>/dev/null || echo "unknown")
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
    if grep -q "# Added by claude-launcher-plus installer" "$SHELL_RC" 2>/dev/null; then
        echo ""
        read -rp "Remove $PREFIX PATH entry from $SHELL_RC? [y/N] " answer </dev/tty
        if [[ "$answer" =~ ^[Yy] ]]; then
            # macOS sed needs '' after -i, Linux does not
            if [[ "$(uname)" == "Darwin" ]]; then
                sed -i '' '/# Added by claude-launcher-plus installer/d' "$SHELL_RC"
                sed -i '' "\|export PATH=\"$PREFIX:\$PATH\"|d" "$SHELL_RC"
            else
                sed -i '/# Added by claude-launcher-plus installer/d' "$SHELL_RC"
                sed -i "\|export PATH=\"$PREFIX:\$PATH\"|d" "$SHELL_RC"
            fi
            removed+=("PATH entry in $SHELL_RC")
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
```

- [ ] **Step 2: Make uninstall.sh executable**

```bash
chmod +x /Users/elero/Desktop/claude-launcher-plus/uninstall.sh
```

- [ ] **Step 3: Commit**

```bash
git add uninstall.sh
git commit -m "feat: add uninstall.sh with safe confirmations

- Root guard: refuses sudo
- Confirms before removing binary (defaults to no)
- Offers providers.json removal (defaults to no)
- Offers PATH line removal from shell config (defaults to no)
- Tracks and reports what was removed vs kept
- Safe non-interactive mode: exits with manual instructions
- macOS/Linux portable sed for PATH line removal

Co-Authored-By: Claude Opus 4.8 <noreply@anthropic.com>"
```

---

### Task 3: Update README.md uninstall section

**Files:**
- Modify: `README.md` (uninstall section, lines 200-209)

- [ ] **Step 1: Replace the manual uninstall section with a reference to the script**

The old text (lines 200-209):
```markdown
## Uninstall

```bash
# Remove the script
rm "$(which claude-launcher-plus)"      # if installed to PATH
# or simply delete wherever you placed it

# Remove provider config (optional)
rm ~/.claude/providers.json
```
```

Replace with:
```markdown
## Uninstall

```bash
# Run the uninstaller from the cloned repository
cd claude-launcher-plus
./uninstall.sh
```

The uninstaller will:
- Confirm before removing `~/.local/bin/claude-launcher-plus`
- Offer to remove `~/.claude/providers.json` (your provider config)
- Offer to clean up the PATH entry added by the installer
- Leave Claude Code's own files (`~/.claude/settings.json`) untouched

To uninstall manually, delete the script from wherever you placed it and optionally remove `~/.claude/providers.json`.
```

- [ ] **Step 2: Also update the "Quick Install" section (line 47) to mention it installs to `~/.local/bin`**

The old text (lines 47-48):
```markdown
./install.sh
```

Replace with:
```markdown
./install.sh   # installs to ~/.local/bin/claude-launcher-plus
```

- [ ] **Step 3: Commit**

```bash
git add README.md
git commit -m "docs: update README with uninstall script reference and install path

Co-Authored-By: Claude Opus 4.8 <noreply@anthropic.com>"
```

---

### Task 4: Verify both scripts

**Files:**
- Test: `install.sh`
- Test: `uninstall.sh`

- [ ] **Step 1: Test install.sh — fresh install**

```bash
# Remove any existing installation to simulate fresh install
rm -f ~/.local/bin/claude-launcher-plus ~/.claude/.clp-version

# Run install.sh
cd /Users/elero/Desktop/claude-launcher-plus
bash install.sh

# Verify binary exists and is executable
test -x ~/.local/bin/claude-launcher-plus && echo "PASS: binary installed and executable" || echo "FAIL: binary missing or not executable"

# Verify version file exists and matches source
expected=$(sed -n 's/^VERSION="\([^"]*\)".*/\1/p' claude-launcher-plus.sh)
actual=$(head -n1 ~/.claude/.clp-version)
[[ "$expected" == "$actual" ]] && echo "PASS: version file matches ($actual)" || echo "FAIL: version mismatch ($actual != $expected)"
```

- [ ] **Step 2: Test install.sh — idempotent (same version)**

```bash
cd /Users/elero/Desktop/claude-launcher-plus
bash install.sh
# Should print: "already up to date" and skip copy
```

- [ ] **Step 3: Test install.sh — non-interactive mode**

```bash
cd /Users/elero/Desktop/claude-launcher-plus
echo "" | bash install.sh 2>&1 | grep -q "already up to date\|Add.*PATH" && echo "PASS: non-interactive mode works" || echo "FAIL"
```

- [ ] **Step 4: Test uninstall.sh — simulated (check behavior without actually removing)**

Read the script to visually verify the confirmation flow:
```bash
bash -n /Users/elero/Desktop/claude-launcher-plus/uninstall.sh
echo "PASS: uninstall.sh passes syntax check" || echo "FAIL: syntax error"
```

- [ ] **Step 5: Test uninstall.sh — non-interactive mode exits safely**

```bash
cd /Users/elero/Desktop/claude-launcher-plus
echo "" | bash uninstall.sh 2>&1 | grep -q "Non-interactive" && echo "PASS: non-interactive safe exit" || echo "Check output"
```

- [ ] **Step 6: Syntax check install.sh**

```bash
bash -n /Users/elero/Desktop/claude-launcher-plus/install.sh
echo "PASS: install.sh passes syntax check" || echo "FAIL: syntax error"
```

---

### Task 5: Final commit for any verification fixes

**Files:**
- Potentially: `install.sh`, `uninstall.sh`

- [ ] **Step 1: Check for any uncommitted changes**

```bash
git -C /Users/elero/Desktop/claude-launcher-plus status
```

- [ ] **Step 2: Commit any remaining changes if needed**

```bash
git -C /Users/elero/Desktop/claude-launcher-plus diff
# Review and commit if issues were fixed during verification
```
