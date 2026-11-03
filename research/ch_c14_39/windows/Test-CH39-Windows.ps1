<#
CH39 Windows read-only public witness/integrity test. No admin, installs, network,
Cognitum production writes, Lu access, or Linux UID simulation.
PowerShell 5.1+; requires Python 3.9+ and 'cryptography' for Ed25519 audit.
Optional -MathProbe exercises a small (7-node) original proof prefix only.
#>
[CmdletBinding()]
param(
    [string]$Package = '',
    [string]$ResultsDirectory = '',
    [switch]$MathProbe,
    [string]$MpfrDll = ''
)
$ErrorActionPreference = 'Stop'
$ExpectedZip = '9e713b102982ea09fecbcfbd27bccf55d56808188bfc3e5be1ba76922000ae6b'
$ArchiveName = 'Cognitum_CH_C14_39_Independent_MPFR_Checker_Original_CH23_2026-11-02.zip'
if ([string]::IsNullOrWhiteSpace($Package)) { $Package = Join-Path $PSScriptRoot $ArchiveName }
if ([string]::IsNullOrWhiteSpace($ResultsDirectory)) {
    $ResultsDirectory = Join-Path $PSScriptRoot ('CH39_Windows_Results_' + (Get-Date -Format 'yyyyMMdd_HHmmss'))
}
New-Item -ItemType Directory -Path $ResultsDirectory -Force | Out-Null
$ReportFile = Join-Path $ResultsDirectory 'CH39_windows_summary.json'
$WorkingRoot = Join-Path ([System.IO.Path]::GetTempPath()) ('CH39Win_' + [guid]::NewGuid().ToString('N'))
$report = [ordered]@{
    test = 'Cognitum CH39 Windows offline public-witness test'
    time_local = (Get-Date).ToString('o')
    powershell = $PSVersionTable.PSVersion.ToString()
    os_version = [Environment]::OSVersion.VersionString
    process_64bit = [Environment]::Is64BitProcess
    package_sha256 = 'NOT_RUN'
    manifest = 'NOT_RUN'
    public_signatures = 'NOT_RUN'
    math_probe = 'NOT_REQUESTED'
    overall = 'NOT_RUN'
    scope = 'Read-only archive integrity + offline Ed25519; optional 7-node MPFR smoke; no Linux UID/security acceptance'
}

function Save-Report { $report | ConvertTo-Json -Depth 8 | Set-Content -LiteralPath $ReportFile -Encoding UTF8 }
function Find-Python {
    foreach ($name in @('py.exe', 'python.exe')) {
        if (-not (Get-Command $name -ErrorAction SilentlyContinue)) { continue }
        try {
            if ($name -eq 'py.exe') { $values = @(& py.exe -3 -c 'import sys;print(sys.executable)' 2>$null) }
            else { $values = @(& python.exe -c 'import sys;print(sys.executable)' 2>$null) }
            if ($LASTEXITCODE -ne 0 -or $values.Count -eq 0) { continue }
            $exe = [string]$values[-1]
            if (Test-Path -LiteralPath $exe -PathType Leaf) { return $exe }
        } catch { continue }
    }
    return $null
}
function Run-Python([string]$Executable,[string[]]$Arguments,[string]$LogPath) {
    $old = $ErrorActionPreference
    try {
        $ErrorActionPreference = 'Continue'
        & $Executable @Arguments 2>&1 | Out-File -LiteralPath $LogPath -Encoding UTF8
        return [int]$LASTEXITCODE
    } catch {
        ('PowerShell invocation error: ' + $_.Exception.Message) | Out-File -LiteralPath $LogPath -Append
        return 1
    } finally { $ErrorActionPreference = $old }
}

