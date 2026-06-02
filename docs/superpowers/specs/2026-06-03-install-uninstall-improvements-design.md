# Design: Improved install.sh & new uninstall.sh

**Date:** 2026-06-03
**Status:** Approved

## Overview

Improve `install.sh` with version tracking, upgrade detection, and interactive PATH setup. Create a matching `uninstall.sh` that safely removes what was installed.

## Design Decisions (settled)

| Decision | Choice | Rationale |
|----------|--------|-----------|
| Uninstall thoroughness | Standard: binary + providers.json offer | Leave Claude Code's own files alone |
| Upgrade behavior | Detect version, skip if same, overwrite if different | Safe, scriptable |
| PATH handling | Offer to add interactively | User stays in control |
| Version tracking | Metadata file `~/.claude/.clp-version` with grep fallback | Reliable primary, tolerant fallback |
| Root guard | Refuse to run as root/sudo | Everything lives in `$HOME` |

## Files

| File | Action | Purpose |
|------|--------|---------|
| `install.sh` | Rewrite | Version-aware install with PATH offer |
| `uninstall.sh` | **New** | Safe removal with confirmations |

## install.sh — Specification

### Behavior flow

```
1. Root check → exit if EUID 0
2. Detect shell (zsh/bash/fish)
3. Check for existing installation
   a. Read ~/.claude/.clp-version
   b. Fallback: grep VERSION= from installed binary
4. If installed and same version → "Already up to date (vX.Y.Z)" → skip to PATH check
5. If installed and different version → "Upgrading vOLD → vNEW" → proceed
6. If not installed → "Installing vNEW" → proceed
7. Copy claude-launcher-plus.sh → ~/.local/bin/claude-launcher-plus
8. chmod +x
9. Write ~/.claude/.clp-version with new version string
10. Copy providers.json → ~/.claude/providers.json (only if not present)
11. Check if ~/.local/bin is in PATH
    a. If yes → done
    b. If no → ask "Add ~/.local/bin to your ~/.<shellrc> PATH? [Y/n]"
       - On yes → append export line → print "Run source ~/.<shellrc> to apply"
       - On no → print manual instructions
```

### Version extraction

- **Primary:** Read first line of `~/.claude/.clp-version` (just the version string, e.g. `1.1.0`)
- **Fallback:** `grep -oP 'VERSION="\K[^"]+' "$TARGET"` on the installed binary
- Source version: same grep on the repo copy of `claude-launcher-plus.sh`

### Shell detection

```bash
case "$SHELL" in
    */zsh)   rc="$HOME/.zshrc" ;;
    */bash)  rc="$HOME/.bashrc" ;;
    */fish)  rc="$HOME/.config/fish/config.fish" ;;
    *)       rc="" ;;  # unknown, print generic instructions
esac
```

### PATH check

Check against both literal and expanded `$HOME`:
```bash
if [[ ":$PATH:" == *":$PREFIX:"* ]]; then ... fi
```

### Root guard

```bash
if [[ "${EUID:-$(id -u)}" -eq 0 ]]; then
    echo "Do not run with sudo — everything installs to your home directory."
    exit 1
fi
```

## uninstall.sh — Specification

### Behavior flow

```
1. Root check → exit if EUID 0
2. Check if ~/.local/bin/claude-launcher-plus exists
   a. If not → "Nothing to uninstall" → exit 0
3. Confirm: "Remove claude-launcher-plus? [y/N]" (default no for safety)
4. Remove binary: rm ~/.local/bin/claude-launcher-plus
5. Remove metadata: rm ~/.claude/.clp-version
6. If ~/.claude/providers.json exists:
   → ask "Remove ~/.claude/providers.json? [y/N]"
   → on yes → rm
7. Detect PATH line added by install.sh in shell config
   → If found → ask "Remove ~/.local/bin PATH entry from ~/.<shellrc>? [y/N]"
   → on yes → remove the exact line
8. Print summary:
   - What was removed
   - What was kept (and where)
```

### PATH line detection

Look for a line matching the pattern `export PATH="$HOME/.local/bin:$PATH"` or `export PATH="$HOME/.local/bin:\$PATH"`. Remove only that exact line (safe `sed` deletion).

### Summary format

```
Uninstall complete.
  Removed: ~/.local/bin/claude-launcher-plus
  Removed: ~/.claude/.clp-version
  Removed: ~/.claude/providers.json
  Kept:    ~/.claude/settings.json (managed by Claude Code)
```

## Edge cases

| Scenario | install.sh | uninstall.sh |
|----------|-----------|--------------|
| Running as root | Exit with message | Exit with message |
| `~/.local/bin` doesn't exist | `mkdir -p` creates it | N/A |
| No shell detected | Print generic PATH instructions | Skip PATH line removal |
| providers.json already exists | Skip, don't overwrite user's config | Offer to remove |
| Script already installed, same version | Skip with message | N/A |
| Nothing installed | N/A | Exit 0 with message |
| `~/.claude/` doesn't exist | Created by `mkdir -p` | Gracefully skip missing files |
| User answers non-interactive (piped) | Skip PATH offer, print instructions | Skip all confirmations, default to "no" (safe) |

## Dependencies

- `bash` 3.2+ (macOS default)
- No new dependencies beyond what the project already requires

## What stays the same

- Install prefix defaults to `$HOME/.local/bin`, overridable via first argument
- providers.json template only copied if destination doesn't exist
- The launcher script itself (`claude-launcher-plus.sh`) is unchanged
