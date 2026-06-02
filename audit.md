# Audit: Claude Code Launcher Plus — Production Readiness Assessment

## Scope
5 tracked files (`.gitignore`, `README.md`, `claude-launcher-plus.sh`, `plans/openrouter-models.md`, `providers.json`). Gitignored files excluded.

---

## 1. Code Quality

### 1.1 Shell Script Architecture —  FAIR

| Issue | Severity | Location |
|-------|----------|----------|
| **Duplicate cleanup logic** — the Python JSON reset block (clear settings.json, unset env vars) is copy-pasted verbatim into `launch_local()`, `launch_cloud()`, and `launch_custom()`. | Medium | Lines 121-133, 221-234, 250-264 |
| **Dead code** — `LOCAL_MODEL=""` is defined in the config section but never referenced. | Low | Line 29 |
| **Inconsistent `read` usage** — `pick_lm_studio_model` reads from `/dev/tty` but `launch_custom` and `show_menu` use plain `read` (inherits stdin). Could break under stdin redirection. | Medium | Lines 102, 301, 330 |
| **Missing `-r` on some `read` calls** — Backslashes in user input are interpreted as escapes. | Low | Multiple |
| **Global `set -euo pipefail`** — The `while IFS='|' read` loop reading from the Python process substitution will silently fail if Python crashes, because `pipefail` + `read` returning non-zero on EOF causes the whole script to exit. | High | Lines 291-293 |
| **7 inline Python scripts** — Embedded Python in bash is fragile. String escaping (`'$VAR'` inside Python) works only because paths expand predictably (`$HOME/.claude/settings.json`) — but will break if paths contain single quotes. | Medium | Throughout |
| **`2>/dev/null` everywhere** — All Python stderr is suppressed. Silent failures make debugging impossible. | High | 7 occurrences |
| **No color opt-out** — ANSI codes hardcoded; no `NO_COLOR` env var support. | Low | Lines 38-43 |
| **`d.clear()` + immediate write** — Settings are wiped before new ones are written. A crash between clear and write leaves empty settings.json. | Medium | Lines 130-132 |

### 1.2 Python Inline Scripts —  CONCERNING

The JSON ingestion pipeline relies on `json.loads('$bash_var')` (single-quoted bash interpolation). This is an **injection vector** — if any JSON value contains a single quote, the Python script breaks. For example, a provider name like `"O'Brien's Proxy"` would break `json.loads('$selected_cfg')`.

**Recommendation**: Pass JSON via `sys.argv` (as the model extraction already does) or via a pipe, not via quoted bash interpolation.

### 1.3 JSON Schema —  GOOD

`providers.json` has clean, well-structured schema. The optional `models` array per provider is cleanly designed. Merge logic (`base_env.copy()` + `base_env.update(model_env)`) correctly implements the overriding semantics from the plan.

---

## 2. Risks

### 2.1 Security —  CRITICAL

| Risk | Detail |
|------|--------|
| **`ANTHROPIC_AUTH_TOKEN` persisted to disk** | In `launch_custom()` (lines 348-365), ALL env vars including `ANTHROPIC_AUTH_TOKEN` are written to `~/.claude/settings.json` in plaintext. Anyone with filesystem access reads the API key. `launch_local()` explicitly strips it (`d.pop('ANTHROPIC_AUTH_TOKEN', None)`) but `launch_custom()` does not. |
| **`ANTHROPIC_AUTH_TOKEN` inconsistency** | The OpenRouter config has `OPENROUTER_API_KEY` as a separate var AND `ANTHROPIC_AUTH_TOKEN` as a plaintext copy. The plan intended `ANTHROPIC_AUTH_TOKEN` to reference the key, not duplicate it with a potentially different value. |
| **No API key validation** | Placeholder values like `<your_deepseek_api_key>` are silently used. Claude Code will either fail cryptically or (worse) send requests with invalid auth. |
| **JSON injection via single quotes** | As noted in 1.2 — user-controlled provider names or env values with `'` break the script. |

### 2.2 Operational —  MODERATE

