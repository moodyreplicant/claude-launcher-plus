# Plan: Static Model Selection for Custom Providers

## Goal

Allow a provider (e.g., OpenRouter) to define 3+ static model entries so the user can choose both a provider **and** a specific model before launching Claude Code.

---

## `providers.json` – New Schema

Add an optional `models` array per provider. Each model entry overrides the relevant env vars (especially `ANTHROPIC_MODEL`):

```json
{
  "providers": {
    "OpenRouter": {
      "env": {
        "OPENROUTER_API_KEY": "sk-or-v1-...",
        "ANTHROPIC_BASE_URL": "https://openrouter.ai/api",
        "ANTHROPIC_AUTH_TOKEN": "sk-or-v1-...",
        "CLAUDE_CODE_DISABLE_NONESSENTIAL_TRAFFIC": "1"
      },
      "models": [
        {
          "name": "Claude 3.5 Sonnet",
          "env": {
            "ANTHROPIC_MODEL": "anthropic/claude-3.5-sonnet"
          }
        },
        {
          "name": "GPT-4o",
          "env": {
            "ANTHROPIC_MODEL": "openai/gpt-4o"
          }
        },
        {
          "name": "Gemini 2.5 Pro",
          "env": {
            "ANTHROPIC_MODEL": "google/gemini-2.5-pro-exp-03-25:free"
          }
        }
      ]
    },
    "Deepseek": {
      "env": {
        "ANTHROPIC_BASE_URL": "https://api.deepseek.com/anthropic",
        "ANTHROPIC_AUTH_TOKEN": "sk-...",
        "ANTHROPIC_MODEL": "deepseek-v4-pro[1m]",
        "CLAUDE_CODE_DISABLE_NONESSENTIAL_TRAFFIC": "1"
      }
    }
  }
}
```

### Merging Rules

- If a provider has `models`, the user picks from the model list **after** selecting the provider.
- Model-level `env` vars are **merged on top** of the provider-level `env` (model overrides take precedence).
- If a provider has **no** `models` array, the existing behavior is preserved (provider-level env used as-is).
- Old `ANTHROPIC_MODEL` at the provider level acts as a fallback default; model-level `ANTHROPIC_MODEL` overrides it.

---

## `claude-launcher-plus.sh` – Changes in `launch_custom()`

### Step 1: Extract models during provider parsing

After the user picks a provider, the Python script that reads `providers.json` also extracts any `models` array and emits it alongside the provider config.

### Step 2: If `models` exists and is non-empty

Print a model selection menu:

```
Available models for OpenRouter:
  1)  Claude 3.5 Sonnet
  2)  GPT-4o
  3)  Gemini 2.5 Pro
```

User picks a model number. Merge the provider's base `env` with the chosen model's `env` (model overrides provider). Export and apply the merged env.

### Step 3: If `models` does not exist

Fall through to the existing behavior (provider-level env only).

---

## Implementation Details

The Python embedded in `launch_custom()` will handle:

1. Reading both `env` and optional `models` from each provider.
2. Emitting the model list + merged config for the selected model.
3. The Bash wrapper reads this, presents menus, and exports vars.

### Provider config emission format

The Python script emits provider info in a structured format (e.g., `name|base_env_json|models_json` or similar) so Bash can parse and present the model menu.

---

## Files Modified

| File | Changes |
|---|---|
| `providers.json` | Add `models` array to OpenRouter with 3 entries |
| `claude-launcher-plus.sh` | Update `launch_custom()` to support model-level selection |

---

## Edge Cases

| Case | Behavior |
|---|---|
| Provider with empty `models` array | Treated as no models (fallback to provider env) |
| Model entry missing `ANTHROPIC_MODEL` | Use provider-level `ANTHROPIC_MODEL` |
| Model `env` includes non-MODEL vars | Any env var can be overridden, not just `ANTHROPIC_MODEL` |
| Provider with no `models` key at all | Existing behavior preserved |

---

## User Flow

```
1. User selects "3) Custom provider"
2. Menu shows available providers (Deepseek, OpenRouter)
3. User selects OpenRouter
4. Menu shows available models (Claude 3.5 Sonnet, GPT-4o, Gemini 2.5 Pro)
5. User selects a model
6. Claude Code launches with the merged provider + model env vars