# Revised Implementation Plan for `claude-launcher-plus.py`

## Overview
This revised plan incorporates feedback on security prioritization, backward compatibility, comprehensive testing, and configuration versioning.

## Revised Priority Order (high → low)
1. **Type safety & documentation** – eliminates hidden bugs
2. **Security fundamentals** – NEW PHASE (moved up from Phase 5)
3. **Logging infrastructure** – replaces ad-hoc prints
4. **Provider JSON validation with versioning** – prevents runtime errors
5. **Robust file handling & atomic writes** – guards against corruption
6. **Permission & security checks** – ensures secrets are protected
7. **Color abstraction** – improves cross-platform UX
8. **Non-interactive mode** – allows CI and headless usage
9. **CLI refactor (subparsers, groups)** – clarifies command structure
10. **Comprehensive test suite** – unit + integration tests
11. **Extended dependency checks** – early failure for missing tools
12. **Dry-run enhancements** – validates config before launching
13. **Documentation & README updates** – final polish
14. **Install/Uninstall script improvements** – safe installation

## Revised Phase Breakdown

### Phase 0 – Project Bootstrapping (Enhanced)
| Task | Description |
|------|-------------|
| Create `requirements.txt` / `pyproject.toml` | Pin dependencies with security updates
| Set up virtualenv | Ensure reproducible builds
| Add CI config (GitHub Actions) | Run lint, tests, security scans on push/PR
| Add `setup.cfg` for flake8/black | Enforce style early
| **NEW**: Add security scanning tools | Bandit, Safety for dependency vulnerabilities
| **NEW**: Code of conduct & contributing guidelines | Establish community standards

### Create Project Skeleton
| Module | Purpose |
|--------|---------|
| `claude_launcher/__init__.py` | Expose public API (`launch`, etc.) |
| `claude_launcher/cli.py` | Argument parsing, sub‑parsers, flag handling |
| `claude_launcher/config.py` | Load/save settings.json & providers.json with schema validation |
| `claude_launcher/providers.py` | Resolve provider env vars, sanitize inputs |
| `claude_launcher/launcher.py` | Orchestrate the actual launch (atomic writes, subprocess) |
| `claude_launcher/utils.py` | Helpers: atomic_write(), color helper, env sanitization |
| `claude_launcher/logger.py` | Structured logging configuration |

**Skeleton snippets**

```python
# claude_launcher/cli.py
import argparse
from .logger import configure_logging
from .launcher import launch

def main() -> None:
    parser = argparse.ArgumentParser(prog="claude-launcher-plus")
    subparsers = parser.add_subparsers(dest="mode", required=True)

    # local mode
    p_local = subparsers.add_parser("local", help="Run Claude locally")
    p_local.add_argument("--dry-run", action="store_true")

    # cloud mode
    p_cloud = subparsers.add_parser("cloud", help="Run Claude in the cloud")

    parser.add_argument("--verbose", action="store_true")
    ns = parser.parse_args()

    configure_logging(ns.verbose)
    launch(ns)

if __name__ == "__main__":
    main()
```

```python
# claude_launcher/config.py
import json, pathlib
from jsonschema import validate

SETTINGS_PATH = pathlib.Path.home() / ".claude" / "settings.json"
PROVIDERS_PATH = pathlib.Path(__file__).parent / "providers.schema.json"

def load_settings() -> dict:
    return json.loads(SETTINGS_PATH.read_text())
```

```python
# claude_launcher/utils.py
def atomic_write(path: str | pathlib.Path, content: str) -> pathlib.Path:
    """Write content atomically with secure temp file creation."""
    path = pathlib.Path(path)
    tmp_fd, tmp_path = tempfile.mkstemp(dir=path.parent, prefix=".tmp_")
    try:
        with os.fdopen(tmp_fd, "w", encoding="utf-8") as f:
            f.write(content)
        os.replace(tmp_path, path)  # atomic rename
        os.chmod(path, 0o600)  # Restrictive permissions for files
        return path
    except Exception:
        if pathlib.Path(tmp_path).exists():
            pathlib.Path(tmp_path).unlink()
        raise
```

```python
# claude_launcher/logger.py
import logging, sys

def configure_logging(verbose: bool) -> None:
    level = logging.DEBUG if verbose else logging.INFO
    fmt = "%(asctime)s %(levelname)s: %(message)s"
    logging.basicConfig(level=level, format=fmt, stream=sys.stdout)
```