| Risk | Detail |
|------|--------|
| **Race condition** | Multiple concurrent instances of the script will overwrite each other's `settings.json`. |
| **No dependency checks** | `python3`, `curl` assumed present. Script fails with unclear errors if missing. |
| **LM Studio health check mismatch** | `check_lm_studio()` pings `/v1/models` but `get_lm_studio_models()` queries `/api/v0/models`. A running server could respond to one but not the other. |
| **`mktemp` portability** | macOS `mktemp` requires a template argument (e.g., `mktemp XXXXXX`). Current bare `mktemp` call (line 56) works on macOS by chance (defaults to `/tmp/tmp.XXXXXXXX`) but is not POSIX-compliant. |

### 2.3 Edge Cases —  MODERATE

| Case | Status | Note |
|------|--------|------|
| Provider with empty `models` array |  Handled | `cfg.get('models', [])` returns `[]`, loop produces no output |
| Model entry missing `ANTHROPIC_MODEL` |  Handled | Provider-level `ANTHROPIC_MODEL` preserved by merge |
| Model `env` includes non-MODEL vars |  Handled | Any var can be overridden via `base_env.update(model_env)` |
| Provider with no `models` key |  Handled | Deepseek works unchanged |
| Only 1 provider configured |  Partial | Menu still shows `[1-1]` prompt which works but is unnecessary UX |
| Only 1 model for provider |  Partial | Auto-selection like LM Studio would be nice but isn't implemented for custom providers |
| Malformed JSON in providers.json |  Broken | Python error goes to stderr  swallowed by `2>/dev/null`  `$providers` empty  "No valid providers" message |

---

## 3. Portability

| Dimension | Assessment |
|-----------|-----------|
| **Shell** | Requires **bash** (uses `[[`, `=~`, arrays, `<<<`, process substitution, `pipefail`). Will NOT work with dash, ash, or POSIX sh. |
| **Python** | Requires **Python 3** (`python3` command). No fallback to `python`. |
| **macOS vs Linux** | `mktemp` usage is BSD-compatible by accident. `read -rp` is fine on both. `curl` behavior identical. |
| **LM Studio** | Hardcoded `http://localhost:1234`. No way to specify different host/port without editing the script. |
| **Claude Code** | Assumes `claude` binary is in PATH. No check for its existence before trying to launch. |

---

## 4. Enhancement Recommendations

### P0 — Must Fix Before Production
1. **Strip `ANTHROPIC_AUTH_TOKEN` from settings.json in `launch_custom()`** — mirror what `launch_local()` does at line 200. This is the critical security issue.
2. **Use `sys.argv` for JSON passing instead of bash interpolation** — eliminate the single-quote injection vector.
3. **Remove `2>/dev/null` or gate it behind a `--verbose` flag** — silent failures are a debugging nightmare.

### P1 — Should Fix
4. **Extract duplicate cleanup into a `reset_settings()` function** — reduces 3 copy-paste blocks to 1.
5. **Add dependency checks** at script startup — `command -v python3`, `command -v curl`, `command -v claude`.
6. **Add `--no-color` support** — check `NO_COLOR` env var or `--no-color` flag.
7. **Restore `pipefail` safety** — wrap `while read` loops in `set +o pipefail` / `set -o pipefail` or use `|| true`.

### P2 — Nice to Have
8. **Auto-skip menu when only 1 provider** — don't prompt when there's no choice.
9. **Provider-level `models` for Deepseek too** — Deepseek could benefit from model selection just like OpenRouter.
10. **`list-providers` / `list-models <provider>` CLI subcommands** — useful for scripting.
11. **Configurable LM Studio host:port** via env var or CLI flag.
12. **Support `ANTHROPIC_DEFAULT_*_MODEL` vars in model entries** — currently only `ANTHROPIC_MODEL` is overridden, but the plan mentions other Claude Code model vars as valid targets.

---

## 5. Production Readiness Verdict

> **NOT YET PRODUCTION-READY**

The P0 items (auth token leakage, injection vector, silent error suppression) must be resolved first. The core architecture (modes, provider config, model selection) is solid and well-designed. The script is functional as a personal dev tool but needs hardening for any multi-user or shared-machine deployment.
