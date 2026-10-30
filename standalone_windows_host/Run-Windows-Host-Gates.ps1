param(
    [string]$Python = 'py',
    [string]$EvidenceDirectory = '.\windows-host-evidence'
)
$ErrorActionPreference = 'Stop'
Set-StrictMode -Version Latest
if ($env:OS -ne 'Windows_NT') { throw 'NATIVE_WINDOWS_REQUIRED' }
$Root = (Resolve-Path (Join-Path $PSScriptRoot '..')).Path
$Evidence = [System.IO.Path]::GetFullPath((Join-Path $Root $EvidenceDirectory))
$Status = 'FAILED'
$Started = [DateTimeOffset]::UtcNow
$Failure = $null
$PythonArgs = @()
if ($Python -eq 'py') { $PythonArgs = @('-3') }

Push-Location $Root
try {
    [System.IO.Directory]::CreateDirectory($Evidence) | Out-Null
    $Scratch = Join-Path $Evidence 'dedicated-scratch'
    [System.IO.Directory]::CreateDirectory($Scratch) | Out-Null
    # Deliberately avoid creating test journals under the user's AppData/Temp.
    $env:COGNITUM_P2Z_SCRATCH_PARENT = $Scratch
    $drive = (Get-Item -LiteralPath $Scratch).PSDrive.Name
    if ($drive -notmatch '^[A-Za-z]$') { throw 'LOCAL_DRIVE_LETTER_REQUIRED' }
    $volume = Get-Volume -DriveLetter $drive -ErrorAction Stop
    if ($volume.FileSystem -ne 'NTFS') { throw "NTFS_REQUIRED: $($volume.FileSystem)" }
    & $Python @PythonArgs -m standalone_windows_host.preflight --scratch $Scratch --out (Join-Path $Evidence 'python-preflight.json')
    if ($LASTEXITCODE -ne 0) { throw 'PYTHON_X86_64_PREFLIGHT_FAILED' }
    $os = Get-CimInstance Win32_OperatingSystem
    $sys = Get-CimInstance Win32_ComputerSystem
    $native = [ordered]@{
        started_utc = $Started.ToString('o')
        os_caption = $os.Caption
        os_version = $os.Version
        os_architecture = $os.OSArchitecture
        system_type = $sys.SystemType
        volume_drive = $drive
        volume_file_system = $volume.FileSystem
        independent_authority = $false
        power_loss_tested = $false
        lu_integration_tested = $false
    }
    $native | ConvertTo-Json -Depth 5 | Set-Content -LiteralPath (Join-Path $Evidence 'native-preflight.json') -Encoding UTF8
    & $Python @PythonArgs -m pytest -q tests/test_c15_t3_windows_host_harness.py tests/test_c15_t3_windows_acl_gate.py 2>&1 |
        Tee-Object -FilePath (Join-Path $Evidence 'pytest-native.log')
    if ($LASTEXITCODE -ne 0) { throw 'WINDOWS_NATIVE_PYTEST_GATE_FAILED' }
    & $Python @PythonArgs -m standalone_windows_host.runner --suite --out (Join-Path $Evidence 'windows-process-restart.json') 2>&1 |
        Tee-Object -FilePath (Join-Path $Evidence 'runner-native.log')
    if ($LASTEXITCODE -ne 0) { throw 'WINDOWS_NATIVE_PROCESS_GATE_FAILED' }
    $result = Get-Content -Raw -LiteralPath (Join-Path $Evidence 'windows-process-restart.json') | ConvertFrom-Json
    if (-not $result.windows_native_executed -or $result.status -ne 'WINDOWS_PROCESS_LEVEL_GATES_PASSED_NOT_CERTIFIED' -or
        $result.acl_audit.acl_policy -ne 'CURRENT_USER_AND_SYSTEM_ONLY' -or
        -not $result.dedicated_scratch_parent_used) { throw 'WINDOWS_NATIVE_EVIDENCE_INCOMPLETE' }
    $Status = 'WINDOWS_PROCESS_LEVEL_GATES_PASSED_NOT_CERTIFIED'
}
catch {
    $Failure = $_.Exception.Message
    Write-Error -Message "Windows host gate failed: $Failure" -ErrorAction Continue
    throw
}
finally {
    if (Test-Path -LiteralPath $Evidence) {
        $summary = [ordered]@{
            status = $Status
            started_utc = $Started.ToString('o')
            finished_utc = [DateTimeOffset]::UtcNow.ToString('o')
            failure = $Failure
            windows_power_loss_tested = $false
            independent_antirollback_host = $false
            lu_integration_tested = $false
        }
        $summary | ConvertTo-Json -Depth 5 | Set-Content -LiteralPath (Join-Path $Evidence 'gate-summary.json') -Encoding UTF8
        # Hash public evidence files; do not hash or emit DPAPI secrets or journal keys.
        Get-ChildItem -LiteralPath $Evidence -File | Get-FileHash -Algorithm SHA256 |
            Select-Object @{Name='File';Expression={$_.Path | Split-Path -Leaf}},Hash |
            ConvertTo-Json -Depth 4 | Set-Content -LiteralPath (Join-Path $Evidence 'evidence-sha256.json') -Encoding UTF8
    }
    Remove-Item Env:COGNITUM_P2Z_SCRATCH_PARENT -ErrorAction SilentlyContinue
    Pop-Location
}
if ($Status -ne 'WINDOWS_PROCESS_LEVEL_GATES_PASSED_NOT_CERTIFIED') { exit 1 }
Write-Host "PASS: Windows x86-64 process gates. See $Evidence; power-loss, Lu and independent antirollback authority still NOT certified."