### Phase 1 – Type Safety & Documentation (High-Impact)
| Task | Target Files | Notes |
|------|--------------|-------|
| Add module-level docstring | `claude-launcher-plus.py` | Summarise purpose, usage
| Add typing annotations to all public functions | This file | Use `-> None`, `-> bool`
| Add type hints to helper functions | This file |
| Add `__all__` for exported symbols | This file |
| Run mypy with strict settings | Project root |
| **NEW**: Add runtime type validation | Critical data structures

### Phase 2 – Security Fundamentals (NEW EARLY PHASE)
| Task | Implementation |
|------|----------------|
| Define security requirements | Authentication, authorization, data protection
| Implement credential rotation support | API key management strategy
| Add timeout for external commands | Prevent hanging on command execution
| Implement sandboxing | For untrusted provider configurations
| Add secret detection in logs | Prevent sensitive data leakage
| **NEW**: Environment variable sanitization | Reject suspicious characters (semicolons, etc.)
| **NEW**: Input validation | For all user-provided data
| **NEW**: Error handling strategy | Graceful degradation and clear messages

### Phase 3 – Logging Infrastructure (High-Impact)
| Task | Details |
|------|---------|
| Replace `print()` with logging module | Use `logging.getLogger(__name__)`
| Add `--verbose` flag to argparse | Sets logger level to DEBUG
| Format logs with timestamps and levels | `logging.basicConfig(format=…)`
| Ensure child processes inherit config | Use proper logger configuration
| Add unit tests for logger configuration |
| **NEW**: Structured logging | JSON format for easier parsing
| **NEW**: Log rotation | Prevent log files from growing indefinitely

### Phase 4 – Provider JSON Validation with Versioning (High-Impact)
| Task | Implementation |
|------|----------------|
| Define JSON Schema for `providers.json` | Version field, backward compatibility
| Use `jsonschema.validate()` in `load_providers` | Clear error messages for validation failures
| Add fallback for version-1 format | Keep backward compatibility
| Write tests covering valid/invalid configs |
| **NEW**: Schema evolution strategy | Clear migration path for future versions
| **NEW**: Configuration profiles | Support dev/prod environments

### Phase 5 – Robust File Handling & Atomic Writes (Medium-Impact)
| Task | Action |
|------|--------|
| Wrap file operations in try/except | Explicit error messages
| Ensure atomic writes to `api-key-helper.sh` | Use temp files and atomic rename
| Set proper permissions after creation | `os.chmod` for security
| Add write permission checks | Before attempting file operations
| **NEW**: File corruption detection | Checksum verification for critical files
| **NEW**: Concurrent operation handling | Locking mechanism for shared resources

### Phase 6 – Permission & Security Checks (Medium-Impact)
| Task | Details |
|------|---------|
| Sanitize provider `env` values | Escape dangerous characters
| Add `--allow-scripts` flag | Explicit permission for shell helpers
| Verify directory permissions | Not world-accessible
| Log warnings for suspicious env values |
| **NEW**: Credential rotation support | API key management
| **NEW**: Timeout implementation | For external command execution
| **NEW**: Sandbox validation | For untrusted configurations

### Phase 7 – Color Abstraction (Low-Impact)
| Task | Steps |
|------|-------|
| Replace hard-coded ANSI codes | Use `colorama` or `rich`
| Add helper function `c(col, msg)` | Consistent color handling
| Update all color usages |
| **NEW**: Cross-platform testing | Verify on Windows, macOS, Linux

### Phase 8 – Non-interactive Mode (Low-Impact)
| Task | Implementation |
|------|----------------|
| Add `--non-interactive` flag |
| Skip all `input()` prompts | Use defaults or exit with error
| Update help text |
| **NEW**: CI/CD integration | Test scenarios for automated environments

### Phase 9 – CLI Refactor (Medium-Impact)
| Task | Action |
|------|--------|
| Refactor argparse to use subparsers | For each mode (`local`, `cloud`, `custom`)
| Group shared options | `--dry-run`, `--verbose`
| Add descriptive help strings |
| **NEW**: Command aliases | For backward compatibility
| **NEW**: Tab completion support | Enhanced CLI experience

### Phase 10 – Comprehensive Test Suite (High-Impact)
| Task | Scope |
|------|-------|
| Write unit tests for core functions | `atomic_write`, settings management
| Write integration tests | Full launch workflow
| Add mutation testing | Critical functions only
| Use `pytest-mock` for external calls |
| Add coverage thresholds | 90%+ for critical paths
| **NEW**: Performance benchmarks | Launch time measurements
| **NEW**: Smoke tests | Basic functionality verification

