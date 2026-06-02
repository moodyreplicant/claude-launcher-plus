# Claude Code Launcher Plus

[![License: MIT](https://img.shields.io/badge/License-MIT-green.svg)](LICENSE)
[![Platform](https://img.shields.io/badge/platform-macOS%20%7C%20Linux-lightgrey)]()

An enhanced launcher for [Claude Code](https://docs.anthropic.com/en/docs/claude-code) with support for **local** (LM Studio), **cloud** (Anthropic OAuth), and **custom provider** modes (DeepSeek, OpenRouter, or any Anthropic-compatible API).

### Why This Exists

Claude Code normally requires an Anthropic API key or OAuth login. The original [claude-code-offline-local-models](https://www.gui.codes/articles/claude-code-offline-local-models) guide by [@gmotzespina](https://github.com/gmotzespina) showed how to redirect Claude Code to a local LM Studio instance — unlocking offline use and freedom from API rate limits.

**Claude Code Launcher Plus** builds on that foundation, adding:
- A unified menu for local, cloud, and custom provider modes
- Static model selection so you can switch between multiple models per provider without editing files
- DeepSeek and OpenRouter support out of the box
- CLI subcommands for scripting and automation

---

## What It Does

- **3 launch modes** — pick local, cloud, or custom provider from an interactive menu or CLI flag
- **Auto-detect LM Studio models** — discovers loaded LLMs on your machine and presents a picker
- **Custom providers with model picker** — configure providers in `~/.claude/providers.json` and choose from multiple static models per provider
- **Zero-config cloud mode** — launches standard Claude Code with your Anthropic account

---

## Prerequisites

| Dependency | Check | Needed For |
|-----------|-------|------------|
| `bash` 3.2+ | `bash --version` | Runtime (macOS default) |
| `python3` | `python3 --version` | JSON parsing in launcher |
| `curl` | `curl --version` | LM Studio API calls |
| `claude` | `claude --version` | Claude Code CLI (installed separately) |

---

## Installation

### Quick Install (recommended)

```bash
git clone https://github.com/moodyreplicant/claude-launcher-plus.git
cd claude-launcher-plus
./install.sh   # installs to ~/.local/bin/claude-launcher-plus
```

### Manual Install

```bash
# Download the script
curl -O https://raw.githubusercontent.com/moodyreplicant/claude-launcher-plus/main/claude-launcher-plus.sh

# Make executable
chmod +x claude-launcher-plus.sh

# Move to your PATH
mv claude-launcher-plus.sh /usr/local/bin/claude-launcher-plus   # macOS/Linux
# or: mv claude-launcher-plus.sh ~/.local/bin/claude-launcher-plus
```

### Add a Shell Alias (no PATH changes needed)

Add this line to your shell config to run `clp` from any terminal:

```bash
# For zsh (macOS default) — add to ~/.zshrc
echo 'alias clp="$HOME/.local/bin/claude-launcher-plus"' >> ~/.zshrc
source ~/.zshrc

# For bash — add to ~/.bashrc or ~/.bash_profile
echo 'alias clp="$HOME/.local/bin/claude-launcher-plus"' >> ~/.bashrc
source ~/.bashrc

# For fish — add to ~/.config/fish/config.fish
echo 'alias clp="$HOME/.local/bin/claude-launcher-plus"' >> ~/.config/fish/config.fish
```

---

## Configuration

### Custom Providers

Copy the template and edit your API keys:

```bash
mkdir -p ~/.claude
cp providers.json ~/.claude/providers.json
```

Edit `~/.claude/providers.json` with your API keys:

```json
{
  "providers": {
    "Deepseek": {
      "env": {
        "ANTHROPIC_BASE_URL": "https://api.deepseek.com/anthropic",
        "ANTHROPIC_AUTH_TOKEN": "sk-your-deepseek-key",
        "ANTHROPIC_MODEL": "deepseek-v4-pro[1m]",
        "CLAUDE_CODE_DISABLE_NONESSENTIAL_TRAFFIC": "1"
      },
      "models": [
        {
          "name": "Deepseek V4 Pro (1M ctx)",
          "env": { "ANTHROPIC_MODEL": "deepseek-v4-pro[1m]" }
        },
        {
          "name": "Deepseek V4 Flash (1M ctx)",
          "env": { "ANTHROPIC_MODEL": "deepseek-v4-flash[1m]" }
        }
      ]
    },
    "OpenRouter": {
      "env": {
        "OPENROUTER_API_KEY": "sk-or-your-key",
        "ANTHROPIC_BASE_URL": "https://openrouter.ai/api",
        "ANTHROPIC_AUTH_TOKEN": "sk-or-your-key",
        "CLAUDE_CODE_DISABLE_NONESSENTIAL_TRAFFIC": "1"
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

**How models work:**
- If a provider has a `models` array, you pick from it after selecting the provider
- Model-level `env` vars are merged on top of provider-level `env` (model overrides provider)
- If a provider has no `models` array, the provider-level env is used as-is
- Any env var can be overridden in a model entry, not just `ANTHROPIC_MODEL`

---

## Usage

### Interactive Menu

```bash
clp
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

# Help
clp help
```

---

## Environment Variables

| Variable | Default | Description |
|----------|---------|-------------|
| `LM_STUDIO_HOST` | `localhost` | LM Studio server hostname |
| `LM_STUDIO_PORT` | `1234` | LM Studio server port |
| `LM_STUDIO_API_KEY` | `lm-studio` | LM Studio API key (for apiKeyHelper) |
| `NO_COLOR` | (unset) | Set to any value to disable colored output |

---

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

---

## Troubleshooting

**"LM Studio: offline" but server is running**
Make sure the LM Studio API server is started. Check: `curl http://localhost:1234/api/v1/models`

**Custom provider not working**
- Verify `~/.claude/providers.json` exists and has valid JSON
- Check `ANTHROPIC_AUTH_TOKEN` matches your API key
- Confirm the `ANTHROPIC_BASE_URL` is correct for your provider

**"Missing required dependencies"**
Install missing tools:
```bash
# macOS
brew install python3 curl

# Ubuntu/Debian
sudo apt install python3 curl
```
Install [Claude Code](https://docs.anthropic.com/en/docs/claude-code) separately.

**Permission denied**
```bash
chmod +x claude-launcher-plus.sh
```

---

## License

MIT — see [LICENSE](LICENSE).

---

## Credits

- **[gui.codes](https://www.gui.codes/articles/claude-code-offline-local-models)** — The original blog post that demonstrated how to redirect Claude Code to a local LM Studio server, making offline local models possible
- **[@gmotzespina](https://github.com/gmotzespina)** — Creator of the original `claude-launcher.sh` script that this project is based on
- This project extends the original with a unified multi-mode menu, custom provider support, and static model selection
