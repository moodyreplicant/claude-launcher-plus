# Contributing to Claude Code Launcher Plus

Thank you for considering contributing! This document outlines how to set up a development environment, run tests, and submit changes.

## Quick Start

```bash
# Clone the repository
git clone https://github.com/moodyreplicant/claude-launcher-plus.git
cd claude-launcher-plus

# Developer install (pipenv + pre-commit)
bash install.sh --dev

# Verify everything works
pipenv run python3 claude-launcher-plus.py --version
pipenv run pytest tests/
pipenv run mypy claude_launcher/
```

## Development Workflow

1. **Branch** from `main` for your changes
2. **Install** the dev environment (`bash install.sh --dev`)
3. **Make changes** — the package lives in `claude_launcher/`
4. **Run linting** before committing:
   ```bash
   pipenv run pre-commit run --all-files
   ```
5. **Run tests** and ensure they pass:
   ```bash
   pipenv run pytest tests/ --cov=claude_launcher/
   ```
6. **Type check** with mypy:
   ```bash
   pipenv run mypy claude_launcher/
   ```
7. **Commit** with a descriptive message following [Conventional Commits](https://www.conventionalcommits.org/):
   - `feat:` — new feature
   - `fix:` — bug fix
   - `docs:` — documentation
   - `test:` — test additions
   - `refactor:` — code restructuring
   - `chore:` — tooling, dependencies

## Project Structure

```
claude-launcher-plus.py     # Entry point → claude_launcher.cli:main
claude_launcher/
  __init__.py               # VERSION
  cli.py                    # Argument parsing
  config.py                 # Settings management
  launcher.py               # Launch modes
  logger.py                 # Structured logging
  providers.py              # Provider config
  utils.py                  # Helpers
tests/                      # 120+ tests
```

## Coding Standards

- **Python**: 3.11+, type-annotated with `mypy --strict`
- **Style**: Black (88 char line length), isort (black profile), flake8
- **Tests**: pytest with unittest.mock, 90%+ coverage on critical modules
- **Commits**: Conventional Commits format
- **No external runtime dependencies** beyond `jsonschema` — prefer stdlib

## Pull Request Process

1. Ensure all CI checks pass (lint, type check, tests, security scan)
2. Update tests for any new functionality
3. Update the README if the CLI interface or configuration format changes
4. Add a release note to `release.md` for significant changes
5. The PR will be reviewed for correctness, test coverage, and backward compatibility

## Reporting Issues

- **Bug reports**: Include the output of `clp --dry-run --verbose` and your `claude --version`
- **Feature requests**: Describe the use case and how it fits the project's scope
- **Security issues**: Open an issue privately or contact the maintainers directly

## Code of Conduct

Please note that this project follows the [Contributor Covenant](CODE_OF_CONDUCT.md).
By participating, you agree to uphold its standards.