### Phase 11 – Extended Dependency Checks (Low-Impact)
| Task | Implementation |
|------|----------------|
| Expand `_check_dep` to list all binaries | `claude`, `curl`, etc.
| Report missing dependencies | Clear installation instructions
| **NEW**: Version compatibility checks | Ensure tool versions are supported

### Phase 12 – Dry-Run Enhancements (Low-Impact)
| Task | Steps |
|------|-------|
| Simulate launch in dry-run mode | Print what would be executed
| Return non-zero on validation failure |
| **NEW**: Configuration validation reporting | Detailed feedback for users

### Phase 13 – Documentation & README Updates (Low-Impact)
| Task | Deliverables |
|------|--------------|
| Update README.md or add `docs/launcher.md` | Installation, configuration
| Add inline comments | Complex logic explanations
| **NEW**: Migration guide | For configuration changes
| **NEW**: Troubleshooting section | Common issues and solutions

### Phase 14 – Install/Uninstall Script Improvements (Low-Impact)
| Task | Details |
|------|---------|
| **install.sh** enhancements | Strict error handling, validation
| **uninstall.sh** improvements | Robust cleanup, verification
| **NEW**: Post-installation verification | Check that everything works
| **NEW**: Migration scripts | For configuration format changes

## Enhanced Success Criteria
1. **All tests pass** (`pytest -q` including integration tests)
2. **mypy reports no type errors** with strict settings
3. **Running dry-run validates configs cleanly**
4. **No sensitive data in logs** at any level
5. **Launch time under 500ms** for typical configurations
6. **Works cross-platform** without modification
7. **Code coverage > 90%** for critical paths
8. **Backward compatibility maintained**
9. **Security scanning passes** (Bandit, Safety)
10. **Installation verification successful**

## Revised Timeline
| Phase | Estimated Effort | Milestone |
|-------|------------------|-----------|
| 0 | 3 hrs | Repo bootstrapped with security tools |
| 1 | 4 hrs | Type hints + docs + runtime validation |
| 2 | 5 hrs | Security fundamentals implemented |
| 3 | 4 hrs | Logging system with structured output |
| 4 | 6 hrs | Provider schema + versioning + tests |
| 5 | 3 hrs | File handling fixes with corruption detection |
| 6 | 4 hrs | Enhanced security checks |
| 7 | 1.5 hrs | Color abstraction with cross-platform testing |
| 8 | 1.5 hrs | Non-interactive flag with CI integration |
| 9 | 4 hrs | CLI refactor with aliases |
| 10 | 8 hrs | Full test suite + integration tests |
| 11 | 1.5 hrs | Dependency checker with version validation |
| 12 | 1.5 hrs | Dry-run enhancements |
| 13 | 3 hrs | Documentation with migration guide |
| 14 | 4 hrs | Install/uninstall scripts + verification |

**Total**: ~50 hours (including buffer for debugging)

## Key Improvements Over Original Plan
1. **Security moved to Phase 2** (from Phase 5) for earlier attention
2. **Comprehensive testing strategy** including integration tests and performance benchmarks
3. **Configuration versioning** with clear migration paths
4. **Full backward compatibility** maintained throughout
5. **Enhanced error handling** and recovery mechanisms
6. **Cross-platform considerations** built into each phase
7. **Post-installation verification** for installation scripts
8. **Migration support** for configuration changes
9. **Performance requirements** added to success criteria
10. **Security scanning** integrated into CI/CD pipeline

## Risk Mitigation Strategy

### High Priority Risks
1. **Configuration Validation**
   - Solution: Schema-based validation with clear error messages
   - Mitigation: Comprehensive test coverage for all config scenarios

2. **Atomic Writes**
   - Solution: Temp file + atomic rename pattern
   - Mitigation: File corruption detection and recovery

3. **Environment Variable Handling**
   - Solution: Strict input validation and sanitization
   - Mitigation: Sandbox testing for untrusted inputs

### Medium Priority Risks
1. **Dependency Management**
   - Solution: Version pinning with compatibility checks
   - Mitigation: Regular dependency update testing

2. **Cross-Platform Compatibility**
   - Solution: Dedicated cross-platform testing phase
   - Mitigation: CI/CD tests on multiple platforms

3. **Permission Handling**
   - Solution: Explicit permission checks and warnings
   - Mitigation: Security-focused code reviews

## Implementation Approach
1. **Start with Phase 0** to establish foundation
2. **Work in small, testable increments** (1-2 phases at a time)
3. **Commit each phase separately** for easy rollback
4. **Run tests after each phase** to catch issues early
5. **Review security implications** at each milestone
6. **Gather feedback** after major phases (e.g., CLI refactor)