$exitCode = 1
try {
    Write-Host 'CH39 Windows public verification (read-only)' -ForegroundColor Cyan
    Write-Host 'This does not test Linux UID separation or prove global optimality.'
    if (-not (Test-Path -LiteralPath $Package -PathType Leaf)) {
        throw ('Package missing: ' + $Package)
    }
    $hash = (Get-FileHash -LiteralPath $Package -Algorithm SHA256).Hash.ToLowerInvariant()
    if ($hash -ne $ExpectedZip) {
        $report.package_sha256 = 'FAIL'
        throw ('Reproduction ZIP digest mismatch. Expected ' + $ExpectedZip + ' got ' + $hash)
    }
    $report.package_sha256 = 'PASS'
    Write-Host 'PASS: original CH39 package SHA-256 matches external pin.' -ForegroundColor Green

    $py = Find-Python
    if (-not $py) {
        $report.manifest = 'BLOCKED'
        $report.public_signatures = 'BLOCKED'
        $report.overall = 'BLOCKED_PYTHON_MISSING'
        $exitCode = 2
        Write-Host 'BLOCKED: Python 3 is not installed or not discoverable.' -ForegroundColor Yellow
        Write-Host 'Install Python 3 for Windows and rerun; no dependency is installed by this kit.'
    } else {
        $report.python_executable = $py
        $ver = @(& $py -c 'import sys;print(sys.version.split()[0])' 2>$null)
        if ($LASTEXITCODE -ne 0) { throw 'Python version probe failed' }
        $report.python_version = [string]$ver[-1]
        $dep = @(& $py -c 'import cryptography; print(cryptography.__version__)' 2>$null)
        if ($LASTEXITCODE -ne 0) {
            $report.manifest = 'BLOCKED'
            $report.public_signatures = 'BLOCKED'
            $report.overall = 'BLOCKED_CRYPTOGRAPHY_MISSING'
            $exitCode = 2
            Write-Host 'BLOCKED: Python cryptography package is unavailable.' -ForegroundColor Yellow
            Write-Host 'To install manually: py -3 -m pip install --user cryptography'
        } else {
            $report.cryptography_version = [string]$dep[-1]
            [void][Reflection.Assembly]::LoadWithPartialName('System.IO.Compression.FileSystem')
            New-Item -ItemType Directory -Path $WorkingRoot -Force | Out-Null
            [System.IO.Compression.ZipFile]::ExtractToDirectory([IO.Path]::GetFullPath($Package),[IO.Path]::GetFullPath($WorkingRoot))
            $env:PYTHONDONTWRITEBYTECODE = '1'
            $env:OPENBLAS_NUM_THREADS = '1'
            $env:OMP_NUM_THREADS = '1'
            $auditJson = Join-Path $ResultsDirectory 'CH39_public_audit.json'
            $auditLog = Join-Path $ResultsDirectory 'CH39_public_audit.log'
            $argsPy = @((Join-Path $PSScriptRoot 'ch39_windows_audit.py'), '--package', $Package,
                        '--root', $WorkingRoot, '--output', $auditJson)
            $rc = Run-Python $py $argsPy $auditLog
            if ($rc -ne 0) {
                $report.manifest = 'FAIL_OR_UNKNOWN'
                $report.public_signatures = 'FAIL_OR_UNKNOWN'
                throw ('CH39 archive or public-audit verification failed. See '+$auditLog)
            }
            $audit = Get-Content -LiteralPath $auditJson -Raw | ConvertFrom-Json
            if ($audit.status -ne 'PASS' -or $audit.package.manifest_sha256_verified_files -ne 1099 -or
                $audit.public_witness.signed_cases -ne 15 -or
                $audit.public_witness.attestor_signatures_verified -ne 15 -or
                $audit.public_witness.final_signer_signatures_verified -ne 15) {
                throw 'Unexpected audit result or incomplete signatures'
            }
            $report.manifest = 'PASS_1099_FILES'
            $report.public_signatures = 'PASS_15_ATTESTOR_15_SIGNER'
            Write-Host 'PASS: all 1,099 archived files have the frozen SHA-256 digests.' -ForegroundColor Green
            Write-Host 'PASS: 15 original case pins, 15 attestor + 15 signer signatures, pinned tip.' -ForegroundColor Green
            $report.overall = 'PASS_PUBLIC_WINDOWS_AUDIT'
            $exitCode = 0

            if ($MathProbe) {
                Write-Host 'Running optional MPFR 7-node projected proof probe...'
                $probeJson = Join-Path $ResultsDirectory 'CH39_mpfr_probe.json'
                $probeLog = Join-Path $ResultsDirectory 'CH39_mpfr_probe.log'
                $mathArgs = @((Join-Path $PSScriptRoot 'ch39_mpfr_probe.py'), '--root', $WorkingRoot, '--output', $probeJson)
                if (-not [string]::IsNullOrWhiteSpace($MpfrDll)) { $mathArgs += @('--mpfr-dll', $MpfrDll) }
                $mathRc = Run-Python $py $mathArgs $probeLog
                if (Test-Path -LiteralPath $probeJson) {
                    $probe = Get-Content -LiteralPath $probeJson -Raw | ConvertFrom-Json
                    $report.math_probe = [string]$probe.status
                } else { $report.math_probe = 'FAIL_NO_RESULT' }
                if ($mathRc -eq 0) { Write-Host 'PASS: 224-bit MPFR verified 7 original prefix nodes.' -ForegroundColor Green }
                elseif ($mathRc -eq 2) {
                    $report.overall = 'PASS_PUBLIC_MATH_BLOCKED'
                    $exitCode = 2
                    Write-Host 'BLOCKED optional MPFR probe; public signed audit still PASSED.' -ForegroundColor Yellow
                } else {
                    $report.overall = 'PASS_PUBLIC_MATH_FAILED'
                    $exitCode = 1
                    Write-Host 'FAIL optional MPFR probe; public signed audit still PASSED.' -ForegroundColor Red
                }
            }
        }
    }
} catch {
    $report.error = $_.Exception.Message
    if ($report.overall -eq 'NOT_RUN' -or $report.overall -eq 'PASS_PUBLIC_WINDOWS_AUDIT') { $report.overall = 'FAIL' }
    Write-Host ('FAIL: '+$report.error) -ForegroundColor Red
    $exitCode = 1
} finally {
    try { Save-Report } catch { Write-Host ('Cannot write summary: '+$_.Exception.Message) }
    try {
        if (Test-Path -LiteralPath $WorkingRoot) { Remove-Item -LiteralPath $WorkingRoot -Recurse -Force }
    } catch { Write-Host 'Temporary extraction could not be removed; see results location.' -ForegroundColor Yellow }
    Write-Host ''
    Write-Host ('Summary: '+$ReportFile)
    Write-Host 'Only share the JSON/log files; do not include machine keys or unrelated documents.'
}
exit $exitCode
