#!/usr/bin/env bash
# claude-launcher-plus.sh
#
# Enhanced launcher for Claude Code with LM Studio and custom provider support.
# Based on the original claude-launcher.sh created by @gmotzespina.
#
#   • Supports three modes:
#       1. Local (LM Studio)
#       2. Cloud (Anthropic OAuth)
#       3. Custom provider (e.g. DeepSeek, OpenRouter, etc.)
#
#   • Added: “fetch_local_models” – discovers loaded LM Studio models
#     and prompts the user to pick one before launching Claude.
#
#   • All configuration files are cleaned up at the start of each mode
#     to avoid stale settings.
#
#   • Added: DeepSeek and OpenRouter support for custom providers via ~/.claude/providers.json

set -euo pipefail

VERSION="1.1.0"

# ------------------------------------------------------------------
# CONFIGURATION SECTION
# ------------------------------------------------------------------

LM_STUDIO_HOST="${LM_STUDIO_HOST:-localhost}"
LM_STUDIO_PORT="${LM_STUDIO_PORT:-1234}"
LM_STUDIO_URL="http://${LM_STUDIO_HOST}:${LM_STUDIO_PORT}"
LM_STUDIO_API_KEY="${LM_STUDIO_API_KEY:-lm-studio}"

CLAUDE_JSON="$HOME/.claude.json"               # Claude onboarding flag
CLAUDE_SETTINGS="$HOME/.claude/settings.json"  # Claude settings file
CUSTOM_PROVIDERS_FILE="$HOME/.claude/providers.json"  # Custom provider config

# ------------------------------------------------------------------
# COLOR DEFINITIONS
# ------------------------------------------------------------------

GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
RED='\033[0;31m'
BOLD='\033[1m'
NC='\033[0m'   # No Color

if [[ -n "${NO_COLOR:-}" ]]; then
    GREEN='' YELLOW='' BLUE='' RED='' BOLD='' NC=''
fi

# ------------------------------------------------------------------
# HELPER FUNCTIONS
# ------------------------------------------------------------------

ensure_onboarding_done() {
    python3 -c "
import json, os
path = '$CLAUDE_JSON'
d = {}
if os.path.exists(path):
    try:
        with open(path) as f:
            d = json.load(f)
    except: pass
d['hasCompletedOnboarding'] = True
with open(path, 'w') as f:
    json.dump(d, f, indent=2)
"
}

ensure_settings_dir() {
    mkdir -p "$HOME/.claude"
}

check_lm_studio() {
    curl -s --connect-timeout 2 "$LM_STUDIO_URL/api/v1/models" > /dev/null 2>&1
}

get_lm_studio_models() {
    local response
    response=$(curl -s --connect-timeout 2 "$LM_STUDIO_URL/api/v1/models" 2>/dev/null) || return 1
    python3 -c "
import json, sys
data = json.loads(sys.stdin.read())
for m in data.get('models', []):
    if len(m.get('loaded_instances', [])) > 0 and m.get('type') == 'llm':
        print(m.get('key', 'unknown'))
" <<<"$response"
}

