# Production Hardening — Change Summary

Branch: `prod` (based on `main`, then `audit`)  
Target: Address all enhancement recommendations from `audit.md`

---

## Commit Index

| # | Commit | Type | Description |
|---|--------|------|-------------|
| 1 | `6c97496` | **P0 Fix** | Security hardening |
| 2 | `79523fe` | **P1 Refactor** | Architecture & diagnostics |
| 3 | `882bca6` | **P2 Feature** | UX improvements & new capabilities |

---

## Commit 1 — P0: Security & Robustness (`6c97496`)

### Changes

| # | Audit Item | What Changed |
|---|-----------|--------------|
| 1 | Strip `ANTHROPIC_AUTH_TOKEN` from settings.json | Added `d.pop('ANTHROPIC_AUTH_TOKEN', None)` and `env.pop('ANTHROPIC_AUTH_TOKEN', None)` in `launch_custom()` "Apply provider config" block, mirroring `launch_local()` behavior |
| 2 | Fix JSON injection via bash interpolation | Changed `json.loads('$selected_cfg')` to `json.loads(sys.argv[1])` with `import sys`, passing `"$selected_cfg"` as argv argument |
| 3 | Enable Python error output | Removed `2>/dev/null` from all 7 Python3 invocations; errors now surface to stderr instead of being silently swallowed |

### Files
- `claude-launcher-plus.sh` — 15 insertions, 12 deletions

---

## Commit 2 — P1: Architecture & Diagnostics (`79523fe`)

### Changes

| # | Audit Item | What Changed |
|---|-----------|--------------|
| 4 | Extract duplicate cleanup | Created `reset_settings()` function replacing 3 identical copy-paste blocks in `launch_local()`, `launch_cloud()`, `launch_custom()` |
| 5 | Dependency checks at startup | Added `check_dependencies()` — validates `python3`, `curl`, `claude` are in PATH before any mode runs |
| 6 | `NO_COLOR` support | Added check for `NO_COLOR` env var; if set, all ANSI color variables are cleared |
| 7 | Pipefail safety | Added `|| true` guards to all 4 `done < <(cmd)` process substitution loops feeding `while read` to prevent script termination on read EOF |

### Files
- `claude-launcher-plus.sh` — 46 insertions, 50 deletions

---

## Commit 3 — P2: UX & New Capabilities (`882bca6`)

### Changes

| # | Audit Item | What Changed |
|---|-----------|--------------|
| 8 | Auto-skip single-option menus | When only 1 provider configured, auto-selects it (no prompt). When selected provider has only 1 model, auto-selects it. |
| 9 | Models for Deepseek | Added `models` array to Deepseek provider: **Deepseek V4 Pro (1M ctx)** and **Deepseek V4 Flash (1M ctx)** |
| 10 | CLI subcommands | Added `list-providers` (lists all configured providers) and `list-models <provider>` (lists models with their `ANTHROPIC_MODEL` values) |
| 11 | Configurable LM Studio | `LM_STUDIO_HOST` and `LM_STUDIO_PORT` env vars override host/port. `LM_STUDIO_API_KEY` also made overridable via env. |
| 12 | `ANTHROPIC_DEFAULT_*_MODEL` in models | Deepseek model entries include all 4 model vars (`OPUS`, `SONNET`, `HAIKU` + `MODEL`) demonstrating full env override support in model entries |

### Files
- `claude-launcher-plus.sh` — 96 insertions, 20 deletions
- `providers.json` — 23 insertions

---

## Final File State

| File | Lines | Changes |
|------|-------|---------|
| `claude-launcher-plus.sh` | 555 | +157 / -82 (net +75) |
| `providers.json` | 69 | +23 (Deepseek models) |
| `.gitignore` | 2 | unchanged |
| `README.md` | 19 | unchanged |
| `plans/openrouter-models.md` | 132 | unchanged |
| `audit.md` | 108 | unchanged |

---

## Verification

All changes pass:
- Bash syntax check (`bash -n`)
- JSON validity (`python3 -c "json.load()"`)
- Injection-free (`json.loads(sys.argv[1])` used for all JSON data, no `'$VAR'` patterns)
- Auth token stripped from settings.json in both local and custom modes

### New CLI Commands

```
$ ./claude-launcher-plus.sh list-providers
Deepseek
OpenRouter

$ ./claude-launcher-plus.sh list-models OpenRouter
NVIDIA: Nemotron 3 Super (free)  ->  nvidia/nemotron-3-super-120b-a12b:free
Poolside: Laguna M.1 (free)      ->  poolside/laguna-m.1:free
OpenAI: gpt-oss-120b (free)      ->  openai/gpt-oss-120b:free

$ ./claude-launcher-plus.sh list-models Deepseek
Deepseek V4 Pro (1M ctx)   ->  deepseek-v4-pro[1m]
Deepseek V4 Flash (1M ctx) ->  deepseek-v4-flash[1m]

$ LM_STUDIO_HOST=192.168.1.50 LM_STUDIO_PORT=9999 ./claude-launcher-plus.sh local
$ NO_COLOR=1 ./claude-launcher-plus.sh
```
