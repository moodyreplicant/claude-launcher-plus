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

# ------------------------------------------------------------------
# CONFIGURATION SECTION
# ------------------------------------------------------------------

LM_STUDIO_URL="http://localhost:1234"          # LM Studio server
LM_STUDIO_API_KEY="lm-studio"                  # API key used by the apiKeyHelper
LOCAL_MODEL=""                                 # Optional: pre‑select a model

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

# ------------------------------------------------------------------
# HELPER FUNCTIONS
# ------------------------------------------------------------------

ensure_onboarding_done() {
    if [[ ! -f "$CLAUDE_JSON" ]]; then
        echo '{"hasCompletedOnboarding": true}' > "$CLAUDE_JSON"
    elif ! grep -q '"hasCompletedOnboarding"' "$CLAUDE_JSON" 2>/dev/null; then
        local tmp=$(mktemp)
        python3 -c "
import json, sys
with open('$CLAUDE_JSON') as f:
    d = json.load(f)
d['hasCompletedOnboarding'] = True
with open('$tmp', 'w') as f:
    json.dump(d, f, indent=2)
" 2>/dev/null && mv "$tmp" "$CLAUDE_JSON"
    fi
}

ensure_settings_dir() {
    mkdir -p "$HOME/.claude"
}

check_lm_studio() {
    curl -s --connect-timeout 2 "$LM_STUDIO_URL/v1/models" > /dev/null 2>&1
}

get_lm_studio_models() {
    local response
    response=$(curl -s --connect-timeout 2 "$LM_STUDIO_URL/api/v0/models" 2>/dev/null) || return 1
    python3 -c "
import json, sys
data = json.loads(sys.stdin.read())
for m in data.get('data', []):
    if m.get('state') == 'loaded' and m.get('type') == 'llm':
        print(m.get('id', 'unknown'))
" 2>/dev/null <<<"$response"
}

