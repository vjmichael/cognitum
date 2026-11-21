# R3 actual native SCM forced host death / cold-process restart refusal.
# Signed uncertain NEVER constitutes worker stop, task success or Core grant.
# This is disposable Windows CI without independent installed publisher.
[CmdletBinding()]
param(
 [Parameter(Mandatory=$true)][string]$Executable,
 [Parameter(Mandatory=$true)][string]$FixtureRoot,
 [Parameter(Mandatory=$true)][string]$EvidencePath
)
Set-StrictMode -Version Latest
$ErrorActionPreference='Stop'
if($env:OS -ne 'Windows_NT'){throw 'Genuine Windows SCM forced-restart test required'}
$svc='CognitumSsmNativeFixtureV1'
$root=[IO.Path]::GetFullPath($FixtureRoot)
$exe=[IO.Path]::GetFullPath($Executable)
$pre=Join-Path $root 'prelaunch.json'
$admit=Join-Path $root 'r3-signed-prelaunch.json'
$uncertain=Join-Path $root 'r3-signed-restart.json'
$stop=Join-Path $root 'stop.json'
$signedStop=Join-Path $root 'r2-signed-stop.json'
if(!(Test-Path -LiteralPath $exe -PathType Leaf) -or
   !(Test-Path -LiteralPath $root -PathType Container) -or
   (Test-Path -LiteralPath $pre) -or (Test-Path -LiteralPath $admit) -or
   (Test-Path -LiteralPath $uncertain) -or (Test-Path -LiteralPath $signedStop)){
 throw 'R3 original restart fixture is absent or not fresh'
}
if(Get-CimInstance Win32_Service -Filter "Name='$svc'"){
 throw 'Cannot adopt/delete foreign original SCM service'
}
$created=$false
try {
  & sc.exe create $svc 'binPath=' ('"'+$exe+'"') 'start=' 'demand' 'obj=' 'LocalSystem'
  if($LASTEXITCODE -ne 0){throw 'Native original SCM create failed'}
  $created=$true
  & sc.exe start $svc
  if($LASTEXITCODE -ne 0){throw 'First genuine original SCM start failed'}
  $born=$null
  $deadline=[DateTime]::UtcNow.AddSeconds(9)
  while([DateTime]::UtcNow -lt $deadline){
    $born=Get-CimInstance Win32_Service -Filter "Name='$svc'"
    if($born -and $born.State -eq 'Running' -and
       [uint32]$born.ProcessId -gt 0 -and
       (Test-Path -LiteralPath $pre -PathType Leaf) -and
       (Test-Path -LiteralPath $admit -PathType Leaf)){break}
    Start-Sleep -Milliseconds 100
  }
  if(!$born -or $born.State -ne 'Running' -or
     [uint32]$born.ProcessId -eq 0 -or
     !(Test-Path -LiteralPath $pre -PathType Leaf) -or
     !(Test-Path -LiteralPath $admit -PathType Leaf)){
    throw 'Actual SCM never durably signed original admission before worker'
  }
  $originalPid=[uint32]$born.ProcessId
  $generation=Get-CimInstance Win32_Process -Filter ("ProcessId="+$originalPid)
  if(!$generation -or $generation.CreationDate -eq $null -or
     [uint32]$generation.SessionId -ne 0){
    throw 'Original live SCM generation unavailable'
  }
  if(Test-Path -LiteralPath $stop){throw 'Original terminal stop occurred before crash; cannot call uncertain'}
  $preSha=(Get-FileHash -LiteralPath $pre -Algorithm SHA256).Hash.ToLowerInvariant()
  $admitSha=(Get-FileHash -LiteralPath $admit -Algorithm SHA256).Hash.ToLowerInvariant()
  # Hard-kill the original SCM service process, NOT via SERVICE_CONTROL_STOP.
  # Its kill-on-close Job reaps any still-active child; this test deliberately
  # has no original live Job handle after host death to claim kernel-empty.
  Stop-Process -Id $originalPid -Force -ErrorAction Stop
  $deadline=[DateTime]::UtcNow.AddSeconds(10)
  while([DateTime]::UtcNow -lt $deadline){
    $state=Get-CimInstance Win32_Service -Filter "Name='$svc'"
    if($state -and $state.State -eq 'Stopped'){break}
    Start-Sleep -Milliseconds 150
  }
  if(!$state -or $state.State -ne 'Stopped'){
    throw 'Native Windows SCM did not observe forced original service loss'
  }
  if(Test-Path -LiteralPath $signedStop){throw 'Forged terminal signer after forced crash'}
  & sc.exe start $svc | Out-Host
  $deadline=[DateTime]::UtcNow.AddSeconds(10)
  while([DateTime]::UtcNow -lt $deadline){
    $state=Get-CimInstance Win32_Service -Filter "Name='$svc'"
    if((Test-Path -LiteralPath $uncertain -PathType Leaf) -and
       $state -and $state.State -eq 'Stopped'){break}
    Start-Sleep -Milliseconds 125
  }
  if(!(Test-Path -LiteralPath $uncertain -PathType Leaf) -or
     !$state -or $state.State -ne 'Stopped'){
    throw 'Restart did not produce externally CNG-signed uncertain refusal'
  }
  if((Get-FileHash -LiteralPath $pre -Algorithm SHA256).Hash.ToLowerInvariant() -cne $preSha -or
     (Get-FileHash -LiteralPath $admit -Algorithm SHA256).Hash.ToLowerInvariant() -cne $admitSha){
    throw 'Original persistent prelaunch/signature changed across SCM restart'
  }
  if(Test-Path -LiteralPath $signedStop){
    throw 'Service unexpectedly issued success/terminal proof for uncertain original'
  }
  $verification=& python scripts/cog_r5_r3_verify_recovery.py --root "$root" --expected-kind uncertain_restart
  if($LASTEXITCODE -ne 0){throw 'Independent signed uncertain original operation verification failed'}
  $verified=$verification | ConvertFrom-Json
  if($verified.signed_original_restart -ne $true -or
     $verified.two_distinct_kernel_service_generations -ne $true -or
     $verified.original_status_success -ne $false -or
     $verified.external_output_release_authorized -ne $false){
    throw 'Restart original uncertainty incorrectly accepted/released'
  }
  [ordered]@{
    schema='cognitum.ssm.r3.native_forced_scm_uncertain.v1'
    status='PASS_REAL_WINDOWS_SCM_FORCED_DEATH_SIGNED_UNCERTAIN_REFUSAL_CI_ONLY'
    source_original_service_pid=$originalPid
    native_SCM_hard_termination_observed=$true
    original_same_nonce_and_prelaunch_durable=$true
    independently_provisioned_machine_P256_prelaunch_signed=$true
    independently_provisioned_machine_P256_uncertain_restart_signed=$true
    independent_verifier_rechecks_original_nonce_and_two_generations=$true
    no_new_original_SSM_execution_authorized=$true
    original_terminal_kernel_empty_claimed=$false
    original_output_released=$false
    signer_installed_production_approved=$false
    appcontainer_numerical_worker_accepted=$false
    Lu_Core_Health_authenticated=$false
  } | ConvertTo-Json -Depth 5 | Set-Content -LiteralPath $EvidencePath -Encoding utf8
  Write-Host 'PASS_REAL_WINDOWS_SCM_FORCED_DEATH_SIGNED_UNCERTAIN_REFUSAL_CI_ONLY'
}finally {
 if($created){
   try{& sc.exe stop $svc | Out-Null}catch{}
   try{& sc.exe delete $svc | Out-Null}catch{}
 }
 $deadline=[DateTime]::UtcNow.AddSeconds(10)
 while([DateTime]::UtcNow -lt $deadline){
   if(!(Get-CimInstance Win32_Service -Filter "Name='$svc'")){break}
   Start-Sleep -Milliseconds 120
 }
 if(Get-CimInstance Win32_Service -Filter "Name='$svc'"){
   throw 'Temporary SCM original fixture could not be independently confirmed deleted'
 }
}