## Next Steps
1. Begin Phase 0 to set up development environment with security tools
2. Commit foundation work before moving to Phase 1
3. Run initial security scan after Phase 0 completion
4. Start Phase 2 (Security) immediately after Phase 1
5. Integrate testing throughout development cycle

This revised plan addresses all the feedback while maintaining the original goals of creating a production-ready, maintainable, and user-friendly launcher tool.

## Modularization Strategy

The current monolithic `claude-launcher-plus.py` is a good starting point, but for long‑term maintainability it should be split into focused modules. The suggested layout keeps the public API small while exposing a clean, testable core.

```
claude_launcher/
├── __init__.py          # expose public functions (e.g., launch)
├── cli.py               # argparse / sub‑parsers, flag handling
├── config.py            # load/save settings.json & providers.json with schema validation
├── providers.py         # resolve provider env vars, sanitize inputs
├── launcher.py          # orchestrate the actual launch (atomic writes, subprocess)
├── utils.py             # helpers: atomic_write, color helper, env sanitization
└── logger.py            # structured logging configuration
```

### Why this split?
1. **Single Responsibility** – each file has one clear purpose.
2. **Easier Testing** – unit tests can import only the module under test.
3. **Clear Public API** – consumers import from `claude_launcher` without needing to know internal file names.
4. **Future Extensibility** – adding a GUI or web wrapper would only touch `cli.py` and the public API.

### Suggested Skeleton (partial)
```python
# claude_launcher/cli.py
import argparse
from .logger import configure_logging
from .launcher import launch

def main() -> None:
    parser = argparse.ArgumentParser(prog="claude-launcher-plus")
    subparsers = parser.add_subparsers(dest="mode", required=True)

    # local mode
    p_local = subparsers.add_parser("local", help="Run Claude locally")
    p_local.add_argument("--dry-run", action="store_true")

    # cloud mode
    p_cloud = subparsers.add_parser("cloud", help="Run Claude in the cloud")

    parser.add_argument("--verbose", action="store_true")
    ns = parser.parse_args()

    configure_logging(ns.verbose)
    launch(ns)  # defined in launcher.py

if __name__ == "__main__":
    main()
```

```python
# claude_launcher/config.py
import json, pathlib
from jsonschema import validate

SETTINGS_PATH = pathlib.Path.home() / ".claude" / "settings.json"
PROVIDERS_PATH = pathlib.Path(__file__).parent / "providers.schema.json"

def load_settings() -> dict:
    return json.loads(SETTINGS_PATH.read_text())

# … (similar for providers, with validation)
```

```python
# claude_launcher/launcher.py
import subprocess, os
from .utils import atomic_write

def launch(args) -> int:
    # resolve provider env vars, write helper script atomically
    helper_path = atomic_write("/tmp/api-key-helper.sh", build_helper_script(args))
    # run the claude binary
    result = subprocess.run(["claude", "--config", str(helper_path)], capture_output=True)
    # handle exit codes, logging, etc.
    return result.returncode
```

```python
# claude_launcher/utils.py
def atomic_write(path: str | pathlib.Path, content: str) -> pathlib.Path:
    """Write content atomically with secure temp file creation."""
    path = pathlib.Path(path)
    tmp_fd, tmp_path = tempfile.mkstemp(dir=path.parent, prefix=".tmp_")
    try:
        with os.fdopen(tmp_fd, "w", encoding="utf-8") as f:
            f.write(content)
        os.replace(tmp_path, path)  # atomic rename
        os.chmod(path, 0o600)  # Restrictive permissions for files
        return path
    except Exception:
        if pathlib.Path(tmp_path).exists():
            pathlib.Path(tmp_path).unlink()
        raise
```

```python
# claude_launcher/logger.py
import logging, sys

def configure_logging(verbose: bool) -> None:
    level = logging.DEBUG if verbose else logging.INFO
    fmt = "%(asctime)s %(levelname)s: %(message)s"
    logging.basicConfig(level=level, format=fmt, stream=sys.stdout)
```

---

### Test Organization
- `tests/test_cli.py` – validate argparse parsing
- `tests/test_config.py` – schema validation & file I/O
- `tests/test_launcher.py` – mock subprocess, verify atomic writes
- `tests/test_utils.py` – color helper & sanitization logic

With this structure the plan remains intact, but each phase can be tackled in isolation and verified independently.
