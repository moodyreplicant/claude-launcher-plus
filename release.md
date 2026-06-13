# Release v2.0.0 — Python Rewrite

**Tag:** `v2.0.0`
**Date:** 2026-06-04
**Branch:** `feat/python-rewrite` → `main`

## Summary

The bash launcher (643 lines, 11 Python subprocesses, fragile `IFS='|'` parsing)
has been replaced by a single Python script (512 lines, stdlib-only, zero new
dependencies). Python 3 was already a hard dependency — this consolidates
everything into one clean process.

## Changes

### Rewrite
- **`claude-launcher-plus.py`** — single-file Python launcher replacing the bash
  script. Uses `argparse`, `urllib` (replaces curl), `json`, `pathlib`, `tempfile`.
  No pip install, no virtualenv.
- **Menu now loops** — `subprocess.run` instead of `exec`, so the interactive
  menu returns after Claude Code exits.
- **Settings written after confirmation** — no more stale provider config if you
  abort.

### Security
- **providers.json v2** — API keys use `$VAR` references (`"$DEEPSEEK_API_KEY"`),
  resolved from the environment at runtime. Config file contains no secrets.
  v1 (plaintext keys) still supported transparently.
- **apiKeyHelper** — created with `os.open(0o700)`, shell-quoted via `shlex.quote()`.
  No TOCTOU window, no shell injection vector.
- **Atomic writes** — all JSON writes go through `tempfile` + `os.replace`.
  Crash-safe, no partial files.

### Bug fixes
- Corrupted `settings.json` is backed up to `.bak` instead of silently wiped
- TTY guards on all interactive prompts (no blocking in non-interactive mode)
- Exit codes reported when Claude Code exits non-zero
- Signal handlers restored before launching Claude (Ctrl+C reaches the child)
- Polling timeout is a hard 60-second deadline

### Windows support
- **`claude-launcher-plus.bat`** — CMD wrapper (3 lines)
- **`install.ps1`** — PowerShell installer with PATH setup
- Python's `pathlib.Path.home()` handles Windows paths natively

### Infrastructure
- **`CLAUDE.md`** — project documentation for AI assistants
- **`providers.schema.json`** — JSON Schema draft-07 for v1/v2 validation
- **`.github/workflows/ci.yml`** — Python syntax, JSON validity, shell syntax on push/PR
- **`archive/claude-launcher-plus.sh`** — old bash launcher, kept for reference

## Migration from v1.x

```bash
git pull
./install.sh   # detects old version, migrates automatically
```

Your `providers.json` and `settings.json` are preserved. The `clp` alias
continues working. To use v2 env-var references, update your API keys:

```bash
# ~/.zshrc or ~/.bashrc
export DEEPSEEK_API_KEY="sk-your-key"
export OPENROUTER_API_KEY="sk-or-your-key"
```

Then update `~/.claude/providers.json` to replace plaintext keys with `$VAR` refs.

## Verification

```bash
python3 -m py_compile claude-launcher-plus.py   # syntax
python3 -m json.tool providers.json > /dev/null  # config
bash -n install.sh && bash -n uninstall.sh        # shell scripts
python3 claude-launcher-plus.py --dry-run custom  # validate
```

---

# Release v2.0.2 — Cold-start crash fixes

**Tag:** `v2.0.2`
**Date:** 2026-06-04
**Branch:** `fix/cold-start-menu-recovery-and-status-crash` (squash-merged to `main`)

## Fixed

- **Interactive menu no longer exits on local mode abort.** Declining "Wait and
  retry?" or having zero models loaded in LM Studio now returns to the menu
  instead of killing the process. (`launch_local()` used `sys.exit(1)` in three
  places where `launch_cloud()` and `launch_custom()` correctly used `return`.)

- **Read-only commands no longer crash on missing env vars.** `clp status`,
  `clp list-providers`, and `clp list-models` no longer call
  `_resolve_env_value()` at load time. `$VAR` references in `providers.json`
  are now resolved only at launch time, when `launch_custom()` has confirmed
  which provider the user wants. Missing env vars still produce a clear error
  message — but only when you actually try to launch, not when browsing.

- **Custom provider abort returns to menu.** Picking a provider whose env var
  is missing now prints the error and returns to the interactive menu rather
  than exiting. `_resolve_env_value()` raises `ProviderConfigError` instead of
  calling `sys.exit(1)`; `launch_custom()` catches it and returns gracefully.


# Release v3.0.0 — Modular Package Refactor

**Tag:** `v3.0.0`
**Date:** 2026-06-13
**Branch:** `feat/refactor` (→ `main`)

## Summary

Complete architectural rewrite from a 530-line monolithic `claude-launcher-plus.py`
into a structured 7-module Python package (`claude_launcher/`) with 120+ tests.

## What Changed

### Architecture
- **Modular package** — `claude_launcher/` with 7 focused modules (cli, config,
  launcher, logger, providers, utils, __init__)
- **Entry point preserved** — `claude-launcher-plus.py` is now a 9-line shim
  that delegates to `claude_launcher.cli:main()`
- **Phase 0 foundation** — `Pipfile` + `Pipfile.lock`, `setup.cfg` for all tools,
  `.pre-commit-config.yaml` with 7 hooks, `pytest.ini`, `.gitignore`

### New Features
- **JSON Schema validation** — `providers.json` validated at load time
  with clear error messages via `jsonschema.validate()`
- **Structured logging** — JSON + human-readable formatters, file output with
  rotation, `--verbose` flag
- **Secret redaction** — `SecretRedactionFilter` masks API keys and tokens in logs
- **Atomic writes with checksums** — SHA-256 companion files detect corruption,
  `0o600` permissions, `FileLock` context manager
- **Input sanitization** — provider name, env var name, and URL validators
- **Env var sanitization** — detection of shell metacharacters in env values
- **`--non-interactive` flag** — force non-TTY mode for scripts and CI
- **`--allow-scripts` flag** — gates apiKeyHelper.sh creation
- **`check-deps` command** — structured dependency reporting with install URLs
- **Enhanced `--dry-run`** — execution plan per mode, validation pass/fail exit code
- **`--user` / `--dev` installer modes** — lightweight user install vs full dev env
- **`CODE_OF_CONDUCT.md` + `CONTRIBUTING.md`** — project governance

### Quality
- **123 tests** across 9 test files (up from 0)
- **mypy --strict: 0 errors** on 7 modules (down from 13)
- **Coverage**: 74% total, 90–100% on critical modules
- **All linting tools**: black, isort, flake8, bandit, safety — all green

### Backward Compatibility
- Entry point `claude-launcher-plus.py` unchanged
- All CLI subcommands (`local`, `cloud`, `custom`, `status`, etc.) unchanged
- `providers.json` v1 and v2 formats both supported
- `settings.json` format unchanged
- Old bash launcher auto-detected and migrated by installer
