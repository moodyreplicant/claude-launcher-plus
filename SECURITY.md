# Security Policy

## Supported Versions

Only the latest release receives security fixes. The table below tracks which
versions are currently eligible for patches.

| Version | Supported          |
|---------|--------------------|
| 3.1.x   | :white_check_mark: |
| 3.0.x   | :white_check_mark: |
| < 3.0   | :x:                |

## Reporting a Vulnerability

**Do not open a public issue.** Instead, email a detailed report to the
maintainer at the address listed on the published crate / repository owner
profile.

Include as much detail as you can:

- A clear description of the issue
- Steps to reproduce, ideally a minimal script or config snippet
- The affected component (installer, launcher, provider validation, etc.)
- Any suggested remediation (optional)

You will receive an acknowledgement within **48 hours**. The maintainer will
follow up with a timeline and coordinate disclosure with you.

## Scope

Security reports about the following are in scope:

- Unintended leakage of provider credentials or API keys
- Code-execution or privilege-escalation vectors in the installer (`install.sh` /
  wrapper scripts)
- Injection paths through provider configuration (`providers.json`), CLI
  arguments, or environment variables
- Path traversal or unsafe file writes (atomic-write helpers, lock files,
  checksum files)

## Out of Scope

- Issues in third-party tools this launcher invokes (Claude Code CLI, LM Studio,
  custom provider endpoints) — please report those to the respective project
- Theoretical attacks that require the attacker to already control the user's
  home directory or shell environment
- Denial-of-service via resource exhaustion (e.g. infinite subprocess spawning)
  — these will be tracked as normal bugs

## Disclosure Policy

Once a fix is merged and released, the advisory will be published in the
[release notes](https://github.com/moodyreplicant/claude-launcher-plus/releases).
Credit will be given to the reporter unless they request anonymity.