pick_lm_studio_model() {
    local models=()
    while IFS= read -r line; do
        [[ -n "$line" ]] && models+=("$line")
    done < <(get_lm_studio_models)

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

# ------------------------------------------------------------------
# MODE: LOCAL (LM Studio)
# ------------------------------------------------------------------

launch_local() {
    echo -e "${BLUE}${BOLD}🖥  Local Mode (LM Studio)${NC}"
    echo ""

    # Clean any stale configuration
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
" 2>/dev/null
    unset ANTHROPIC_BASE_URL ANTHROPIC_API_KEY ANTHROPIC_MODEL CLAUDE_CODE_DISABLE_NONESSENTIAL_TRAFFIC ANTHROPIC_AUTH_TOKEN

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
" 2>/dev/null

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
" 2>/dev/null
    unset ANTHROPIC_BASE_URL ANTHROPIC_API_KEY ANTHROPIC_MODEL CLAUDE_CODE_DISABLE_NONESSENTIAL_TRAFFIC ANTHROPIC_AUTH_TOKEN
    rm -f "$HOME/.claude/api-key-helper.sh"

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
" 2>/dev/null
    unset ANTHROPIC_BASE_URL ANTHROPIC_API_KEY ANTHROPIC_MODEL CLAUDE_CODE_DISABLE_NONESSENTIAL_TRAFFIC ANTHROPIC_AUTH_TOKEN
    rm -f "$HOME/.claude/api-key-helper.sh"

    if [[ ! -f "$CUSTOM_PROVIDERS_FILE" ]]; then
        echo -e "${RED}No custom providers configured.${NC}"
        echo "Create a $CUSTOM_PROVIDERS_FILE with your provider configurations."
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
" 2>/dev/null)

    if [[ -z "$providers" ]]; then
        echo -e "${RED}No valid providers found in configuration.${NC}"
        return 1
    fi

    local provider_list=()
    while IFS='|' read -r name cfg; do
        provider_list+=("$name")
    done <<< "$providers"

    echo -e "Available providers:"
    for i in "${!provider_list[@]}"; do
        echo -e "  ${BOLD}$((i+1)))${NC}  ${provider_list[$i]}"
    done
    echo ""

    read -rp "Choose provider [1-${#provider_list[@]}]: " choice
    if [[ "$choice" =~ ^[0-9]+$ ]] && (( choice >= 1 && choice <= ${#provider_list[@]} )); then
        local selected_name="${provider_list[$((choice-1))]}"
        local selected_cfg
        while IFS='|' read -r name cfg; do
            [[ "$name" == "$selected_name" ]] && { selected_cfg="$cfg"; break; }
        done <<< "$providers"

        # Apply provider config
        python3 -c "
import json, os
cfg = json.loads('$selected_cfg')
for k,v in cfg.get('env', {}).items():
    os.environ[k] = str(v)
path = '$CLAUDE_SETTINGS'
d={}
if os.path.exists(path):
    try:
        with open(path) as f: d=json.load(f)
    except: pass
d.pop('apiKeyHelper', None)          # remove local auth helper
env = d.setdefault('env', {})
for k,v in cfg.get('env', {}).items():
    env[k] = str(v)
with open(path,'w') as f: json.dump(d,f,indent=2)
" 2>/dev/null

        # ── NEW: Export provider env vars before launch ─────────────────────
        while IFS='=' read -r k v; do
            export "$k=$v"
        done < <(python3 -c "
import json, sys
cfg = json.loads(sys.argv[1])
for k, v in cfg.get('env', {}).items():
    print(f'{k}={v}')
" "$selected_cfg")
        # ───────────────────────────────────────────────────────────────

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

    local models=()
    if check_lm_studio; then
        while IFS= read -r line; do
            [[ -n "$line" ]] && models+=("$line")
        done < <(get_lm_studio_models)
    fi

    if [[ ${#models[@]} -eq 0 ]]; then
        echo -e "  LM Studio:  ${GREEN}● running${NC} at ${LM_STUDIO_URL} — 0 models loaded"
    else
        echo -e "  LM Studio:  ${GREEN}● running${NC} at ${LM_STUDIO_URL} — ${#models[@]} model(s): ${BOLD}${models[*]}${NC}"
    fi

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
    echo ""
    echo -e "${BOLD}┌─────────────────────────────────────┐${NC}"
    echo -e "${BOLD}│     Claude Code Launcher  🚀        │${NC}"
    echo -e "${BOLD}└─────────────────────────────────────┘${NC}"
    echo ""

    local models=()
    if check_lm_studio; then
        while IFS= read -r line; do
            [[ -n "$line" ]] && models+=("$line")
        done < <(get_lm_studio_models)
    fi

    if [[ ${#models[@]} -gt 0 ]]; then
        echo -e "  LM Studio:  ${GREEN}● running${NC} at ${LM_STUDIO_URL} — ${#models[@]} model(s): ${BOLD}${models[*]}${NC}"
    else
        echo -e "  LM Studio: ${RED}● offline${NC}"
    fi

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
        *) echo -e "  ${RED}Invalid choice${NC}"; show_menu ;;
    esac
}

# ------------------------------------------------------------------
# MAIN ENTRY POINT
# ------------------------------------------------------------------

case "${1:-}" in
    local)   shift; launch_local "$@" ;;
    cloud)   shift; launch_cloud "$@" ;;
    custom)  shift; launch_custom "$@" ;;
    status)  show_status ;;
    help|-h|--help)
        echo "Usage: $(basename "$0") [local|cloud|custom|status|help]"
        echo ""
        echo "  local    Launch Claude Code with LM Studio"
        echo "  cloud    Launch Claude Code with Anthropic account"
        echo "  custom   Launch Claude Code with custom provider"
        echo "  status   Show configuration and LM Studio status"
        echo "  (none)   Interactive menu"
        ;;
    *)       show_menu ;;
esac