# C06/P9 Windows x86-64 convenience wrapper. Runs no GitHub operations.
# Requires Python 3.11+, Git for Windows, and Rust 1.88+ for native tests.
[CmdletBinding()]
param(
    [Parameter(Mandatory=$true)][string]$LuSource,
    [Parameter(Mandatory=$true)][string]$Report,
    [ValidateSet('preflight','scoped','all')][string]$Mode = 'all',
    [switch]$AllowCargoDependencyDownloads
)
$ErrorActionPreference = 'Stop'
$here = Split-Path -Parent $MyInvocation.MyCommand.Path
$runner = Join-Path $here 'native_test_workspace.py'
if (-not (Test-Path -LiteralPath $runner -PathType Leaf)) {
    throw "The Cognitum P9 native workspace tool is missing"
}
# The pinned source is an EXISTING LOCAL Git checkout, never a GitHub URL.
if (-not (Test-Path -LiteralPath $LuSource -PathType Container)) {
    throw "LuSource must be an existing local Git checkout"
}
$pythonCommand = Get-Command 'py' -ErrorAction SilentlyContinue
if ($pythonCommand) {
    $program = $pythonCommand.Source
    $args = @('-3', $runner, '--lu-source', $LuSource, '--report', $Report, '--mode', $Mode)
} else {
    $pythonCommand = Get-Command 'python' -ErrorAction Stop
    $program = $pythonCommand.Source
    $args = @($runner, '--lu-source', $LuSource, '--report', $Report, '--mode', $Mode)
}
if ($AllowCargoDependencyDownloads) { $args += '--allow-cargo-network' }
& $program @args
exit $LASTEXITCODE
