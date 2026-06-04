# CLAUDE.md

Claude Code Launcher Plus — an enhanced launcher for [Claude Code](https://docs.anthropic.com/en/docs/claude-code) with support for local (LM Studio), cloud (Anthropic OAuth), and custom provider modes.

## Architecture

```
claude-launcher-plus.py       # Main launcher (~450 lines, Python 3.6+, stdlib-only)
├── launch_local()            # LM Studio mode — discover models, present picker, launch
├── launch_cloud()            # Anthropic OAuth mode — reset settings, launch
├── launch_custom()           # Custom provider mode — read providers.json, picker, launch
├── show_status()             # Display LM Studio status, config, auth state
├── interactive_menu()        # TUI loop (returns after claude exits via subprocess.run)
│
├── SettingsManager           # load/reset/save ~/.claude/settings.json (atomic writes)
├── ProviderManager           # load/validate/resolve providers.json (v1 + v2 schema)
└── LMStudioClient            # urllib.request → LM Studio REST API (replaces curl)

install.sh                    # Unix installer (bash 3.2+) — shell detection, PATH, alias
uninstall.sh                  # Unix uninstaller (bash 3.2+) — safe removal with confirmations
install.ps1                   # Windows installer (PowerShell)
claude-launcher-plus.bat      # Windows CMD wrapper (3 lines)

providers.json                # Provider config template (v2: $VAR env references)
providers.schema.json         # JSON Schema (draft-07) for validation
```

## Running During Development

```bash
# Direct execution
python3 claude-launcher-plus.py local
python3 claude-launcher-plus.py cloud
python3 claude-launcher-plus.py custom
python3 claude-launcher-plus.py status
python3 claude-launcher-plus.py list-providers
python3 claude-launcher-plus.py list-models Deepseek

# Interactive menu
python3 claude-launcher-plus.py

# Dry-run (validate all config without launching)
python3 claude-launcher-plus.py --dry-run custom
```

## Conventions

- **Stdlib only** — no pip dependencies, no virtualenv. `json`, `pathlib`, `tempfile`, `urllib`, `subprocess`, `argparse`, `signal`.
- **Python 3.6+** — f-strings are fine, `pathlib` preferred over `os.path`, type hints optional.
- **Atomic writes** — all writes to `settings.json` go through `tempfile.NamedTemporaryFile` + `os.replace`.
- **TTY guards** — all interactive prompts check `sys.stdin.isatty()` before reading input.
- **Error messages** — every error includes a remediation hint (e.g., "Export it before launching.").
- **Backward compatible** — providers.json v1 (plaintext keys) is supported alongside v2 (`$VAR` references).
- **Shell scripts** (`install.sh`, `uninstall.sh`) remain bash 3.2+ compatible (macOS default). Use `sed -n` (not `grep -P`), portable BRE patterns.

## Settings Management

The launcher manages these keys in `~/.claude/settings.json`:

| Key | Mode | Purpose |
|-----|------|---------|
| `apiKeyHelper` | local | Path to auth script |
| `env.ANTHROPIC_BASE_URL` | custom | API endpoint |
| `env.ANTHROPIC_MODEL` | custom | Model ID |
| `env.ANTHROPIC_AUTH_TOKEN` | custom | API key |
| `env.CLAUDE_CODE_DISABLE_NONESSENTIAL_TRAFFIC` | local, custom | Telemetry off |
| `env.CLAUDE_CODE_ATTRIBUTION_HEADER` | local | Attribution toggle |
| `env.CLAUDE_CODE_EFFORT_LEVEL` | custom | Effort/thinking |
| `env.ANTHROPIC_DEFAULT_{OPUS,SONNET,HAIKU}_MODEL` | custom | Default model aliases |
| `env.OPENROUTER_API_KEY` | custom | OpenRouter key |

All other keys in `settings.json` are preserved across mode switches. The launcher uses
selective key removal (never `d.clear()`). Personal settings should go in
`.claude/settings.local.json` (project-local, never touched by the launcher).

## Release Process

1. Update `VERSION` string in `claude-launcher-plus.py`
2. Bump version in `install.sh` metadata reference
3. Update `README.md` if needed
4. Commit: `release: bump version to X.Y.Z`
5. Create annotated tag: `git tag -a vX.Y.Z -m "Release notes summary"`
6. Push: `git push origin main --tags`
7. Create GitHub Release from the tag with full release notes

## Testing

No automated test suite. Verification is manual:

```bash
# Syntax checks
python3 -m py_compile claude-launcher-plus.py
python3 -m json.tool providers.json > /dev/null
shellcheck install.sh uninstall.sh

# Manual smoke tests per mode (see docs/plans/ for test matrix)
```

## Key Design Decisions

1. **Python over bash** — Python 3 is already a hard dependency. Consolidating 11 subprocess
   spawns into one Python process eliminates ~400ms overhead and IFS parsing fragility.
2. **subprocess.run, not exec** — the interactive menu returns after Claude Code exits.
3. **Confirm before write** — settings are only written after user confirms the launch.
4. **Shell installers stay shell** — shell detection, PATH manipulation, and aliases are
   inherently shell operations. Converting to Python would add a bootstrap problem.
5. **providers.json v2 uses $VAR syntax** — simple, human-readable, no complex object nesting.
   Values starting with `$` are resolved from `os.environ` at runtime.
