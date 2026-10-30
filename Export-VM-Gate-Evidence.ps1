# Export only allowlisted diagnostics. NEVER include DPAPI state, keys, journal, or SQLite DB.
param([string]$GuestRoot = "$env:SystemDrive\CognitumDisposableVMGate\Run1",
      [string]$Output = "$PSScriptRoot\Cognitum_T3_VM_Evidence.zip")
$ErrorActionPreference='Stop'
$allow=@('phase-marker.json','reboot-evidence.json','snapshot-marker.json','witness-enroll.json','witness-advance.json','witness-check.json')
$staging=Join-Path ([IO.Path]::GetTempPath()) ('cognitum-allowlist-'+[guid]::NewGuid().ToString('N'))
New-Item -Path $staging -ItemType Directory -ErrorAction Stop | Out-Null
try {
    foreach ($name in $allow) {
        $src=Join-Path $GuestRoot $name
        if (Test-Path -LiteralPath $src -PathType Leaf) { Copy-Item -LiteralPath $src -Destination (Join-Path $staging $name) }
    }
    if (Test-Path $Output) { throw 'Refusing to overwrite an existing evidence archive' }
    Compress-Archive -Path (Join-Path $staging '*.json') -DestinationPath $Output -CompressionLevel Optimal
    Write-Host "Evidence export: $Output"
    Write-Host 'Review JSON for private scope data before sharing.'
} finally { Remove-Item -LiteralPath $staging -Recurse -Force -ErrorAction SilentlyContinue }
