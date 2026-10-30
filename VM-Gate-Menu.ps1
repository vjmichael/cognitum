# Cognitum C15 T3 DISPOSABLE VM-only validation; NO automated reboots or power cuts.
$ErrorActionPreference = 'Stop'
Set-Location $PSScriptRoot
try {
    if (-not [Environment]::Is64BitOperatingSystem) { throw '64-bit Windows required.' }
    $machine = Get-CimInstance Win32_ComputerSystem
    $machineText = "$( $machine.Manufacturer ) $( $machine.Model )"
    if ($machineText -notmatch 'Virtual|VMware|QEMU|KVM|Xen|Parallels|Bochs|Hyper-V|bhyve') {
        throw "No supported VM identifier found ($machineText). This kit refuses to run on an apparent physical PC."
    }
    Write-Host 'DISPOSABLE VM ONLY. This kit never turns off or reboots a computer.' -ForegroundColor Yellow
    $confirm = Read-Host 'Type DISPOSABLE-VM-ONLY to permit this test'
    if ($confirm -cne 'DISPOSABLE-VM-ONLY') { throw 'VM-only operator consent missing' }
    $env:COGNITUM_DISPOSABLE_VM='I_CONFIRM_DISPOSABLE_VM'
    $venvPython=Join-Path $PSScriptRoot '.vm-gate-venv\Scripts\python.exe'
    if (-not (Test-Path $venvPython)) {
        $python = if ($env:COGNITUM_PYTHON_EXE) { $env:COGNITUM_PYTHON_EXE } else {
            $found=Get-Command python.exe -ErrorAction SilentlyContinue
            if ($found) { $found.Source } else { '' }
        }
        if (-not $python -or -not (Test-Path $python)) { throw 'Complete CPython x64 is required. Set COGNITUM_PYTHON_EXE to its executable.' }
        & $python -c 'import sys;assert sys.maxsize>2**32;assert sys.version_info>=(3,10)'
        if ($LASTEXITCODE -ne 0) {throw 'Python must be 64-bit 3.10+'}
        & $python -m venv (Join-Path $PSScriptRoot '.vm-gate-venv')
        if ($LASTEXITCODE -ne 0) {throw 'Python venv creation failed'}
        & $venvPython -m pip install -r (Join-Path $PSScriptRoot 'standalone_windows_host\requirements.txt')
        if ($LASTEXITCODE -ne 0) {throw 'Pinned dependency installation failed'}
    }
    $root = Join-Path $env:SystemDrive 'CognitumDisposableVMGate\Run1'
    Write-Host "Isolated guest state path: $root" -ForegroundColor Cyan
    Write-Host '1 Prepare reboot | 2 Verify reboot | 3 Snapshot genesis | 4 Snapshot commit | 5 Snapshot check | 6 Prepare hypervisor powercut | 7 Verify powercut'
    $choice=Read-Host 'Choose operation (1-7)'
    $mode=$null;$scenario=$null
    switch ($choice) {
        '1' { $mode='prepare'; $scenario='reboot' }
        '2' { $mode='verify' }
        '3' { $mode='snapshot-init' }
        '4' { $mode='snapshot-commit' }
        '5' { $mode='snapshot-check' }
        '6' { $mode='prepare'; $scenario='hypervisor_powercut' }
        '7' { $mode='verify' }
        default { throw 'Unknown operation' }
    }
    $arguments=@('-m','standalone_vm_recovery.guest',$mode,'--root',$root)
    if ($scenario) { $arguments+=@('--scenario',$scenario) }
    & $venvPython @arguments
    if ($LASTEXITCODE -ne 0) { throw "VM gate returned $LASTEXITCODE" }
    Write-Host 'Operation finished. This did NOT perform a reboot, shutdown, or power cut.' -ForegroundColor Green
    Write-Host 'To test reboot: manually restart only the disposable GUEST VM, then choose Verify.'
    Write-Host 'For hypervisor powercut: use your hypervisor UI on the disposable VM only; record host logs.'
    Write-Host 'For snapshot rollback: host witness database MUST remain outside the guest and outside its snapshots.'
} catch {
    Write-Error $_
    exit 2
}
