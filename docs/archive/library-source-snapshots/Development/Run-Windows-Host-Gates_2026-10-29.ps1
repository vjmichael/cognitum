param([string]$Python = 'py', [string]$EvidenceDirectory = '.\windows-host-evidence')
$ErrorActionPreference = 'Stop'
if (-not $IsWindows -and $env:OS -ne 'Windows_NT') { throw 'Native Windows required' }
$Root = (Resolve-Path (Join-Path $PSScriptRoot '..')).Path
Push-Location $Root
try {
  if (-not (Test-Path $EvidenceDirectory)) { New-Item -Type Directory $EvidenceDirectory | Out-Null }
  $PythonArgs = @()
  if ($Python -eq 'py') { $PythonArgs = @('-3') }
  & $Python @PythonArgs -c "import sys,platform; assert sys.maxsize>2**32 and platform.machine().lower() in ('amd64','x86_64'), 'x86-64 Python required'"
  if ($LASTEXITCODE -ne 0) { throw '64-bit Python check failed' }
  $drive = (Get-Item $EvidenceDirectory).PSDrive.Name
  $volume = Get-Volume -DriveLetter $drive -ErrorAction Stop
  if ($volume.FileSystem -ne 'NTFS') { throw "NTFS required, found $($volume.FileSystem)" }
  & $Python @PythonArgs -m pytest -q tests/test_c15_t3_windows_host_harness.py
  if ($LASTEXITCODE -ne 0) { throw 'Windows focused suite failed' }
  & $Python @PythonArgs -m standalone_windows_host.runner --suite --out (Join-Path $EvidenceDirectory 'p2z-windows-host-evidence.json')
  if ($LASTEXITCODE -ne 0) { throw 'Windows subprocess suite failed' }
  Write-Host 'Process-level host validation passed. Power loss, real Lu, and antirollback authority NOT certified.'
}
finally { Pop-Location }