# Run the pytest suite.
#
# The suite cannot run in PowerShell at all: pytest_homeassistant_custom_component
# imports fcntl, which is POSIX-only, so `pytest` here dies at collection with
# ModuleNotFoundError before a single test runs. It runs under WSL instead,
# against this same working tree through /mnt/<drive>.
#
# The venv lives INSIDE the WSL filesystem (~/.venvs/price_watch) rather than in
# the repo. A venv on /mnt/e is slow to create and slow to import from, and one
# in the working tree is something deploy.ps1 and git both have to know to skip.
# The first run creates it and installs requirements_test.txt (a couple of
# minutes - homeassistant is a big wheel); later runs reuse it.
#
# Usage:
#   .\test.ps1                         whole suite, quiet
#   .\test.ps1 tests/test_fx.py        one file
#   .\test.ps1 -k region -v            pytest args pass straight through
#   .\test.ps1 --cov=custom_components.price_watch    coverage, as CI runs it
#   .\test.ps1 -Reinstall              rebuild the venv from requirements_test.txt
#
# Note CI lints only custom_components/ (`ruff check custom_components/price_watch`),
# so tests/ is not covered by it - run `ruff check tests` by hand if you want.
param(
    [switch]$Reinstall,
    [Parameter(ValueFromRemainingArguments = $true)]$PytestArgs
)

$ErrorActionPreference = 'Stop'

if (-not (Get-Command wsl -ErrorAction SilentlyContinue)) {
    Write-Error "WSL is not available, and the HA test harness cannot run on Windows. Install WSL, or run the suite in CI."
    exit 1
}

# wslpath converts E:\price_watch to /mnt/e/price_watch. Never hand-build that
# path: this repo does not have to live on E: forever.
$repo = (& wsl -e wslpath -u "$PSScriptRoot" 2>&1 | Out-String).Trim()
if ([string]::IsNullOrWhiteSpace($repo)) {
    Write-Error "Could not map $PSScriptRoot into WSL."
    exit 1
}

$venv = '$HOME/.venvs/price_watch'
$pytestArgsText = if ($PytestArgs) { ($PytestArgs -join ' ') } else { '-q' }

$bootstrap = if ($Reinstall) { "rm -rf $venv; " } else { '' }
$bootstrap += @"
# The stamp, not the interpreter, is the readiness test: an install killed
# part-way (closed window, timeout) leaves a venv with a working python and
# no pytest in it, and checking for bin/python would call that done and then
# fail confusingly on every later run.
if [ ! -f $venv/.requirements-installed ]; then
  echo 'Setting up the test venv (a couple of minutes - homeassistant is a big wheel)...'
  [ -x $venv/bin/python ] || python3 -m venv $venv || exit 1
  $venv/bin/pip install -q -U pip wheel || exit 1
  $venv/bin/pip install -q -r '$repo/requirements_test.txt' || exit 1
  touch $venv/.requirements-installed
fi
"@

# WSL's git defaults to autocrlf=false while the Windows checkout is CRLF, which
# makes `git status` in WSL report every CRLF file as wholly modified - and a
# commit from there would rewrite them. Keep the two in agreement.
$gitConfig = "git -C '$repo' config core.autocrlf true;"

# Newlines, not spaces: $bootstrap ends in `fi`, and `fi git ...` on one line
# is a bash syntax error.
$cmd = @"
$bootstrap
$gitConfig
cd '$repo' && $venv/bin/python -m pytest $pytestArgsText
"@

& wsl -e bash -lc $cmd
exit $LASTEXITCODE
