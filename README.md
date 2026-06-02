# Claude Code Launcher Plus

An enhanced launcher for [Claude Code](https://claude.ai) with support for local (LM Studio), cloud (Anthropic), and custom provider modes (e.g., DeepSeek, OpenRouter).

## Usage

```bash
./claude-launcher-plus.sh [local|cloud|custom|status|help]
```

- **local** — Launch Claude Code connected to a local LM Studio instance
- **cloud** — Launch Claude Code with your Anthropic account
- **custom** — Launch Claude Code with a custom provider (configured in `~/.claude/providers.json`)
- **status** — Show current configuration and LM Studio status
- *(no argument)* — Interactive menu

## Custom Providers

Configure custom providers in `~/.claude/providers.json`. See the [plan](plans/openrouter-models.md) for extending providers with static model selection.