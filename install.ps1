# install.ps1 — Windows installer for claude-launcher-plus
# Usage: powershell -ExecutionPolicy Bypass -File install.ps1
#
# Installs to %LOCALAPPDATA%\Programs\claude-launcher-plus\
# Adds to user PATH and creates a 'clp' alias.

param(
    [string]$Prefix = "$env:LOCALAPPDATA\Programs\claude-launcher-plus"
)

$ErrorActionPreference = "Stop"

# ── Root guard ──────────────────────────────────────────────────
if ([System.Security.Principal.WindowsIdentity]::GetCurrent().IsSystem) {
    Write-Host "Error: Do not run as SYSTEM — everything installs to your user directory." -ForegroundColor Red
    exit 1
}

# ── Pre-flight checks ───────────────────────────────────────────
$ScriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path
$SourceScript = Join-Path $ScriptDir "claude-launcher-plus.py"
$SourceBat = Join-Path $ScriptDir "claude-launcher-plus.bat"
$ProvidersTemplate = Join-Path $ScriptDir "providers.json"

if (-not (Test-Path $SourceScript)) {
    Write-Host "Error: claude-launcher-plus.py not found in current directory." -ForegroundColor Red
    Write-Host "Run this from the cloned repository."
    exit 1
}

# Check Python
$python = Get-Command python3 -ErrorAction SilentlyContinue
if (-not $python) { $python = Get-Command python -ErrorAction SilentlyContinue }
if (-not $python) {
    Write-Host "Error: Python 3.6+ is required but not found." -ForegroundColor Red
    Write-Host "Install from https://python.org and try again."
    exit 1
}

# Check Claude Code
$claude = Get-Command claude -ErrorAction SilentlyContinue
if (-not $claude) {
    Write-Host "Warning: 'claude' not found in PATH. Install Claude Code separately." -ForegroundColor Yellow
}

# ── Version extraction ──────────────────────────────────────────
$SourceVersion = "unknown"
$versionLine = Select-String -Path $SourceScript -Pattern '^VERSION\s*=\s*"([^"]*)"'
if ($versionLine) {
    $SourceVersion = $versionLine.Matches.Groups[1].Value
}
Write-Host "claude-launcher-plus v$SourceVersion"

# ── Install ─────────────────────────────────────────────────────
$TargetDir = $Prefix
$TargetPy = Join-Path $TargetDir "claude-launcher-plus.py"
$TargetBat = Join-Path $TargetDir "claude-launcher-plus.bat"

# Check existing installation
if (Test-Path $TargetPy) {
    $installedVersion = "unknown"
    $installedLine = Select-String -Path $TargetPy -Pattern '^VERSION\s*=\s*"([^"]*)"'
    if ($installedLine) {
        $installedVersion = $installedLine.Matches.Groups[1].Value
    }
    if ($installedVersion -eq $SourceVersion) {
        Write-Host "Already up to date (v$SourceVersion)."
    } else {
        Write-Host "Upgrading v$installedVersion -> v$SourceVersion"
        New-Item -ItemType Directory -Force -Path $TargetDir | Out-Null
        Copy-Item $SourceScript $TargetPy -Force
        Copy-Item $SourceBat $TargetBat -Force
        Write-Host "Installed to $TargetDir"
    }
} else {
    Write-Host "Installing v$SourceVersion"
    New-Item -ItemType Directory -Force -Path $TargetDir | Out-Null
    Copy-Item $SourceScript $TargetPy
    Copy-Item $SourceBat $TargetBat
    Write-Host "Installed to $TargetDir"
}

# ── Providers template ──────────────────────────────────────────
$ProvidersDest = "$env:USERPROFILE\.claude\providers.json"
if (-not (Test-Path $ProvidersDest)) {
    if (Test-Path $ProvidersTemplate) {
        New-Item -ItemType Directory -Force -Path "$env:USERPROFILE\.claude" | Out-Null
        Copy-Item $ProvidersTemplate $ProvidersDest
        Write-Host "Template providers.json created at $ProvidersDest"
        Write-Host "Edit it to add your API keys before using custom provider mode."
    }
}

# ── PATH setup ──────────────────────────────────────────────────
$userPath = [Environment]::GetEnvironmentVariable("PATH", "User")
if ($userPath -notlike "*$TargetDir*") {
    $answer = Read-Host "Add $TargetDir to your user PATH? [Y/n]"
    if ($answer -notmatch '^[Nn]') {
        [Environment]::SetEnvironmentVariable(
            "PATH", "$userPath;$TargetDir", "User"
        )
        $env:PATH = "$env:PATH;$TargetDir"
        Write-Host "Added to PATH. Restart your terminal for it to take effect."
    }
} else {
    Write-Host "$TargetDir is already in your PATH."
}

# ── Alias ───────────────────────────────────────────────────────
Write-Host ""
Write-Host "To use the 'clp' shortcut, run 'claude-launcher-plus' from CMD or PowerShell."
Write-Host "Done!"