pick_lm_studio_model() {
    local models=()
    while IFS= read -r line; do
        [[ -n "$line" ]] && models+=("$line")
    done < <(get_lm_studio_models || true)

    if [[ ${#models[@]} -eq 0 ]]; then
        echo "no model loaded"
        return 1
    elif [[ ${#models[@]} -eq 1 ]]; then
        echo "${models[0]}"
    else
        echo -e "\n  ${BOLD}Available LM Studio models:${NC}" >&2
        for i in "${!models[@]}"; do
            echo -e "  ${BOLD}$((i+1)))${NC}  ${models[$i]}" >&2
        done
        echo "" >&2
        read -rp "  Choose model [1-${#models[@]}]: " choice </dev/tty
        if [[ "$choice" =~ ^[0-9]+$ ]] && (( choice >= 1 && choice <= ${#models[@]} )); then
            echo "${models[$((choice-1))]}"
        else
            echo -e "  ${RED}Invalid choice, using first model.${NC}" >&2
            echo "${models[0]}"
        fi
    fi
}

print_lm_studio_status() {
    local models=() studio_running=false
    if check_lm_studio; then
        studio_running=true
        while IFS= read -r line; do
            [[ -n "$line" ]] && models+=("$line")
        done < <(get_lm_studio_models || true)
    fi
    if $studio_running; then
        if [[ ${#models[@]} -gt 0 ]]; then
            echo -e "  LM Studio:  ${GREEN}● running${NC} at ${LM_STUDIO_URL} — ${#models[@]} model(s): ${BOLD}${models[*]}${NC}"
        else
            echo -e "  LM Studio:  ${GREEN}● running${NC} at ${LM_STUDIO_URL} — 0 models loaded"
        fi
    else
        echo -e "  LM Studio: ${RED}● offline${NC} at ${LM_STUDIO_URL}"
    fi
}

# ------------------------------------------------------------------
# STARTUP HELPERS
# ------------------------------------------------------------------

check_dependencies() {
    local missing=()
    for dep in python3 curl claude; do
        command -v "$dep" &>/dev/null || missing+=("$dep")
    done
    if [[ ${#missing[@]} -gt 0 ]]; then
        echo -e "${RED}Missing required dependencies: ${missing[*]}${NC}"
        return 1
    fi
    return 0
}

confirm_launch() {
    # Only prompt interactively; skip if stdin is not a TTY (e.g. piped / scripted)
    if [[ ! -t 0 ]]; then
        return 0
    fi
    echo ""
    echo -e "  ${BOLD}${BLUE}═══ Ready to launch: ${1} ═══${NC}"
    shift
    for line in "$@"; do
        echo -e "  $line"
    done
    echo ""
    local answer
    read -rp "  Proceed? [Y/n] " answer </dev/tty
    if [[ "$answer" =~ ^[Nn] ]]; then
        echo -e "  ${YELLOW}Aborted.${NC}"
        return 1
    fi
    return 0
}

reset_settings() {
    python3 -c "
import json, os
path = '$CLAUDE_SETTINGS'
d = {}
if os.path.exists(path):
    try:
        with open(path) as f:
            d = json.load(f)
    except: pass
d.clear()
with open(path, 'w') as f:
    json.dump(d, f, indent=2)
"
    unset ANTHROPIC_BASE_URL ANTHROPIC_API_KEY ANTHROPIC_MODEL CLAUDE_CODE_DISABLE_NONESSENTIAL_TRAFFIC ANTHROPIC_AUTH_TOKEN
    rm -f "$HOME/.claude/api-key-helper.sh"
}

# ------------------------------------------------------------------
# MODE: LOCAL (LM Studio)
# ------------------------------------------------------------------

launch_local() {
    echo -e "${BLUE}${BOLD}🖥  Local Mode (LM Studio)${NC}"
    echo ""

    reset_settings

    # Verify LM Studio is running
    if ! check_lm_studio; then
        echo -e "${RED}✗ LM Studio is not responding at ${LM_STUDIO_URL}${NC}"
        echo -e "  Make sure LM Studio is running and the server is started."
        read -rp "Wait and retry? (y/n) " choice
        if [[ "$choice" == [Yy] ]]; then
            echo -e "  Waiting for LM Studio..."
            for i in {1..30}; do
                if check_lm_studio; then
                    echo -e "  ${GREEN}✓ Connected!${NC}"
                    break
                fi
                sleep 2; printf "."
            done
            echo ""
            if ! check_lm_studio; then
                echo -e "${RED}  Timed out. Please start LM Studio and try again.${NC}"
                exit 1
            fi
        else
            exit 1
        fi
    fi

    echo -e "${GREEN}✓ LM Studio is running${NC}"
    echo ""

    ensure_onboarding_done
    ensure_settings_dir

    # Fetch and pick a model
    local chosen_model
    chosen_model=$(pick_lm_studio_model)
    if [[ -z "$chosen_model" ]]; then
        echo -e "${RED}No loaded models found – aborting.${NC}"
        exit 1
    fi
    export ANTHROPIC_MODEL="$chosen_model"
    echo -e "  Model: ${BOLD}${ANTHROPIC_MODEL}${NC}"

    # Create apiKeyHelper
    local key_helper="$HOME/.claude/api-key-helper.sh"
    cat > "$key_helper" <<EOF
#!/bin/bash
echo "$LM_STUDIO_API_KEY"
EOF
    chmod +x "$key_helper"

    # Environment for LM Studio
    export ANTHROPIC_BASE_URL="$LM_STUDIO_URL"
    export CLAUDE_CODE_DISABLE_NONESSENTIAL_TRAFFIC=1
    unset ANTHROPIC_API_KEY 2>/dev/null || true

    # Persist settings
    python3 -c "
import json, os
path = '$CLAUDE_SETTINGS'
d = {}
if os.path.exists(path):
    try:
        with open(path) as f:
            d = json.load(f)
    except: pass
d['apiKeyHelper'] = '$key_helper'
d.pop('ANTHROPIC_AUTH_TOKEN', None)
env = d.setdefault('env', {})
env['CLAUDE_CODE_ATTRIBUTION_HEADER'] = '0'
env.pop('ANTHROPIC_AUTH_TOKEN', None)
with open(path, 'w') as f:
    json.dump(d, f, indent=2)
"

    echo ""
    if ! confirm_launch "Local Mode (LM Studio)" \
        "  Model:  ${BOLD}${ANTHROPIC_MODEL}${NC}" \
        "  URL:    ${LM_STUDIO_URL}"; then
        return 0
    fi
    echo -e "  ${GREEN}Launching Claude Code → LM Studio${NC}"
    echo -e "  ─────────────────────────────────"
    exec claude "$@"
}

# ------------------------------------------------------------------
# MODE: CLOUD (Anthropic)
# ------------------------------------------------------------------

launch_cloud() {
    echo -e "${BLUE}${BOLD}☁️  Cloud Mode (Anthropic)${NC}"
    echo ""

    reset_settings
    if ! confirm_launch "Cloud Mode (Anthropic)" \
        "  Provider: Anthropic API" \
        "  Auth:     OAuth / Anthropic account"; then
        return 0
    fi
    echo -e "  ${GREEN}Launching Claude Code → Anthropic API${NC}"
    echo -e "  ─────────────────────────────────────"
    exec claude "$@"
}

# ------------------------------------------------------------------
# MODE: CUSTOM PROVIDER
# ------------------------------------------------------------------

launch_custom() {
    echo -e "${BLUE}${BOLD}🔧 Custom Provider Mode${NC}"
    echo ""

    reset_settings

    if [[ ! -f "$CUSTOM_PROVIDERS_FILE" ]]; then
        echo -e "${RED}No custom providers configured.${NC}"
        echo -e "  Expected config at: ${BOLD}${CUSTOM_PROVIDERS_FILE}${NC}"
        echo ""
        echo "  To get started:"
        echo "    cp providers.json ~/.claude/providers.json"
        echo "    # Then edit it with your API keys"
        return 1
    fi

    local providers
    providers=$(python3 -c "
import json, sys
try:
    with open('$CUSTOM_PROVIDERS_FILE') as f:
        data = json.load(f)
    for name, cfg in data.get('providers', {}).items():
        print(f'{name}|{json.dumps(cfg)}')
except Exception as e:
    sys.stderr.write(str(e))
    sys.exit(1)
")

    if [[ -z "$providers" ]]; then
        echo -e "${RED}No valid providers found in configuration.${NC}"
        return 1
    fi

    local provider_list=()
    while IFS='|' read -r name cfg; do
        provider_list+=("$name")
    done <<< "$providers"

    local choice=1 selected_name selected_cfg
    if [[ ${#provider_list[@]} -eq 1 ]]; then
        selected_name="${provider_list[0]}"
        echo -e "Provider: ${BOLD}${selected_name}${NC} (auto-selected)"
    else
        echo -e "Available providers:"
        for i in "${!provider_list[@]}"; do
            echo -e "  ${BOLD}$((i+1)))${NC}  ${provider_list[$i]}"
        done
        echo ""
        read -rp "Choose provider [1-${#provider_list[@]}]: " choice </dev/tty
    fi
    if [[ "$choice" =~ ^[0-9]+$ ]] && (( choice >= 1 && choice <= ${#provider_list[@]} )); then
        selected_name="${provider_list[$((choice-1))]}"
        while IFS='|' read -r name cfg; do
            [[ "$name" == "$selected_name" ]] && { selected_cfg="$cfg"; break; }
        done <<< "$providers"

        # ── Model selection (if provider has models) ──────────────────────
        local models_output
        models_output=$(python3 -c "
import json, sys
cfg = json.loads(sys.argv[1])
for i, m in enumerate(cfg.get('models', [])):
    print(f'{i+1}|{m[\"name\"]}')
" "$selected_cfg")

        if [[ -n "$models_output" ]]; then
            local model_entries=()
            while IFS='|' read -r idx model_name; do
                model_entries+=("$model_name")
            done <<< "$models_output"

            local model_choice=1 chosen_model_name=""
            if [[ ${#model_entries[@]} -eq 1 ]]; then
                chosen_model_name="${model_entries[0]}"
                echo -e "Model: ${BOLD}${chosen_model_name}${NC} (auto-selected)"
            else
                echo -e "Available models for ${BOLD}$selected_name${NC}:"
                for i in "${!model_entries[@]}"; do
                    echo -e "  ${BOLD}$((i+1)))${NC}  ${model_entries[$i]}"
                done
                echo ""
                read -rp "Choose model [1-${#model_entries[@]}]: " model_choice </dev/tty
            fi
            if [[ "$model_choice" =~ ^[0-9]+$ ]] && (( model_choice >= 1 && model_choice <= ${#model_entries[@]} )); then
                chosen_model_name="${model_entries[$((model_choice-1))]}"
                selected_cfg=$(python3 -c "
import json, sys
cfg = json.loads(sys.argv[1])
idx = int(sys.argv[2]) - 1
model_env = cfg['models'][idx].get('env', {})
base_env = cfg.get('env', {}).copy()
base_env.update(model_env)
print(json.dumps({'env': base_env}))
" "$selected_cfg" "$model_choice")
            else
                echo -e "${RED}Invalid choice${NC}"
                return 1
            fi
        fi
        # ───────────────────────────────────────────────────────────────

        # Apply provider config and export env vars
        local env_output
        env_output=$(python3 -c "
import json, os, sys
cfg = json.loads(sys.argv[1])
env_dict = cfg.get('env', {})
for k, v in env_dict.items():
    os.environ[k] = str(v)
path = '$CLAUDE_SETTINGS'
d = {}
if os.path.exists(path):
    try:
        with open(path) as f: d = json.load(f)
    except: pass
d.pop('apiKeyHelper', None)
d.pop('ANTHROPIC_AUTH_TOKEN', None)
d_env = d.setdefault('env', {})
for k, v in env_dict.items():
    d_env[k] = str(v)
d_env.pop('ANTHROPIC_AUTH_TOKEN', None)
with open(path, 'w') as f: json.dump(d, f, indent=2)
for k, v in env_dict.items():
    print(f'{k}={v}')
" "$selected_cfg")

        while IFS='=' read -r k v; do
            export "$k=$v"
        done <<< "$env_output"

        if [[ -n "${chosen_model_name:-}" ]]; then
            if ! confirm_launch "Custom Provider (${selected_name})" \
                "  Provider: ${BOLD}${selected_name}${NC}" \
                "  Model:    ${BOLD}${chosen_model_name}${NC}"; then
                return 0
            fi
        else
            if ! confirm_launch "Custom Provider (${selected_name})" \
                "  Provider: ${BOLD}${selected_name}${NC}"; then
                return 0
            fi
        fi
        echo -e "  ${GREEN}Launched with custom provider: $selected_name${NC}"
        echo -e "  ─────────────────────────────────────"
        exec claude "$@"
    else
        echo -e "${RED}Invalid choice${NC}"
        return 1
    fi
}

# ------------------------------------------------------------------
# STATUS (for the menu)
# ------------------------------------------------------------------

show_status() {
    echo -e "${BLUE}${BOLD}📊 Claude Code Launcher — Status${NC}"
    echo ""

    print_lm_studio_status

    if [[ -n "${ANTHROPIC_BASE_URL:-}" ]]; then
        echo -e "  Base URL:   ${YELLOW}${ANTHROPIC_BASE_URL}${NC}"
    else
        echo -e "  Base URL:   ${GREEN}Anthropic default (cloud)${NC}"
    fi

    if [[ -f "$CLAUDE_JSON" ]] && grep -q '"hasCompletedOnboarding": true' "$CLAUDE_JSON"; then
        echo -e "  Onboarding: ${GREEN}✓ bypassed${NC}"
    else
        echo -e "  Onboarding: ${YELLOW}not set${NC}"
    fi

    echo ""
    echo -e "  ${BOLD}Custom Providers:${NC}"
    if [[ -f "$CUSTOM_PROVIDERS_FILE" ]]; then
        python3 -c "
import json
with open('$CUSTOM_PROVIDERS_FILE') as f:
    data = json.load(f)
providers = data.get('providers', {})
if not providers:
    print('    (no providers defined)')
for name, cfg in providers.items():
    model_count = len(cfg.get('models', []))
    base_url = cfg.get('env', {}).get('ANTHROPIC_BASE_URL', 'not set')
    line = f'    {name}  →  {base_url}'
    if model_count > 0:
        line += f'  ({model_count} models)'
    print(line)
"
    else
        echo -e "    ${YELLOW}none configured${NC}  (create ${CUSTOM_PROVIDERS_FILE})"
    fi

    if [[ -f "$CLAUDE_SETTINGS" ]] && grep -q '"apiKeyHelper"' "$CLAUDE_SETTINGS"; then
        echo -e "  Auth:       ${YELLOW}apiKeyHelper (local mode)${NC}"
    elif [[ -n "${ANTHROPIC_AUTH_TOKEN:-}" ]]; then
        echo -e "  Auth:       ${YELLOW}ANTHROPIC_AUTH_TOKEN (custom provider)${NC}"
    else
        echo -e "  Auth:       ${GREEN}OAuth / Anthropic account${NC}"
    fi

    if [[ -f "$CLAUDE_SETTINGS" ]]; then
        echo -e "  Settings:   ${GREEN}✓ exists${NC}"
    else
        echo -e "  Settings:   ${YELLOW}not found${NC}"
    fi
}

# ------------------------------------------------------------------
# INTERACTIVE MENU
# ------------------------------------------------------------------

show_menu() {
    while true; do
        echo ""
        echo -e "${BOLD}┌─────────────────────────────────────┐${NC}"
        echo -e "${BOLD}│     Claude Code Launcher  🚀        │${NC}"
        echo -e "${BOLD}└─────────────────────────────────────┘${NC}"
        echo ""

        print_lm_studio_status

        echo ""
        echo -e "  ${BOLD}1)${NC}  🖥  Local mode (LM Studio)"
        echo -e "  ${BOLD}2)${NC}  ☁️  Cloud mode (Anthropic)"
        echo -e "  ${BOLD}3)${NC}  🔧 Custom provider"
        echo -e "  ${BOLD}4)${NC}  📊 Status (LM Studio)"
        echo -e "  ${BOLD}q)${NC}  Exit"
        echo ""
        read -rp "  Choose [1/2/3/4/q]: " choice

        case "$choice" in
            1) launch_local ;;
            2) launch_cloud ;;
            3) launch_custom ;;
            4) show_status ;;
            q|Q) exit 0 ;;
            *) echo -e "  ${RED}Invalid choice${NC}" ;;
        esac
    done
}

# ------------------------------------------------------------------
# MAIN ENTRY POINT
# ------------------------------------------------------------------

check_dependencies || exit 1

case "${1:-}" in
    local)   shift; launch_local "$@" ;;
    cloud)   shift; launch_cloud "$@" ;;
    custom)  shift; launch_custom "$@" ;;
    status)  show_status ;;
    list-providers)
        if [[ ! -f "$CUSTOM_PROVIDERS_FILE" ]]; then
            echo "No custom providers configured (missing ~/.claude/providers.json)"
            exit 1
        fi
        python3 -c "
import json
with open('$CUSTOM_PROVIDERS_FILE') as f:
    data = json.load(f)
for name in data.get('providers', {}):
    print(name)
" ;;
    list-models)
        target_provider="${2:-}"
        if [[ -z "$target_provider" ]]; then
            echo "Usage: $(basename "$0") list-models <provider>"
            exit 1
        fi
        if [[ ! -f "$CUSTOM_PROVIDERS_FILE" ]]; then
            echo "No custom providers configured (missing ~/.claude/providers.json)"
            exit 1
        fi
        python3 -c "
import json, sys
target = sys.argv[1]
with open('$CUSTOM_PROVIDERS_FILE') as f:
    data = json.load(f)
provider = data.get('providers', {}).get(target)
if not provider:
    print(f'Provider \"{target}\" not found')
    sys.exit(1)
models = provider.get('models', [])
if not models:
    print(f'{target}: no models defined (uses provider-level env only)')
else:
    for m in models:
        model_name = m.get('name', 'unknown')
        model_env = m.get('env', {})
        model_id = model_env.get('ANTHROPIC_MODEL', 'no ANTHROPIC_MODEL set')
        print(f'{model_name}  ->  {model_id}')
" "$target_provider" ;;
    --version|-V)
        echo "claude-launcher-plus v${VERSION}"
        ;;
    help|-h|--help)
        echo "Usage: $(basename "$0") [local|cloud|custom|status|list-providers|list-models|help]"
        echo ""
        echo "  local           Launch Claude Code with LM Studio"
        echo "  cloud           Launch Claude Code with Anthropic account"
        echo "  custom          Launch Claude Code with custom provider"
        echo "  status          Show configuration and LM Studio status"
        echo "  list-providers  List configured custom providers"
        echo "  list-models <p> List available models for a provider"
        echo "  --version, -V    Print version and exit"
        echo "  (none)          Interactive menu"
        echo ""
        echo "  Environment:"
        echo "    LM_STUDIO_HOST    Override LM Studio host (default: localhost)"
        echo "    LM_STUDIO_PORT    Override LM Studio port (default: 1234)"
        echo "    LM_STUDIO_API_KEY Override LM Studio API key"
        echo "    NO_COLOR          Disable colored output"
        ;;
    *)       show_menu ;;
esac
