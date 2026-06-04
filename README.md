# Claude Code Launcher Plus

[![License: MIT](https://img.shields.io/badge/License-MIT-green.svg)](LICENSE)
[![Platform](https://img.shields.io/badge/platform-macOS%20%7C%20Linux%20%7C%20Windows-lightgrey)]()
[![CI](https://github.com/moodyreplicant/claude-launcher-plus/actions/workflows/ci.yml/badge.svg)](https://github.com/moodyreplicant/claude-launcher-plus/actions/workflows/ci.yml)

An enhanced launcher for [Claude Code](https://docs.anthropic.com/en/docs/claude-code) with support for **local** (LM Studio), **cloud** (Anthropic OAuth), and **custom provider** modes (DeepSeek, OpenRouter, or any Anthropic-compatible API).

> **v2.0.0** — Rewritten in Python. Zero new dependencies, native Windows support, env-var references for API keys (no secrets in config files), and the interactive menu now loops after Claude exits.

<p align="center">
  <img src="clp.png" alt="Claude Code Launcher Plus — interactive menu" width="680">
</p>

### Why This Exists

Claude Code normally requires an Anthropic API key or OAuth login. The original [claude-code-offline-local-models](https://www.gui.codes/articles/claude-code-offline-local-models) guide by [@gmotzespina](https://github.com/gmotzespina) showed how to redirect Claude Code to a local LM Studio instance — unlocking offline use and freedom from API rate limits.

**Claude Code Launcher Plus** builds on that foundation, adding:
- A unified menu for local, cloud, and custom provider modes
- Static model selection so you can switch between multiple models per provider without editing files
- DeepSeek and OpenRouter support out of the box
- CLI subcommands for scripting and automation
- **New in v2.0.0:** Python rewrite, Windows support, env-var API key references, menu looping

---

## What It Does

- **3 launch modes** — pick local, cloud, or custom provider from an interactive menu or CLI flag
- **Auto-detect LM Studio models** — discovers loaded LLMs on your machine and presents a picker
- **Custom providers with model picker** — configure providers in `~/.claude/providers.json` and choose from multiple static models per provider
- **Zero-config cloud mode** — launches standard Claude Code with your Anthropic account
- **Menu returns after exit** — the interactive loop continues after Claude Code closes (no more `exec`)

---

## Prerequisites

| Dependency | Check | Needed For |
|-----------|-------|------------|
| `python3` 3.6+ | `python3 --version` | Runtime (macOS 12+ / Ubuntu 20.04+ ship 3.9+) |
| `claude` | `claude --version` | Claude Code CLI (installed separately) |
| `curl` | `curl --version` | LM Studio health checks (optional — `urllib` fallback) |

---

## Installation

### macOS & Linux

```bash
git clone https://github.com/moodyreplicant/claude-launcher-plus.git
cd claude-launcher-plus
./install.sh   # installs to ~/.local/bin/claude-launcher-plus
```

The installer:
- Checks Python 3.6+ is available
- Detects and migrates from the old bash-based launcher
- Offers to add `~/.local/bin` to your PATH
- Creates a `clp` alias in your shell config
- Copies the providers.json template (only if none exists)

### Windows

**PowerShell (recommended):**

```powershell
git clone https://github.com/moodyreplicant/claude-launcher-plus.git
cd claude-launcher-plus
powershell -ExecutionPolicy Bypass -File install.ps1
```

Installs to `%LOCALAPPDATA%\Programs\claude-launcher-plus\` and adds to your user PATH.

**Manual (CMD or PowerShell):**

```cmd
copy claude-launcher-plus.py %LOCALAPPDATA%\Programs\claude-launcher-plus\
copy claude-launcher-plus.bat %LOCALAPPDATA%\Programs\claude-launcher-plus\
```

Then add the folder to your PATH, or run via the `.bat` wrapper.

### Manual Install (any platform)

```bash
# Download and make executable
chmod +x claude-launcher-plus.py
./claude-launcher-plus.py   # interactive menu
```

---

## Configuration

### Custom Providers (v2 — recommended)

Copy the template:

```bash
mkdir -p ~/.claude
cp providers.json ~/.claude/providers.json
```

**v2 format uses `$VAR` references** — your API keys stay in environment variables, never in the config file:

```json
{
  "version": 2,
  "providers": {
    "Deepseek": {
      "description": "DeepSeek API (Anthropic-compatible endpoint)",
      "website": "https://platform.deepseek.com",
      "env": {
        "ANTHROPIC_BASE_URL": "https://api.deepseek.com/anthropic",
        "ANTHROPIC_AUTH_TOKEN": "$DEEPSEEK_API_KEY",
        "ANTHROPIC_MODEL": "deepseek-v4-pro[1m]",
        "ANTHROPIC_DEFAULT_OPUS_MODEL": "deepseek-v4-pro[1m]",
        "ANTHROPIC_DEFAULT_SONNET_MODEL": "deepseek-v4-pro[1m]",
        "ANTHROPIC_DEFAULT_HAIKU_MODEL": "deepseek-v4-flash[1m]",
        "CLAUDE_CODE_DISABLE_NONESSENTIAL_TRAFFIC": "1",
        "CLAUDE_CODE_EFFORT_LEVEL": "max"
      },
      "models": [
        {
          "name": "Deepseek V4 Pro (1M ctx)",
          "env": {
            "ANTHROPIC_MODEL": "deepseek-v4-pro[1m]",
            "ANTHROPIC_DEFAULT_OPUS_MODEL": "deepseek-v4-pro[1m]",
            "ANTHROPIC_DEFAULT_SONNET_MODEL": "deepseek-v4-pro[1m]",
            "ANTHROPIC_DEFAULT_HAIKU_MODEL": "deepseek-v4-flash[1m]"
          }
        },
        {
          "name": "Deepseek V4 Flash (1M ctx)",
          "env": {
            "ANTHROPIC_MODEL": "deepseek-v4-flash[1m]",
            "ANTHROPIC_DEFAULT_OPUS_MODEL": "deepseek-v4-flash[1m]",
            "ANTHROPIC_DEFAULT_SONNET_MODEL": "deepseek-v4-flash[1m]",
            "ANTHROPIC_DEFAULT_HAIKU_MODEL": "deepseek-v4-flash[1m]"
          }
        }
      ]
    },
    "OpenRouter": {
      "description": "OpenRouter — unified API for many model providers",
      "website": "https://openrouter.ai",
      "env": {
        "OPENROUTER_API_KEY": "$OPENROUTER_API_KEY",
        "ANTHROPIC_BASE_URL": "https://openrouter.ai/api",
        "ANTHROPIC_AUTH_TOKEN": "$OPENROUTER_API_KEY",
        "ANTHROPIC_MODEL": "poolside/laguna-m.1:free",
        "CLAUDE_CODE_DISABLE_NONESSENTIAL_TRAFFIC": "1",
        "CLAUDE_CODE_EFFORT_LEVEL": "max"
      },
      "models": [
        {
          "name": "NVIDIA: Nemotron 3 Super (free)",
          "env": { "ANTHROPIC_MODEL": "nvidia/nemotron-3-super-120b-a12b:free" }
        },
        {
          "name": "Poolside: Laguna M.1 (free)",
          "env": { "ANTHROPIC_MODEL": "poolside/laguna-m.1:free" }
        },
        {
          "name": "OpenAI: gpt-oss-120b (free)",
          "env": { "ANTHROPIC_MODEL": "openai/gpt-oss-120b:free" }
        }
      ]
    }
  }
}
```

Then export your keys in your shell profile (`~/.zshrc`, `~/.bashrc`, or `~/.profile`):

```bash
export DEEPSEEK_API_KEY="sk-your-key"
export OPENROUTER_API_KEY="sk-or-your-key"
```

**v1 format (plaintext keys) is still supported** — the launcher detects the absence of `"version"` and handles v1 transparently.

**How models work:**
- If a provider has a `models` array, you pick from it after selecting the provider
- Model-level `env` vars are merged on top of provider-level `env` (model overrides provider)
- If a provider has no `models` array, the provider-level env is used as-is

---

## Usage

### Interactive Menu

```bash
clp
# or: python3 claude-launcher-plus.py
```

### CLI Commands

```bash
# Launch modes
clp local          # LM Studio
clp cloud          # Anthropic OAuth
clp custom         # Custom provider (with model picker)

# Status & discovery
clp status         # Show config + LM Studio status
clp list-providers     # List configured providers
clp list-models OpenRouter    # List models for a provider

# Validation (no launch)
clp --dry-run custom    # Validate config + connectivity

# Help
clp --help
```

---

## Settings Management

### Which keys the launcher manages

The launcher writes to `~/.claude/settings.json` to configure the active provider.
It **only touches these keys** — everything else you set is preserved across mode switches.

| Key | Purpose | Set By |
|-----|---------|--------|
| `apiKeyHelper` | Path to auth script | `local` mode |
| `env.ANTHROPIC_BASE_URL` | API endpoint | `custom` mode |
| `env.ANTHROPIC_MODEL` | Model ID | `custom` mode |
| `env.ANTHROPIC_AUTH_TOKEN` | API key | `custom` mode |
| `env.CLAUDE_CODE_DISABLE_NONESSENTIAL_TRAFFIC` | Telemetry off | `custom` mode |
| `env.CLAUDE_CODE_EFFORT_LEVEL` | Effort/thinking | `custom` mode |
| `env.ANTHROPIC_DEFAULT_{OPUS,SONNET,HAIKU}_MODEL` | Default model aliases | `custom` mode |
| `env.OPENROUTER_API_KEY` | OpenRouter key | `custom` mode (OpenRouter) |

### Preserving your personal settings

Claude Code merges settings from **three scopes**, with higher scopes overriding lower:

| Scope | Location | Priority | Touched by launcher? |
|-------|----------|----------|---------------------|
| User (global) | `~/.claude/settings.json` | Lowest | **Yes** — provider config written here |
| Project | `.claude/settings.json` | Medium | No |
| **Local** | `.claude/settings.local.json` | **Highest** | **No** |

**Recommended:** Put personal settings in `.claude/settings.local.json` in your project.
The launcher never touches this file.

---

## Upgrading from v1.x (bash launcher)

If you installed the old bash-based launcher (v1.0.0–v1.3.0), just run the new installer:

```bash
git pull
./install.sh
```

Your `providers.json` and `settings.json` are preserved. The `clp` alias continues working.
The old `api-key-helper.sh` is regenerated with restricted permissions on next local-mode launch.

To roll back, check out the `v1.3.0` tag and run `install.sh` from there.

---

## Environment Variables

| Variable | Default | Description |
|----------|---------|-------------|
| `LM_STUDIO_HOST` | `localhost` | LM Studio server hostname |
| `LM_STUDIO_PORT` | `1234` | LM Studio server port |
| `LM_STUDIO_API_KEY` | `lm-studio` | LM Studio API key |
| `NO_COLOR` | (unset) | Disable colored output |

**Provider API keys** (v2 format — set these in your shell profile, not in providers.json):

| Variable | Provider |
|----------|----------|
| `DEEPSEEK_API_KEY` | Deepseek |
| `OPENROUTER_API_KEY` | OpenRouter |

---

## Uninstall

```bash
# Run the uninstaller from the cloned repository
./uninstall.sh
```

The uninstaller will:
- Confirm before removing the binary
- Offer to remove `~/.claude/providers.json` (your provider config)
- Offer to remove `~/.claude/api-key-helper.sh` (LM Studio auth helper)
- Offer to clean up the PATH entry added by the installer
- Leave Claude Code's own files (`~/.claude/settings.json`) untouched

---

## Troubleshooting

**"LM Studio: offline" but server is running**
Make sure the LM Studio API server is started. Check: `curl http://localhost:1234/api/v1/models`

**Custom provider not working**
- Verify `~/.claude/providers.json` exists and has valid JSON
- v2 format: make sure `DEEPSEEK_API_KEY` (or your provider's env var) is exported
- v1 format: check `ANTHROPIC_AUTH_TOKEN` matches your API key
- Run `clp --dry-run custom` to validate without launching

**"Missing required dependencies"**
```bash
# macOS
brew install python3

# Ubuntu/Debian
sudo apt install python3

# Windows
winget install Python.Python.3
```
Install [Claude Code](https://docs.anthropic.com/en/docs/claude-code) separately.

**Environment variable not found (v2 providers)**
```
Error: Environment variable 'DEEPSEEK_API_KEY' is not set.
Required by provider 'Deepseek'.
Add 'export DEEPSEEK_API_KEY=<your-key>' to your shell config and restart your shell.
```
Set the variable in `~/.zshrc`, `~/.bashrc`, or `~/.profile` and restart your terminal.

---

## License

MIT — see [LICENSE](LICENSE).

---

## Credits

- **[gui.codes](https://www.gui.codes/articles/claude-code-offline-local-models)** — Original blog post demonstrating Claude Code → LM Studio redirection
- **[@gmotzespina](https://github.com/gmotzespina)** — Creator of the original `claude-launcher.sh`
- This project extends the original with a unified multi-mode menu, custom provider support, static model selection, and a Python rewrite for cross-platform support
